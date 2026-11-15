"""Analyse du sommeil : quantité, dette, régularité, architecture et impact sur la VFC.

Références : Walker (2017) ; Phillips et al. (2017, Sleep Regularity) ;
Mah et al. (2011, extension du sommeil chez l'athlète) ; Milewski et al.
(2014, < 8 h de sommeil et risque de blessure chez l'adolescent sportif) ;
Wittmann et al. (2006, « social jetlag »).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .hrv import daily_hrv

DEFAULT_NEED_H = 8.0


def _to_minutes(value) -> float:
    """'23:40' → minutes depuis 18 h (gère le passage de minuit : 01:10 → 430)."""
    try:
        h, m = str(value).strip().split(":")[:2]
        return (int(h) * 60 + int(m) - 18 * 60) % 1440
    except (ValueError, AttributeError):
        return np.nan


def _fmt_minutes(minutes: float) -> str:
    if minutes is None or pd.isna(minutes):
        return "—"
    total = (int(round(minutes)) + 18 * 60) % 1440
    return f"{total // 60:02d}:{total % 60:02d}"


def sleep_frame(checkins: pd.DataFrame) -> pd.DataFrame:
    """Une ligne par nuit (datée du matin du réveil)."""
    if checkins is None or checkins.empty:
        return pd.DataFrame()
    df = checkins.copy()
    df["Date"] = df["Date"].dt.normalize()
    df = df.groupby("Date").last().reset_index().sort_values("Date")
    df = df[df["Heures_Sommeil"].fillna(0) > 0]
    out = pd.DataFrame(
        {
            "Date": df["Date"],
            "Heures": df["Heures_Sommeil"],
            "Score": df["Score_Sommeil"],
            "Deep": df["Deep_Min"],
            "REM": df["REM_Min"],
            "Light": df["Light_Min"],
            "Awake": df["Awake_Min"],
            "Bed": df["Coucher"].map(_to_minutes),
            "Wake": df["Lever"].map(_to_minutes),
        }
    )
    return out.reset_index(drop=True)


@dataclass
class SleepSummary:
    nights: int
    avg_h: float | None = None
    avg_h_28: float | None = None
    debt_h: float | None = None
    need_h: float = DEFAULT_NEED_H
    bed_sd: float | None = None
    wake_sd: float | None = None
    bedtime: str = "—"
    waketime: str = "—"
    deep_pct: float | None = None
    rem_pct: float | None = None
    efficiency: float | None = None
    social_jetlag: float | None = None
    score: float | None = None
    regularity: str = "—"
    insights: list[tuple[str, str]] = field(default_factory=list)  # (niveau, message)


def summarize(frame: pd.DataFrame, need_h: float = DEFAULT_NEED_H) -> SleepSummary:
    if frame is None or frame.empty:
        return SleepSummary(nights=0, need_h=need_h)
    last7 = frame.tail(7)
    last28 = frame.tail(28)
    s = SleepSummary(nights=len(frame), need_h=need_h)
    s.avg_h = float(last7["Heures"].mean())
    s.avg_h_28 = float(last28["Heures"].mean())
    s.debt_h = float((need_h - last7["Heures"]).clip(lower=0).sum())
    if last28["Bed"].notna().sum() >= 5:
        s.bed_sd = float(last28["Bed"].std())
        s.wake_sd = float(last28["Wake"].std())
        s.bedtime = _fmt_minutes(last28["Bed"].mean())
        s.waketime = _fmt_minutes(last28["Wake"].mean())
        mid = (last28["Bed"] + (last28["Wake"] - last28["Bed"]) % 1440 / 2) % 1440
        weekend = last28["Date"].dt.weekday >= 5
        if weekend.any() and (~weekend).any():
            s.social_jetlag = float(abs(mid[weekend].mean() - mid[~weekend].mean()))
    stages = last28[["Deep", "REM", "Light", "Awake"]].dropna()
    if len(stages) >= 3:
        asleep = stages[["Deep", "REM", "Light"]].sum(axis=1)
        s.deep_pct = float((stages["Deep"] / asleep).mean() * 100)
        s.rem_pct = float((stages["REM"] / asleep).mean() * 100)
        s.efficiency = float((asleep / (asleep + stages["Awake"])).mean() * 100)
    if last7["Score"].notna().any():
        s.score = float(last7["Score"].mean())

    if s.bed_sd is not None:
        s.regularity = "Excellente" if s.bed_sd < 30 else "Correcte" if s.bed_sd < 60 else "Irrégulière"

    ins = s.insights
    if s.avg_h < 7:
        ins.append(("error", f"Moyenne de {s.avg_h:.1f} h sur 7 nuits : sous le seuil de 7 h associé à un risque de blessure accru chez le sportif."))
    elif s.avg_h < need_h - 0.25:
        ins.append(("warning", f"{s.avg_h:.1f} h en moyenne : correct, mais sous ton besoin de {need_h:g} h. Les athlètes gagnent en performance en visant 8 à 10 h."))
    else:
        ins.append(("success", f"{s.avg_h:.1f} h en moyenne sur 7 nuits : volume de sommeil optimal pour récupérer."))
    if s.debt_h >= 5:
        ins.append(("error", f"Dette de sommeil de {s.debt_h:.1f} h cette semaine : planifie des nuits plus longues ou une sieste de 20-30 min."))
    if s.bed_sd is not None and s.bed_sd >= 60:
        ins.append(("warning", f"Heure de coucher variable (± {s.bed_sd:.0f} min) : la régularité compte autant que la durée pour la qualité du sommeil."))
    if s.social_jetlag is not None and s.social_jetlag >= 60:
        ins.append(("warning", f"« Jetlag social » de {s.social_jetlag:.0f} min entre semaine et week-end : ton horloge biologique se décale chaque lundi."))
    if s.deep_pct is not None and s.deep_pct < 13:
        ins.append(("info", f"Sommeil profond à {s.deep_pct:.0f} % : c'est la phase de sécrétion d'hormone de croissance. Évite l'alcool et l'intensité tardive."))
    return s


@dataclass
class SleepHRVEffect:
    n: int
    r: float | None = None
    short_ms: float | None = None  # VFC moyenne après nuits courtes
    long_ms: float | None = None  # VFC moyenne après nuits longues
    threshold: float = 7.0


def sleep_hrv_effect(checkins: pd.DataFrame, threshold: float = 7.0) -> SleepHRVEffect:
    """Lien personnel entre durée de la nuit et VFC mesurée au réveil."""
    frame = sleep_frame(checkins)
    hrv = daily_hrv(checkins)
    if frame.empty or hrv.empty:
        return SleepHRVEffect(n=0, threshold=threshold)
    df = frame.set_index("Date")[["Heures"]].join(hrv.rename("VFC"), how="inner").dropna()
    eff = SleepHRVEffect(n=len(df), threshold=threshold)
    if len(df) < 10 or df["Heures"].std() == 0:
        return eff
    eff.r = float(np.corrcoef(df["Heures"], np.log(df["VFC"]))[0, 1])
    short, long_ = df[df["Heures"] < threshold], df[df["Heures"] >= threshold]
    if len(short) >= 3 and len(long_) >= 3:
        eff.short_ms, eff.long_ms = float(short["VFC"].mean()), float(long_["VFC"].mean())
    return eff
