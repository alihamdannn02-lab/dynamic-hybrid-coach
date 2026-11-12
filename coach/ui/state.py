"""État applicatif partagé : mode d'accès, stockage, cache, analyses, coach IA, Garmin.

Deux modes d'accès :

* **athlète (propriétaire)** : données réelles (Google Sheets ou CSV) et
  connexion Garmin automatique via les secrets ;
* **démo** : chaque visiteur reçoit sa propre base en mémoire, pré-remplie avec
  12 semaines simulées. Il peut tout explorer, saisir des données ou connecter
  *sa* montre sans jamais toucher aux données réelles.

Si le secret ``APP_PASSWORD`` est défini (recommandé pour une URL publique),
les visiteurs arrivent en mode démo et le propriétaire déverrouille ses données
avec le mot de passe. Sinon, l'application s'ouvre sur les données réelles.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass

import pandas as pd
import streamlit as st

from .. import demo, schema
from ..ai import Coach
from ..config import get_secret
from ..forecast import HRVModel, train_hrv_model
from ..garmin import GarminError, GarminSession
from ..hrv import hrv_status, hrv_trend
from ..readiness import Readiness, readiness_from_history
from ..risk import RiskReport, compute_risk
from ..sleep import SleepSummary, sleep_frame, summarize
from ..storage import LocalStorage, MemoryStorage, Storage, build_storage
from ..training_load import acwr_status, daily_load, fc_max_tanaka, performance_manager, sessions_from_history

DEMO_AGE = 28


# --- Mode d'accès --------------------------------------------------------------
def password_protected() -> bool:
    return bool(get_secret("APP_PASSWORD"))


def is_demo() -> bool:
    if password_protected():
        return not st.session_state.get("owner_unlocked", False)
    return bool(st.session_state.get("demo_mode", False))


def unlock(password: str) -> bool:
    ok = hmac.compare_digest(str(password).encode(), str(get_secret("APP_PASSWORD")).encode())
    if ok:
        st.session_state["owner_unlocked"] = True
        _auto_login(garmin())
    return ok


def lock() -> None:
    st.session_state["owner_unlocked"] = False
    if "garmin" in st.session_state:
        st.session_state["garmin"].logout()
        del st.session_state["garmin"]


# --- Stockage -------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def _owner_storage() -> Storage:
    return build_storage()


def _demo_storage() -> MemoryStorage:
    if "demo_storage" not in st.session_state:
        mem = MemoryStorage()
        demo.seed(mem, age=DEMO_AGE)
        st.session_state["demo_storage"] = mem
    return st.session_state["demo_storage"]


def storage() -> Storage:
    if is_demo():
        return _demo_storage()
    try:
        return _owner_storage()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Connexion à la base impossible ({exc}). Bascule en stockage local.")
        return LocalStorage(get_secret("LOCAL_DATA_DIR", "data"))


def is_local() -> bool:
    s = storage()
    return isinstance(s, LocalStorage) and not isinstance(s, MemoryStorage)


@st.cache_data(ttl=300, show_spinner=False)
def _owner_load(sheet: str) -> pd.DataFrame:
    return _owner_storage().read(sheet)


def load(sheet: str) -> pd.DataFrame:
    try:
        if is_demo():
            return _demo_storage().read(sheet)
        return _owner_load(sheet)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Lecture de « {sheet} » impossible : {exc}")
        return schema.normalize(sheet, [])


def append(sheet: str, rows: list[list]) -> None:
    storage().append(sheet, rows)
    clear_cache()


def clear_cache() -> None:
    _owner_load.clear()
    _analytics.clear()


def reset_demo() -> None:
    st.session_state.pop("demo_storage", None)


# --- Analyses partagées par les pages --------------------------------------------
@dataclass
class Analytics:
    realise: pd.DataFrame
    checkins: pd.DataFrame
    sessions: pd.DataFrame
    daily: pd.Series
    pmc: pd.DataFrame
    readiness: Readiness | None
    risk: RiskReport
    hrv: pd.DataFrame
    sleep: pd.DataFrame
    sleep_summary: SleepSummary
    hrv_model: HRVModel

    @property
    def hrv_status(self):
        return hrv_status(self.hrv)

    @property
    def load_status(self):
        return acwr_status(self.daily)


@st.cache_data(ttl=300, show_spinner=False)
def _analytics(realise: pd.DataFrame, checkins: pd.DataFrame, need_h: float) -> Analytics:
    sessions = sessions_from_history(realise)
    daily = daily_load(sessions)
    return Analytics(
        realise=realise,
        checkins=checkins,
        sessions=sessions,
        daily=daily,
        pmc=performance_manager(daily),
        readiness=readiness_from_history(checkins),
        risk=compute_risk(daily, checkins),
        hrv=hrv_trend(checkins),
        sleep=sleep_frame(checkins),
        sleep_summary=summarize(sleep_frame(checkins), need_h),
        hrv_model=train_hrv_model(daily, checkins),
    )


def analytics() -> Analytics:
    return _analytics(load(schema.REALISE), load(schema.CHECKIN), sleep_need())


@st.cache_resource(show_spinner=False)
def coach() -> Coach:
    return Coach()


# --- Profil -------------------------------------------------------------------
def age() -> int:
    return int(st.session_state.get("age", DEMO_AGE if is_demo() else 25))


def fc_max() -> int:
    custom = st.session_state.get("fc_max_custom")
    return int(custom) if custom else fc_max_tanaka(age())


def sleep_need() -> float:
    return float(st.session_state.get("sleep_need", 8.0))


# --- Garmin -------------------------------------------------------------------
def garmin() -> GarminSession:
    """Session Garmin propre au navigateur (jamais partagée entre utilisateurs)."""
    if "garmin" not in st.session_state:
        session = GarminSession()
        st.session_state["garmin"] = session
        if not is_demo():  # jamais de connexion automatique au compte du propriétaire pour un visiteur
            _auto_login(session)
    return st.session_state["garmin"]


def _auto_login(session: GarminSession) -> None:
    if session.connected:
        return
    tokens = get_secret("GARMIN_TOKENS")
    email, password = get_secret("GARMIN_EMAIL"), get_secret("GARMIN_PASSWORD")
    try:
        if tokens:
            session.login_with_tokens(str(tokens))
        elif email and password:
            session.login(str(email), str(password))
    except GarminError as exc:
        st.session_state["garmin_autologin_error"] = str(exc)


def current_week() -> int:
    prog = load(schema.PROGRAMME)
    if prog.empty or prog["Semaine"].dropna().empty:
        return 1
    return int(prog["Semaine"].max())


def imported_activity_ids() -> set[str]:
    df = load(schema.REALISE)
    if df.empty:
        return set()
    return {str(x) for x in df["Activity_ID"] if str(x).strip()}


def checkin_dates() -> set[str]:
    df = load(schema.CHECKIN)
    if df.empty:
        return set()
    return set(df["Date"].dt.strftime("%Y-%m-%d"))
