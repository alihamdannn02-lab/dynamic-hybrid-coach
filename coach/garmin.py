"""Intégration Garmin Connect.

Garmin ne propose son API officielle (Health / Activity API) qu'aux entreprises
partenaires. Pour un usage personnel, on s'appuie sur la bibliothèque
open-source ``garminconnect`` qui utilise le même protocole que l'application
mobile Garmin Connect :

* connexion e-mail / mot de passe, avec prise en charge de la double
  authentification (MFA) ;
* réutilisation d'un jeton (``GARMIN_TOKENS``) pour éviter de se reconnecter à
  chaque démarrage — recommandé sur Streamlit Cloud, Garmin limitant les
  connexions SSO répétées.

Le mot de passe n'est jamais stocké : seule la session (jetons) est conservée
dans ``st.session_state``, propre à chaque navigateur.

Les fonctions ``parse_*`` sont pures et testées unitairement : elles tolèrent
les champs absents (selon le modèle de montre, toutes les métriques ne sont pas
disponibles).
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from typing import Any

from . import schema

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modèles de données
# ---------------------------------------------------------------------------
@dataclass
class Wellness:
    date: str
    sommeil_h: float | None = None
    score_sommeil: int | None = None
    vfc: int | None = None
    vfc_status: str | None = None
    vfc_hebdo: int | None = None
    fcr: int | None = None
    body_battery: int | None = None
    training_readiness: int | None = None
    training_readiness_level: str | None = None
    stress: int | None = None
    errors: list[str] = field(default_factory=list)

    @property
    def energie_suggeree(self) -> int | None:
        """Body Battery (0-100) → énergie perçue (1-10)."""
        if self.body_battery is None:
            return None
        return int(min(10, max(1, round(self.body_battery / 10))))

    @property
    def has_data(self) -> bool:
        return any(v is not None for v in (self.sommeil_h, self.vfc, self.fcr, self.body_battery))

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Activity:
    activity_id: str
    name: str
    start: datetime
    type_key: str
    sport: str
    distance_km: float
    duration_min: int
    elevation_m: int
    avg_hr: int | None
    zones_min: list[int]
    rpe: float | None
    pace_or_power: str
    training_load: float | None = None

    @property
    def date_str(self) -> str:
        return self.start.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _num(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    v = _num(value)
    return None if v is None else int(round(v))


SPORT_MAP = {
    "running": "Course à pied",
    "street_running": "Course à pied",
    "track_running": "Course à pied",
    "treadmill_running": "Course à pied",
    "indoor_running": "Course à pied",
    "virtual_run": "Course à pied",
    "trail_running": "Trail / Ski Alpinisme",
    "ultra_run": "Trail / Ski Alpinisme",
    "hiking": "Trail / Ski Alpinisme",
    "mountaineering": "Trail / Ski Alpinisme",
    "backcountry_skiing": "Trail / Ski Alpinisme",
    "backcountry_skiing_snowboarding_ws": "Trail / Ski Alpinisme",
    "skate_skiing_ws": "Trail / Ski Alpinisme",
    "cross_country_skiing_ws": "Trail / Ski Alpinisme",
    "cycling": "Cyclisme",
    "road_biking": "Cyclisme",
    "mountain_biking": "Cyclisme",
    "gravel_cycling": "Cyclisme",
    "indoor_cycling": "Cyclisme",
    "virtual_ride": "Cyclisme",
    "e_bike_fitness": "Cyclisme",
    "lap_swimming": "Natation",
    "open_water_swimming": "Natation",
    "swimming": "Natation",
    "strength_training": "Renforcement / PPG",
    "indoor_cardio": "Cross-Training",
    "hiit": "Cross-Training",
    "boxing": "Cross-Training",
    "fitness_equipment": "Cross-Training",
    "indoor_rowing": "Cross-Training",
    "rowing": "Cross-Training",
    "yoga": "Mobilité",
    "pilates": "Mobilité",
    "breathwork": "Mobilité",
    "walking": "Marche",
    "multi_sport": "Triathlon / Multisport",
    "triathlon": "Triathlon / Multisport",
}


def map_sport(type_key: str) -> str:
    key = (type_key or "").lower()
    if key in SPORT_MAP:
        return SPORT_MAP[key]
    for fragment, sport in (("run", "Course à pied"), ("bik", "Cyclisme"), ("cycl", "Cyclisme"), ("swim", "Natation"), ("ski", "Trail / Ski Alpinisme")):
        if fragment in key:
            return sport
    return "Autre"


def format_pace(sport: str, avg_speed_ms: float | None, avg_power: float | None) -> str:
    if sport == "Cyclisme":
        if avg_power:
            return f"{round(avg_power)} W"
        if avg_speed_ms:
            return f"{avg_speed_ms * 3.6:.1f} km/h"
        return ""
    if not avg_speed_ms or avg_speed_ms <= 0:
        return ""
    if sport == "Natation":
        secs = 100 / avg_speed_ms
        return f"{int(secs // 60)}:{int(secs % 60):02d} min/100m"
    secs = 1000 / avg_speed_ms
    return f"{int(secs // 60)}:{int(secs % 60):02d} min/km"


# ---------------------------------------------------------------------------
# Parseurs (fonctions pures)
# ---------------------------------------------------------------------------
def parse_sleep(sleep: dict | None) -> tuple[float | None, int | None, int | None, int | None]:
    """→ (heures de sommeil, score, VFC nocturne moyenne, FC repos)."""
    if not isinstance(sleep, dict):
        return None, None, None, None
    dto = sleep.get("dailySleepDTO") or {}
    secs = _num(dto.get("sleepTimeSeconds"))
    hours = round(secs / 3600, 1) if secs else None
    scores = dto.get("sleepScores") or {}
    overall = scores.get("overall") or {}
    score = _int(overall.get("value"))
    return hours, score, _int(sleep.get("avgOvernightHrv")), _int(sleep.get("restingHeartRate"))


def parse_hrv(hrv: dict | None) -> tuple[int | None, str | None, int | None]:
    """→ (VFC moyenne de la nuit, statut Garmin, moyenne 7 j)."""
    if not isinstance(hrv, dict):
        return None, None, None
    summary = hrv.get("hrvSummary") or {}
    return _int(summary.get("lastNightAvg")), summary.get("status"), _int(summary.get("weeklyAvg"))


def parse_rhr(rhr: dict | None) -> int | None:
    if not isinstance(rhr, dict):
        return None
    metrics = (rhr.get("allMetrics") or {}).get("metricsMap") or {}
    values = metrics.get("WELLNESS_RESTING_HEART_RATE") or []
    for item in values:
        v = _int(item.get("value"))
        if v:
            return v
    return None


def parse_training_readiness(data: Any) -> tuple[int | None, str | None]:
    if isinstance(data, list):
        data = data[0] if data else None
    if not isinstance(data, dict):
        return None, None
    return _int(data.get("score")), data.get("level")


def parse_activity(raw: dict, zones_payload: Any = None) -> Activity:
    type_key = (raw.get("activityType") or {}).get("typeKey", "")
    sport = map_sport(type_key)
    start_str = raw.get("startTimeLocal") or raw.get("startTimeGMT") or ""
    try:
        start = datetime.fromisoformat(str(start_str).replace("T", " ").split(".")[0])
    except ValueError:
        start = datetime.now()

    zones_sec = [_num(raw.get(f"hrTimeInZone_{i}")) for i in range(1, 6)]
    if all(z is None for z in zones_sec) and isinstance(zones_payload, list):
        by_zone = {int(z.get("zoneNumber", 0)): _num(z.get("secsInZone")) for z in zones_payload if isinstance(z, dict)}
        zones_sec = [by_zone.get(i) for i in range(1, 6)]
    zones_min = [int(round((z or 0) / 60)) for z in zones_sec]

    raw_rpe = _num(raw.get("directWorkoutRpe"))
    rpe = round(raw_rpe / 10, 1) if raw_rpe else None  # Garmin : échelle 10-100
    if rpe is None:
        from .training_load import rpe_from_zones

        rpe = rpe_from_zones(zones_min)

    duration = _num(raw.get("duration")) or _num(raw.get("movingDuration")) or 0
    return Activity(
        activity_id=str(raw.get("activityId", "")),
        name=str(raw.get("activityName") or type_key or "Activité Garmin"),
        start=start,
        type_key=type_key,
        sport=sport,
        distance_km=round((_num(raw.get("distance")) or 0) / 1000, 2),
        duration_min=int(round(duration / 60)),
        elevation_m=_int(raw.get("elevationGain")) or 0,
        avg_hr=_int(raw.get("averageHR")),
        zones_min=zones_min,
        rpe=rpe,
        pace_or_power=format_pace(sport, _num(raw.get("averageSpeed")), _num(raw.get("avgPower"))),
        training_load=_num(raw.get("activityTrainingLoad")),
    )


def activity_to_row(act: Activity, semaine: int, default_rpe: int = 5) -> list:
    """Ligne au format ``Historique_Realise``."""
    rpe = int(round(act.rpe)) if act.rpe else default_rpe
    is_strength = act.sport == "Renforcement / PPG"
    return schema.pad_row(
        schema.REALISE,
        [
            act.date_str,
            int(semaine),
            schema.jour_fr(act.start),
            act.name,
            "Séance Garmin" if is_strength else "Bilan Endurance | Garmin",
            0.0,
            0,
            0,
            0,
            rpe,
            float(act.distance_km),
            int(act.duration_min),
            *[int(z) for z in act.zones_min],
            act.sport,
            int(act.elevation_m),
            act.pace_or_power,
            act.activity_id,
        ],
    )


# ---------------------------------------------------------------------------
# Session Garmin (I/O)
# ---------------------------------------------------------------------------
class GarminError(Exception):
    """Erreur présentable à l'utilisateur."""


def _friendly(exc: Exception) -> GarminError:
    name = type(exc).__name__
    if "TooManyRequests" in name:
        return GarminError("Garmin limite les tentatives de connexion. Réessaie dans quelques minutes.")
    if "Authentication" in name:
        return GarminError("Identifiants refusés par Garmin (ou code MFA invalide).")
    return GarminError(f"Connexion à Garmin impossible : {exc}")


class GarminSession:
    """Encapsule l'authentification et la collecte des données Garmin Connect."""

    def __init__(self) -> None:
        self.api = None
        self._pending = None  # instance Garmin en attente du code MFA
        self._mfa_state = None

    # --- Authentification -------------------------------------------------
    @property
    def connected(self) -> bool:
        return self.api is not None

    @property
    def awaiting_mfa(self) -> bool:
        return self._pending is not None

    @property
    def display_name(self) -> str:
        if not self.api:
            return ""
        return getattr(self.api, "full_name", None) or getattr(self.api, "display_name", "") or ""

    def login_with_tokens(self, tokens: str) -> None:
        from garminconnect import Garmin

        try:
            api = Garmin()
            api.login(tokenstore=tokens)
        except Exception as exc:  # noqa: BLE001
            raise _friendly(exc) from exc
        self.api = api

    def login(self, email: str, password: str, is_cn: bool = False) -> str:
        """Retourne ``"ok"`` ou ``"mfa"`` si un code de vérification est requis."""
        from garminconnect import Garmin

        try:
            api = Garmin(email=email, password=password, is_cn=is_cn, return_on_mfa=True)
            status, state = api.login()
        except Exception as exc:  # noqa: BLE001
            raise _friendly(exc) from exc
        if status == "needs_mfa":
            self._pending, self._mfa_state = api, state
            return "mfa"
        # En mode return_on_mfa, le profil n'est pas encore chargé : on rouvre
        # proprement la session à partir des jetons fraîchement émis.
        self.login_with_tokens(api.client.dumps())
        return "ok"

    def submit_mfa(self, code: str) -> None:
        if not self._pending:
            raise GarminError("Aucune connexion en attente de code MFA.")
        try:
            self._pending.resume_login(self._mfa_state, code.strip())
        except Exception as exc:  # noqa: BLE001
            raise _friendly(exc) from exc
        self.api, self._pending, self._mfa_state = self._pending, None, None

    def tokens(self) -> str | None:
        return self.api.client.dumps() if self.api else None

    def logout(self) -> None:
        if self.api:
            try:
                self.api.logout()
            except Exception:  # noqa: BLE001
                pass
        self.api, self._pending, self._mfa_state = None, None, None

    # --- Données ------------------------------------------------------------
    def _call(self, errors: list[str], label: str, fn, *args):
        try:
            return fn(*args)
        except Exception as exc:  # noqa: BLE001
            log.info("Garmin %s indisponible : %s", label, exc)
            errors.append(label)
            return None

    def fetch_wellness(self, day: date | None = None) -> Wellness:
        if not self.api:
            raise GarminError("Non connecté à Garmin.")
        d = (day or date.today()).isoformat()
        w = Wellness(date=d)
        api, err = self.api, w.errors

        sleep = self._call(err, "sommeil", api.get_sleep_data, d)
        w.sommeil_h, w.score_sommeil, vfc_sleep, rhr_sleep = parse_sleep(sleep)

        hrv = self._call(err, "VFC", api.get_hrv_data, d)
        w.vfc, w.vfc_status, w.vfc_hebdo = parse_hrv(hrv)
        w.vfc = w.vfc or vfc_sleep

        summary = self._call(err, "résumé quotidien", api.get_user_summary, d) or {}
        w.fcr = _int(summary.get("restingHeartRate")) or rhr_sleep
        if not w.fcr:
            w.fcr = parse_rhr(self._call(err, "FC repos", api.get_rhr_day, d))
        w.body_battery = _int(summary.get("bodyBatteryMostRecentValue")) or _int(summary.get("bodyBatteryHighestValue"))
        w.stress = _int(summary.get("averageStressLevel"))
        if w.stress is not None and w.stress < 0:
            w.stress = None

        tr = self._call(err, "Training Readiness", api.get_training_readiness, d)
        w.training_readiness, w.training_readiness_level = parse_training_readiness(tr)
        return w

    def fetch_activities(self, start: date, end: date) -> list[Activity]:
        if not self.api:
            raise GarminError("Non connecté à Garmin.")
        try:
            raws = self.api.get_activities_by_date(start.isoformat(), end.isoformat())
        except Exception as exc:  # noqa: BLE001
            raise _friendly(exc) from exc
        activities = []
        for raw in raws or []:
            zones = None
            if raw.get("hrTimeInZone_1") is None and raw.get("averageHR") and raw.get("activityId"):
                zones = self._call([], "zones FC", self.api.get_activity_hr_in_timezones, raw["activityId"])
            activities.append(parse_activity(raw, zones))
        return sorted(activities, key=lambda a: a.start, reverse=True)
