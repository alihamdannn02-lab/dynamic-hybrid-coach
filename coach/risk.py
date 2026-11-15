"""Indice de risque de blessure multifactoriel et explicable.

Le risque de blessure n'est jamais prédit par un seul marqueur. L'indice combine
six facteurs issus de la littérature, chacun converti en points, pour obtenir un
score de 0 à 100 dont **chaque point est traçable** jusqu'à sa cause :

| Facteur | Seuils | Référence |
|---|---|---|
| ACWR (EWMA 7/28 j) | > 1,3 vigilance ; > 1,5 danger ; < 0,8 sous-charge | Gabbett 2016 ; Williams et al. 2017 |
| Monotonie de Foster | > 2,0 | Foster 1998 |
| VFC 7 j sous la plage normale | ln rMSSD < baseline − 0,5 ET | Plews et al. 2013 |
| FC de repos 7 j au-dessus de la baseline | +3 / +5 bpm | Buchheit 2014 |
| Sommeil moyen 7 j | < 7 h ; < 6,5 h | Milewski et al. 2014 |
| Douleurs déclarées | récentes ; même zone ≥ 3 j sur 7 | Clarsen et al. 2013 (OSTRC) |

⚠️ Limites assumées : l'ACWR est débattu (Impellizzeri et al. 2020, couplage
mathématique) et cet indice est une **aide à la décision heuristique**, non un
modèle clinique validé. Il signale quand regarder de plus près, il ne pose pas
de diagnostic.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .hrv import hrv_trend

NO_PAIN = {"", "aucun", "aucune", "nan", "none"}


@dataclass
class Factor:
    key: str
    name: str
    points: float
    max_points: float
    value: str
    why: str
    action: str


@dataclass
class RiskReport:
    score: int
    level: str
    color: str
    factors: list[Factor] = field(default_factory=list)
    timeline: pd.DataFrame = field(default_factory=pd.DataFrame)
    coverage: list[str] = field(default_factory=list)

    @property
    def drivers(self) -> list[Factor]:
        return sorted([f for f in self.factors if f.points > 0], key=lambda f: -f.points)


def level_of(score: float) -> tuple[str, str]:
    if score >= 50:
        return "Élevé", "#E74C3C"
    if score >= 25:
        return "Modéré", "#E67E22"
    return "Faible", "#58D68D"


def ewma_acwr(daily: pd.Series) -> pd.Series:
    """ACWR par moyennes exponentielles (Williams et al. 2017), λ = 2 / (N + 1)."""
    acute = daily.ewm(alpha=2 / (7 + 1), adjust=False).mean()
    chronic = daily.ewm(alpha=2 / (28 + 1), adjust=False).mean()
    return (acute / chronic.replace(0, np.nan)).where(np.arange(len(daily)) >= 27)


def _pain_series(checkins: pd.DataFrame, index: pd.DatetimeIndex) -> tuple[pd.Series, pd.Series, pd.Series]:
    """→ (douleur récente 3 j, zone persistante 7 j, libellé de la zone persistante)."""
    recent = pd.Series(False, index=index)
    persistent = pd.Series(False, index=index)
    zone = pd.Series("", index=index)
    if checkins is None or checkins.empty:
        return recent, persistent, zone
    by_day: dict[pd.Timestamp, set[str]] = {}
    for d, txt in zip(checkins["Date"].dt.normalize(), checkins["Muscles_Douloureux"].astype(str)):
        zones = {z.strip() for z in txt.split(",") if z.strip().lower() not in NO_PAIN}
        if zones:
            by_day.setdefault(d, set()).update(zones)
    for d in index:
        window = [by_day.get(d - pd.Timedelta(days=k), set()) for k in range(7)]
        recent[d] = any(window[:3])
        counts: dict[str, int] = {}
        for zs in window:
            for z in zs:
                counts[z] = counts.get(z, 0) + 1
        worst = max(counts.items(), key=lambda kv: kv[1], default=("", 0))
        if worst[1] >= 3:
            persistent[d], zone[d] = True, worst[0]
    return recent, persistent, zone


def _daily(checkins: pd.DataFrame, col: str, index: pd.DatetimeIndex) -> pd.Series:
    if checkins is None or checkins.empty:
        return pd.Series(np.nan, index=index)
    s = checkins[["Date", col]].dropna()
    s = s[s[col] > 0]
    s = s.assign(Date=s["Date"].dt.normalize()).groupby("Date")[col].last()
    return s.reindex(index)


def compute_risk(daily_load: pd.Series, checkins: pd.DataFrame) -> RiskReport:
    """Calcule l'indice jour par jour et détaille les facteurs du dernier jour."""
    dates = []
    if daily_load is not None and not daily_load.empty:
        dates += [daily_load.index.min(), daily_load.index.max()]
    if checkins is not None and not checkins.empty:
        dates += [checkins["Date"].min().normalize(), checkins["Date"].max().normalize()]
    if not dates:
        return RiskReport(0, "Données insuffisantes", "#8B949E", coverage=["Aucune donnée d'entraînement ni de check-in."])
    idx = pd.date_range(min(dates), max(max(dates), pd.Timestamp.today().normalize()), freq="D")
    load = (daily_load if daily_load is not None else pd.Series(dtype=float)).reindex(idx, fill_value=0.0).astype(float)
    coverage = []

    # 1. ACWR
    acwr = ewma_acwr(load)
    p_acwr = pd.Series(0.0, index=idx)
    p_acwr[acwr > 1.3] = 18
    p_acwr[acwr > 1.5] = 30
    p_acwr[acwr < 0.8] = 6
    if acwr.dropna().empty:
        coverage.append("ACWR : 4 semaines d'entraînement nécessaires.")

    # 2. Monotonie
    roll = load.rolling(7, min_periods=7)
    monotony = roll.mean() / roll.std().replace(0, np.nan)
    p_mono = ((monotony > 2.0) & (roll.mean() > 0)).astype(float) * 12

    # 3. VFC
    trend = hrv_trend(checkins).reindex(idx).ffill(limit=2)
    below = trend["ln7"] < trend["lower"]
    p_hrv = below.astype(float) * 20
    if trend["base"].dropna().empty:
        coverage.append("VFC : 14 jours de mesures nécessaires pour la plage normale.")

    # 4. FC de repos
    rhr = _daily(checkins, "FC_Repos", idx)
    rhr7 = rhr.rolling(7, min_periods=3).mean()
    rhr_base = rhr.rolling(60, min_periods=14).mean()
    rhr_delta = rhr7 - rhr_base
    p_rhr = pd.Series(0.0, index=idx)
    p_rhr[rhr_delta >= 3] = 8
    p_rhr[rhr_delta >= 5] = 15
    if rhr_base.dropna().empty:
        coverage.append("FC de repos : 14 jours de mesures nécessaires.")

    # 5. Sommeil
    sleep = _daily(checkins, "Heures_Sommeil", idx)
    sleep7 = sleep.rolling(7, min_periods=3).mean()
    p_sleep = pd.Series(0.0, index=idx)
    p_sleep[sleep7 < 7.0] = 8
    p_sleep[sleep7 < 6.5] = 15

    # 6. Douleurs
    recent, persistent, zone = _pain_series(checkins, idx)
    p_pain = recent.astype(float) * 8
    p_pain[persistent] = 20

    parts = pd.DataFrame({"acwr": p_acwr, "monotonie": p_mono, "vfc": p_hrv, "fcr": p_rhr, "sommeil": p_sleep, "douleur": p_pain})
    timeline = parts.assign(score=parts.sum(axis=1).clip(upper=100))

    d = idx[-1]
    fmt = lambda v, f: "—" if pd.isna(v) else f.format(v)  # noqa: E731
    factors = [
        Factor(
            "acwr",
            "Pic de charge (ACWR)",
            p_acwr[d],
            30,
            fmt(acwr[d], "{:.2f}"),
            "Une charge aiguë (7 j) qui dépasse largement la charge chronique (28 j) expose les tissus à plus que ce à quoi ils sont adaptés.",
            "Limite la hausse de charge à ~10 % par semaine ; remplace une séance intense par de l'endurance fondamentale.",
        ),
        Factor(
            "monotonie",
            "Monotonie de l'entraînement",
            p_mono[d],
            12,
            fmt(monotony[d], "{:.2f}"),
            "Des journées toutes semblables (peu de vraies journées faciles) empêchent la récupération (Foster).",
            "Alterne vraiment jours durs et jours faciles ; garde au moins un jour de repos complet.",
        ),
        Factor(
            "vfc",
            "VFC sous la norme",
            p_hrv[d],
            20,
            fmt(np.exp(trend["ln7"][d]) if pd.notna(trend["ln7"][d]) else np.nan, "{:.0f} ms (7 j)"),
            "Une VFC durablement basse traduit une dominance sympathique : fatigue, stress, maladie.",
            "Réduis l'intensité 2-3 jours, priorise sommeil et nutrition, puis réévalue.",
        ),
        Factor(
            "fcr",
            "FC de repos élevée",
            p_rhr[d],
            15,
            fmt(rhr_delta[d], "{:+.1f} bpm vs baseline"),
            "Une FC de repos qui monte de plusieurs bpm sur une semaine accompagne souvent la fatigue ou une infection.",
            "Vérifie l'hydratation et les signes de maladie ; pas d'intensité tant qu'elle ne redescend pas.",
        ),
        Factor(
            "sommeil",
            "Manque de sommeil",
            p_sleep[d],
            15,
            fmt(sleep7[d], "{:.1f} h / nuit (7 j)"),
            "Moins de 7-8 h par nuit est associé à un risque de blessure nettement plus élevé chez le sportif.",
            "Vise 8 h et plus : couche-toi 30 min plus tôt cette semaine.",
        ),
        Factor(
            "douleur",
            "Douleurs déclarées",
            p_pain[d],
            20,
            f"{zone[d]} (≥ 3 j / 7)" if persistent[d] else ("récentes" if recent[d] else "aucune"),
            "Une douleur qui persiste au même endroit est le premier signe d'une blessure de surcharge.",
            "Supprime l'impact sur la zone concernée et consulte si la douleur persiste au-delà d'une semaine.",
        ),
    ]
    score = int(round(timeline["score"].iloc[-1]))
    level, color = level_of(score)
    return RiskReport(score, level, color, factors, timeline, coverage)
