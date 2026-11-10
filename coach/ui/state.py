"""État applicatif partagé : stockage, cache de lecture, coach IA, session Garmin, profil."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import schema
from ..ai import Coach
from ..config import get_secret
from ..garmin import GarminError, GarminSession
from ..storage import LocalStorage, Storage, build_storage
from ..training_load import fc_max_tanaka


@st.cache_resource(show_spinner=False)
def _storage() -> Storage:
    return build_storage()


def storage() -> Storage:
    try:
        return _storage()
    except Exception as exc:  # noqa: BLE001
        st.error(f"Connexion à la base impossible ({exc}). Bascule en stockage local.")
        return LocalStorage(get_secret("LOCAL_DATA_DIR", "data"))


def is_local() -> bool:
    return isinstance(storage(), LocalStorage)


@st.cache_data(ttl=300, show_spinner=False)
def load(sheet: str) -> pd.DataFrame:
    try:
        return storage().read(sheet)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Lecture de « {sheet} » impossible : {exc}")
        return schema.normalize(sheet, [])


def append(sheet: str, rows: list[list]) -> None:
    storage().append(sheet, rows)
    load.clear()


def clear_cache() -> None:
    load.clear()


@st.cache_resource(show_spinner=False)
def coach() -> Coach:
    return Coach()


# --- Profil -------------------------------------------------------------------
def age() -> int:
    return int(st.session_state.get("age", 25))


def fc_max() -> int:
    custom = st.session_state.get("fc_max_custom")
    return int(custom) if custom else fc_max_tanaka(age())


# --- Garmin -------------------------------------------------------------------
def garmin() -> GarminSession:
    """Session Garmin propre au navigateur (jamais partagée entre utilisateurs)."""
    if "garmin" not in st.session_state:
        session = GarminSession()
        st.session_state["garmin"] = session
        _auto_login(session)
    return st.session_state["garmin"]


def _auto_login(session: GarminSession) -> None:
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
