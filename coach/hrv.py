"""Analyse de la VFC selon les pratiques de la recherche en sciences du sport.

Méthode (Plews et al. 2012-2013 ; Buchheit 2014 ; Altini, HRV4Training) :

* on travaille sur **ln(rMSSD)**, dont la distribution est quasi normale ;
* la **moyenne glissante sur 7 jours** lisse le bruit jour-à-jour (une mesure
  isolée est peu fiable) ;
* la **ligne de base** est la moyenne sur 60 jours, et la **plage normale**
  vaut baseline ± 0,5 écart-type (≈ plus petit changement significatif, SWC) ;
* le **coefficient de variation (CV)** sur 7 jours mesure la stabilité : un CV
  qui grimpe signale un système nerveux autonome perturbé, même si la moyenne
  reste dans la norme.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

BASELINE_DAYS = 60
MIN_BASELINE = 14
SWC_FACTOR = 0.5


def daily_hrv(checkins: pd.DataFrame) -> pd.Series:
    """Une valeur de VFC par jour (dernière mesure du jour), indexée par date."""
    if checkins is None or checkins.empty:
        return pd.Series(dtype=float)
    df = checkins[["Date", "VFC"]].dropna()
    df = df[df["VFC"] > 0]
    if df.empty:
        return pd.Series(dtype=float)
    s = df.assign(Date=df["Date"].dt.normalize()).groupby("Date")["VFC"].last()
    return s.sort_index().astype(float)


def hrv_trend(checkins: pd.DataFrame) -> pd.DataFrame:
    """Série complète : VFC brute, ln, moyenne 7 j, baseline, plage normale, CV."""
    vfc = daily_hrv(checkins)
    if vfc.empty:
        return pd.DataFrame(columns=["VFC", "ln", "ln7", "base", "lower", "upper", "cv7"])
    ln = np.log(vfc)
    ln7 = ln.rolling(7, min_periods=3).mean()
    base = ln.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE).mean()
    sd = ln.rolling(BASELINE_DAYS, min_periods=MIN_BASELINE).std()
    cv7 = ln.rolling(7, min_periods=3).std() / ln7 * 100
    return pd.DataFrame(
        {
            "VFC": vfc,
            "ln": ln,
            "ln7": ln7,
            "base": base,
            "lower": base - SWC_FACTOR * sd,
            "upper": base + SWC_FACTOR * sd,
            "cv7": cv7,
        }
    )


@dataclass
class HRVStatus:
    status: str  # "stable" | "basse" | "haute" | "insuffisant"
    label: str
    color: str
    advice: str
    vfc7: float | None = None
    baseline: float | None = None
    lower: float | None = None
    upper: float | None = None
    cv7: float | None = None
    cv_trend: float | None = None


def hrv_status(trend: pd.DataFrame) -> HRVStatus:
    if trend.empty or trend["base"].dropna().empty or pd.isna(trend["ln7"].iloc[-1]):
        n = int(trend["VFC"].count()) if not trend.empty else 0
        return HRVStatus("insuffisant", "Baseline en construction", "#8B949E", f"Il faut {MIN_BASELINE} jours de mesures pour établir ta plage normale ({n}/{MIN_BASELINE}).")
    last = trend.iloc[-1]
    vals = {k: float(np.exp(last[k])) for k in ("ln7", "base", "lower", "upper")}
    cv = float(last["cv7"]) if pd.notna(last["cv7"]) else None
    cv_prev = trend["cv7"].iloc[-15:-7].mean() if len(trend) > 14 else np.nan
    cv_trend = cv - float(cv_prev) if cv is not None and pd.notna(cv_prev) else None
    common = dict(vfc7=vals["ln7"], baseline=vals["base"], lower=vals["lower"], upper=vals["upper"], cv7=cv, cv_trend=cv_trend)
    if last["ln7"] < last["lower"]:
        return HRVStatus(
            "basse",
            "Sous ta plage normale",
            "#E74C3C",
            "VFC 7 j sous ta norme : fatigue accumulée, stress ou maladie probable. Réduis l'intensité et priorise le sommeil.",
            **common,
        )
    if last["ln7"] > last["upper"]:
        return HRVStatus(
            "haute",
            "Au-dessus de ta plage normale",
            "#5DADE2",
            "VFC 7 j au-dessus de ta norme : souvent bonne adaptation. Si la FC de repos chute et que les performances baissent, suspecte une saturation parasympathique (surmenage).",
            **common,
        )
    advice = "VFC stable dans ta plage normale : tu absorbes bien la charge."
    if cv_trend is not None and cv_trend > 2:
        advice += " Attention, la variabilité jour-à-jour augmente (CV en hausse) : surveille les prochains jours."
    return HRVStatus("stable", "Dans ta plage normale", "#58D68D", advice, **common)
