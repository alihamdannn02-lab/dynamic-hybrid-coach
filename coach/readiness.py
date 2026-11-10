"""Score de Readiness matinal.

Contrairement à la V3 (comparaison à des normes populationnelles fixes), la VFC et
la FC de repos sont comparées à la **ligne de base personnelle** de l'athlète
(moyenne glissante des 30 derniers check-ins) dès que l'historique le permet.
C'est l'approche utilisée par les plateformes de référence (HRV4Training,
Whoop, Garmin HRV Status) : une VFC de 45 ms peut être excellente pour l'un et
alarmante pour l'autre.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

MIN_BASELINE_POINTS = 5
WEIGHTS = {"sommeil": 0.25, "energie": 0.20, "fcr": 0.25, "vfc": 0.30}


@dataclass
class Baseline:
    vfc: float = 60.0
    fcr: float = 50.0
    personal: bool = False
    n: int = 0


@dataclass
class Readiness:
    score: int
    components: dict[str, float] = field(default_factory=dict)
    baseline: Baseline = field(default_factory=Baseline)

    @property
    def status(self) -> str:
        if self.score >= 75:
            return "green"
        if self.score >= 50:
            return "amber"
        return "red"

    @property
    def advice(self) -> str:
        return {
            "green": "🟢 **Feu vert !** Tes constantes sont excellentes : séance qualitative possible.",
            "amber": "🟡 **Attention.** Récupération moyenne : privilégie l'endurance fondamentale (Z2).",
            "red": "🔴 **Alerte fatigue.** Constantes dans le rouge : repos ou récupération active.",
        }[self.status]


def _clip(x: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, x))


def score_sommeil(heures: float) -> float:
    if 7.5 <= heures <= 9.0:
        return 100.0
    if heures > 9.0:
        return 85.0
    # décroissance linéaire : 7.5h -> 100, 4h -> 0
    return _clip((heures - 4.0) / 3.5 * 100.0)


def score_vfc(vfc: float, base: float) -> float:
    """100 si VFC >= baseline, 0 à -30 % de la baseline."""
    if base <= 0:
        return 50.0
    ratio = vfc / base
    return _clip((ratio - 0.70) / 0.30 * 100.0)


def score_fcr(fcr: float, base: float) -> float:
    """100 si FCR <= baseline, -12.5 points par bpm au-dessus (0 à +8 bpm)."""
    return _clip(100.0 - max(0.0, fcr - base) * 12.5)


def compute_baseline(history: pd.DataFrame | None, window: int = 30) -> Baseline:
    """Ligne de base personnelle à partir de l'historique de check-in (hors jour courant)."""
    if history is None or history.empty:
        return Baseline()
    recent = history.sort_values("Date").tail(window)
    vfc = recent["VFC"].dropna()
    fcr = recent["FC_Repos"].dropna()
    vfc = vfc[vfc > 0]
    fcr = fcr[fcr > 0]
    if len(vfc) < MIN_BASELINE_POINTS or len(fcr) < MIN_BASELINE_POINTS:
        return Baseline(n=int(min(len(vfc), len(fcr))))
    return Baseline(vfc=float(vfc.mean()), fcr=float(fcr.mean()), personal=True, n=int(len(vfc)))


def compute_readiness(sommeil: float, vfc: float, fcr: float, energie: float, baseline: Baseline | None = None) -> Readiness:
    baseline = baseline or Baseline()
    comps = {
        "sommeil": score_sommeil(float(sommeil)),
        "energie": _clip(float(energie) * 10.0),
        "fcr": score_fcr(float(fcr), baseline.fcr),
        "vfc": score_vfc(float(vfc), baseline.vfc),
    }
    total = sum(comps[k] * w for k, w in WEIGHTS.items())
    return Readiness(score=round(total), components=comps, baseline=baseline)


def readiness_from_history(checkins: pd.DataFrame) -> Readiness | None:
    """Readiness du dernier check-in, avec une baseline calculée sur les précédents."""
    if checkins is None or checkins.empty:
        return None
    df = checkins.sort_values("Date").reset_index(drop=True)
    last = df.iloc[-1]
    baseline = compute_baseline(df.iloc[:-1])
    try:
        return compute_readiness(
            float(last["Heures_Sommeil"]),
            float(last["VFC"]),
            float(last["FC_Repos"]),
            float(last["Niveau_Energie"]),
            baseline,
        )
    except (TypeError, ValueError):
        return None
