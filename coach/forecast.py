"""Prédictions : VFC du lendemain, forme le jour J, temps de course.

1. **Modèle personnel de VFC** — régression ridge entraînée sur l'historique
   de l'athlète : la VFC de demain matin est expliquée par la charge du jour,
   celle de la veille, la nuit à venir et l'état du jour. Le modèle est évalué
   en **validation glissante** (walk-forward : chaque jour est prédit avec les
   seules données antérieures) et comparé à une prédiction naïve
   (« demain = aujourd'hui »). Le gain réel est affiché, même s'il est nul.
2. **Planificateur de forme** — projection du modèle de Banister (CTL/ATL/TSB)
   jusqu'à une date de course selon plusieurs scénarios, dont un affûtage
   progressif (−55 % sur 10 jours, Bosquet et al. 2007).
3. **Prédicteur de temps** — formule de Riegel (1981) appliquée à la meilleure
   sortie récente.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .training_load import ATL_DAYS, CTL_DAYS, performance_manager

# ---------------------------------------------------------------------------
# 1. Modèle de VFC
# ---------------------------------------------------------------------------
FEATURES = ["charge_j", "fraicheur", "sommeil", "etat_j"]
FEATURE_LABELS = {
    "charge_j": "Charge du jour (+100 TSS)",
    "fraicheur": "Fraîcheur TSB (+10 points)",
    "sommeil": "Nuit à venir (+1 h)",
    "etat_j": "VFC du jour au-dessus de ta baseline (+10 %)",
}
SCALES = {"charge_j": 1.0, "fraicheur": 1.0, "sommeil": 1.0, "etat_j": 0.1}
MIN_ROWS = 28


def hrv_dataset(daily_load: pd.Series, checkins: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par matin d : cible = ln(VFC_d) − baseline (moyenne 60 j jusqu'à d−1)."""
    if checkins is None or checkins.empty or daily_load is None or daily_load.empty:
        return pd.DataFrame()
    ck = checkins.assign(Date=checkins["Date"].dt.normalize()).groupby("Date").last()
    vfc = ck["VFC"].where(ck["VFC"] > 0)
    idx = pd.date_range(min(vfc.index.min(), daily_load.index.min()), max(vfc.index.max(), daily_load.index.max()), freq="D")
    ln = np.log(vfc.reindex(idx))
    base = ln.rolling(60, min_periods=10).mean().shift(1)
    dev = ln - base
    load = daily_load.reindex(idx, fill_value=0.0)
    tsb = performance_manager(load)["TSB"]  # TSB[d] = CTL − ATL en fin de journée d−1
    df = pd.DataFrame(
        {
            "y": dev,
            "charge_j": load.shift(1) / 100,
            "fraicheur": tsb / 10,
            "sommeil": ck["Heures_Sommeil"].reindex(idx) - 7.5,
            "etat_j": dev.shift(1),
            "base": base,
            "vfc": vfc.reindex(idx),
            "vfc_prev": vfc.reindex(idx).shift(1),
        }
    )
    return df.dropna()


def _fit(X: np.ndarray, y: np.ndarray, lam: float = 1.0):
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1
    Z = (X - mu) / sd
    beta = np.linalg.solve(Z.T @ Z + lam * np.eye(Z.shape[1]), Z.T @ (y - y.mean()))
    coef = beta / sd
    intercept = y.mean() - mu @ coef
    return intercept, coef


@dataclass
class HRVModel:
    n: int
    intercept: float = 0.0
    coef: dict[str, float] = field(default_factory=dict)
    mae_model: float | None = None
    mae_naive: float | None = None
    resid_sd: float | None = None
    backtest: pd.DataFrame = field(default_factory=pd.DataFrame)

    @property
    def ready(self) -> bool:
        return bool(self.coef)

    @property
    def gain_pct(self) -> float | None:
        if not self.mae_model or not self.mae_naive:
            return None
        return (1 - self.mae_model / self.mae_naive) * 100

    def effect_pct(self, key: str) -> float:
        """Effet d'une unité de la variable sur la VFC du lendemain, en %."""
        return (np.exp(self.coef[key] * SCALES[key]) - 1) * 100

    def predict_dev(self, charge_j: float, tsb: float, sommeil_h: float, etat_j: float) -> float:
        x = np.array([charge_j / 100, tsb / 10, sommeil_h - 7.5, etat_j])
        return float(self.intercept + x @ np.array([self.coef[k] for k in FEATURES]))


def train_hrv_model(daily_load: pd.Series, checkins: pd.DataFrame, backtest_days: int = 30) -> HRVModel:
    df = hrv_dataset(daily_load, checkins)
    model = HRVModel(n=len(df))
    if len(df) < MIN_ROWS:
        return model
    X, y = df[FEATURES].to_numpy(), df["y"].to_numpy()

    start = max(20, len(df) - backtest_days)
    rows = []
    for i in range(start, len(df)):
        b0, b = _fit(X[:i], y[:i])
        pred = df["base"].iloc[i] + b0 + X[i] @ b
        rows.append({"Date": df.index[i], "Réel": df["vfc"].iloc[i], "Modèle": float(np.exp(pred)), "Naïf": df["vfc_prev"].iloc[i]})
    bt = pd.DataFrame(rows).set_index("Date")
    model.backtest = bt
    model.mae_model = float((bt["Réel"] - bt["Modèle"]).abs().mean())
    model.mae_naive = float((bt["Réel"] - bt["Naïf"]).abs().mean())

    model.intercept, coef = _fit(X, y)
    model.coef = dict(zip(FEATURES, coef))
    model.resid_sd = float(np.std(y - (model.intercept + X @ coef)))
    return model


@dataclass
class TodayState:
    base_ln: float  # baseline (ln) qui servira de référence demain matin
    etat_j: float  # écart du jour à la baseline (ln)
    charge_jour: float  # TSS déjà réalisé aujourd'hui
    ctl: float  # CTL / ATL de la veille au soir
    atl: float
    vfc_jour: float

    def tsb_tomorrow(self, charge_jour: float) -> float:
        """TSB de demain matin si l'athlète réalise ``charge_jour`` aujourd'hui."""
        ctl = self.ctl + (charge_jour - self.ctl) / CTL_DAYS
        atl = self.atl + (charge_jour - self.atl) / ATL_DAYS
        return ctl - atl


def today_state(daily_load: pd.Series, checkins: pd.DataFrame) -> TodayState | None:
    if checkins is None or checkins.empty:
        return None
    ck = checkins.assign(Date=checkins["Date"].dt.normalize()).groupby("Date").last()
    vfc = ck["VFC"].where(ck["VFC"] > 0).dropna()
    if len(vfc) < 10:
        return None
    ln = np.log(vfc)
    base_today = ln.iloc[:-1].tail(60).mean()
    today = pd.Timestamp.today().normalize()
    load = daily_load if daily_load is not None else pd.Series(dtype=float)
    pmc = performance_manager(load[load.index < today]) if not load.empty else pd.DataFrame()
    return TodayState(
        base_ln=float(ln.tail(60).mean()),
        etat_j=float(ln.iloc[-1] - base_today),
        charge_jour=float(load.get(today, 0.0)),
        ctl=float(pmc["CTL"].iloc[-1]) if not pmc.empty else 0.0,
        atl=float(pmc["ATL"].iloc[-1]) if not pmc.empty else 0.0,
        vfc_jour=float(vfc.iloc[-1]),
    )


# ---------------------------------------------------------------------------
# 2. Planificateur de forme (Banister)
# ---------------------------------------------------------------------------
def project_pmc(ctl0: float, atl0: float, plan: np.ndarray, start: pd.Timestamp) -> pd.DataFrame:
    ctl, atl = ctl0, atl0
    rows = []
    for load in plan:
        tsb = ctl - atl
        ctl += (load - ctl) / CTL_DAYS
        atl += (load - atl) / ATL_DAYS
        rows.append((load, ctl, atl, tsb))
    idx = pd.date_range(start, periods=len(plan), freq="D")
    return pd.DataFrame(rows, index=idx, columns=["TSS", "CTL", "ATL", "TSB"])


def race_scenarios(pmc: pd.DataFrame, race_date: pd.Timestamp, taper_days: int = 10) -> dict[str, pd.DataFrame]:
    last = pmc.iloc[-1]
    base = float(pmc["TSS"].tail(28).mean())
    start = pmc.index[-1] + pd.Timedelta(days=1)
    n = max(1, (race_date.normalize() - start).days + 1)
    t = np.arange(n)
    maintain = np.full(n, base)
    build = base * 1.08 ** (t // 7)
    taper = maintain.copy()
    k = min(taper_days, n)
    taper[n - k :] = base * np.linspace(1.0, 0.45, k)
    return {name: project_pmc(last.CTL, last.ATL, plan, start) for name, plan in (("Maintien", maintain), ("Progression +8 %/sem.", build), ("Affûtage 10 j", taper))}


def best_scenario(scenarios: dict[str, pd.DataFrame], window: tuple[float, float] = (5, 25)) -> str:
    """Le scénario qui arrive le plus en forme (CTL max) avec une fraîcheur (TSB) dans la cible."""
    ok = {k: v.iloc[-1] for k, v in scenarios.items() if window[0] <= v["TSB"].iloc[-1] <= window[1]}
    if ok:
        return max(ok, key=lambda k: ok[k]["CTL"])
    return min(scenarios, key=lambda k: abs(scenarios[k]["TSB"].iloc[-1] - np.mean(window)))


# ---------------------------------------------------------------------------
# 3. Prédicteur de temps (Riegel)
# ---------------------------------------------------------------------------
RACES = {"5 km": 5.0, "10 km": 10.0, "Semi-marathon": 21.0975, "Marathon": 42.195}
RUN_SPORTS = {"Course à pied", "Trail / Ski Alpinisme"}


def riegel(t_min: float, d1: float, d2: float, k: float = 1.06) -> float:
    return t_min * (d2 / d1) ** k


def fmt_time(minutes: float) -> str:
    secs = int(round(minutes * 60))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h}h{m:02d}'{s:02d}" if h else f"{m}'{s:02d}"


def race_predictions(realise: pd.DataFrame, days: int = 90) -> dict | None:
    if realise is None or realise.empty:
        return None
    since = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    runs = realise[
        realise["Sport_Discipline"].isin(RUN_SPORTS)
        & (realise["Distance_Km"] >= 3)
        & (realise["Duree_Min"] > 0)
        & (realise["Date"] >= since)
        & (realise["Denivele_M"].fillna(0) < realise["Distance_Km"] * 25)  # exclut le trail très vallonné
    ]
    if runs.empty:
        return None
    eq10 = runs.apply(lambda r: riegel(r["Duree_Min"], r["Distance_Km"], 10.0), axis=1)
    best = runs.loc[eq10.idxmin()]
    preds = {name: riegel(best["Duree_Min"], best["Distance_Km"], d) for name, d in RACES.items()}
    return {"source": best, "predictions": preds}
