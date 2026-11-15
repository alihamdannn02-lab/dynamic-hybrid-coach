"""Entraînement — séance du jour, coach IA et programme, au même endroit."""

from __future__ import annotations

import streamlit as st

from ..i18n import t
from . import coach_ia, session


def render() -> None:
    tab_session, tab_coach, tab_plan = st.tabs([f"🏃 {t('tr.session')}", f"🧠 {t('tr.coach')}", f"📅 {t('tr.plan')}"])
    with tab_session:
        session.render(embedded=True)
    with tab_coach:
        coach_ia.generator()
    with tab_plan:
        coach_ia.planner()
