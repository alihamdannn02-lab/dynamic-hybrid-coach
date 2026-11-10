"""Modélisation de la charge d'entraînement.

* **Charge par séance** : TSS estimé à partir de la méthode sRPE de Foster
  (durée × intensité perçue), converti sur l'échelle TSS (100 = 1 h au seuil)
  afin que les seuils de forme (TSB) habituels restent pertinents.
* **Banister / Performance Manager** : CTL (42 j) et ATL (7 j) calculées comme
  des moyennes exponentielles **journalières** (les jours sans séance comptent
  pour 0 — erreur fréquente que corrigeait mal la V3).
* **ACWR** (Acute:Chronic Workload Ratio, Gabbett 2016) : 7 j / 28 j.
* **Zones cardiaques** : FCmax estimée par la formule de Tanaka (208 − 0,7 × âge).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

CTL_DAYS = 42
ATL_DAYS = 7

ZONES = [
    # (nom, borne basse %FCmax, borne haute %FCmax, couleur)
    ("Z1 · Récup", 0.50, 0.60, "#5DADE2"),
    ("Z2 · Endurance", 0.60, 0.70, "#58D68D"),
    ("Z3 · Tempo", 0.70, 0.80, "#F4D03F"),
    ("Z4 · Seuil", 0.80, 0.90, "#E67E22"),
    ("Z5 · VO2max", 0.90, 1.00, "#E74C3C"),
]
ZONE_RPE = [2.0, 4.0, 6.0, 8.0, 9.5]


def fc_max_tanaka(age: float) -> int:
    return round(208 - 0.7 * age)


def hr_zones(fc_max: int) -> list[dict]:
    return [{"zone": name, "min": round(lo * fc_max), "max": round(hi * fc_max), "color": color} for name, lo, hi, color in ZONES]


def rpe_from_zones(minutes: list[float]) -> float | None:
    """RPE estimé à partir du temps passé dans chaque zone (pondération par la durée)."""
    total = float(sum(minutes))
    if total <= 0:
        return None
    return round(sum(m * r for m, r in zip(minutes, ZONE_RPE)) / total, 1)


def estimate_tss(duration_min: float, rpe: float) -> float:
    """TSS approché : h × IF² × 100 avec IF ≈ 0.45 + 0.055 × RPE (RPE 10 → IF 1.0)."""
    if not duration_min or not rpe or duration_min <= 0 or rpe <= 0:
        return 0.0
    intensity = 0.45 + 0.055 * float(np.clip(rpe, 1, 10))
    return round(duration_min / 60.0 * intensity**2 * 100.0, 1)


def sessions_from_history(realise: pd.DataFrame) -> pd.DataFrame:
    """Regroupe les lignes (une par série en muscu) en séances uniques."""
    if realise is None or realise.empty:
        return pd.DataFrame(columns=["Date", "Semaine", "Sport_Discipline", "Session_RPE", "Duree", "Denivele", "Distance", "TSS"])
    df = realise.copy()
    df["Sport_Discipline"] = df["Sport_Discipline"].astype(str).str.strip().replace({"": "Renforcement / PPG", "nan": "Renforcement / PPG"})
    df["Day"] = df["Date"].dt.normalize()
    grouped = (
        df.groupby(["Day", "Sport_Discipline", "Type_Seance"], dropna=False)
        .agg(
            Semaine=("Semaine", "max"),
            Session_RPE=("Session_RPE", "max"),
            Duree=("Duree_Min", "max"),
            Denivele=("Denivele_M", "max"),
            Distance=("Distance_Km", "max"),
        )
        .reset_index()
        .rename(columns={"Day": "Date"})
    )
    grouped = grouped.fillna({"Session_RPE": 0, "Duree": 0, "Denivele": 0, "Distance": 0})
    # Les séances de repos ont un RPE (fatigue) mais aucune charge.
    is_rest = grouped["Sport_Discipline"].str.lower().eq("repos")
    grouped.loc[is_rest, "Duree"] = 0
    grouped["TSS"] = [estimate_tss(d, r) for d, r in zip(grouped["Duree"], grouped["Session_RPE"])]
    return grouped.sort_values("Date").reset_index(drop=True)


def daily_load(sessions: pd.DataFrame, until: pd.Timestamp | None = None) -> pd.Series:
    """Série journalière continue de TSS (0 les jours sans entraînement)."""
    if sessions is None or sessions.empty:
        return pd.Series(dtype=float)
    daily = sessions.groupby("Date")["TSS"].sum()
    end = max(daily.index.max(), (until or pd.Timestamp.today()).normalize())
    idx = pd.date_range(daily.index.min(), end, freq="D")
    return daily.reindex(idx, fill_value=0.0).astype(float)


def _ewma_from_zero(daily: pd.Series, days: int) -> pd.Series:
    """X_t = X_{t-1} + (TSS_t − X_{t-1}) / τ, avec X_0 = 0 (athlète sans historique).

    ``Series.ewm(adjust=False)`` initialise sur la première valeur : une seule
    grosse séance le premier jour gonflerait artificiellement la CTL.
    """
    values = np.empty(len(daily))
    acc = 0.0
    for i, load in enumerate(daily.to_numpy(dtype=float)):
        acc += (load - acc) / days
        values[i] = acc
    return pd.Series(values, index=daily.index)


def performance_manager(daily: pd.Series) -> pd.DataFrame:
    """CTL / ATL / TSB (modèle impulsion-réponse de Banister, version Coggan)."""
    if daily.empty:
        return pd.DataFrame(columns=["TSS", "CTL", "ATL", "TSB"])
    ctl = _ewma_from_zero(daily, CTL_DAYS)
    atl = _ewma_from_zero(daily, ATL_DAYS)
    tsb = (ctl - atl).shift(1).fillna(0.0)
    return pd.DataFrame({"TSS": daily, "CTL": ctl, "ATL": atl, "TSB": tsb})


@dataclass
class LoadStatus:
    acwr: float | None
    label: str
    color: str
    advice: str
    monotony: float | None


def acwr_status(daily: pd.Series) -> LoadStatus:
    """Ratio charge aiguë / chronique et monotonie de Foster sur 7 jours."""
    if daily is None or len(daily) < 14:
        return LoadStatus(None, "Données insuffisantes", "gray", "Il faut au moins 2 semaines d'historique.", None)
    acute = daily.tail(7).mean()
    chronic = daily.tail(28).mean()
    week = daily.tail(7)
    monotony = float(week.mean() / week.std()) if week.std() > 0 else None
    if chronic <= 0:
        return LoadStatus(None, "Reprise", "gray", "Pas de charge chronique : progresse graduellement.", monotony)
    ratio = round(float(acute / chronic), 2)
    if ratio > 1.5:
        return LoadStatus(ratio, "Zone de danger", "#E74C3C", "Pic de charge brutal : réduis le volume cette semaine.", monotony)
    if ratio > 1.3:
        return LoadStatus(ratio, "Vigilance", "#E67E22", "Charge en hausse rapide : surveille sommeil et douleurs.", monotony)
    if ratio >= 0.8:
        return LoadStatus(ratio, "Zone optimale", "#58D68D", "Progression maîtrisée (sweet spot 0.8 – 1.3).", monotony)
    return LoadStatus(ratio, "Désentraînement", "#5DADE2", "Charge faible : idéal en affûtage, sinon augmente progressivement.", monotony)


def tsb_label(tsb: float) -> str:
    if tsb > 10:
        return "Frais / affûté"
    if tsb >= -10:
        return "Neutre"
    if tsb >= -30:
        return "Surcharge productive"
    return "Risque de surmenage"
