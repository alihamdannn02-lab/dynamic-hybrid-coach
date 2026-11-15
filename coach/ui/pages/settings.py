"""Réglages — Garmin, profil, accès aux données, méthodologie.

Streamlit efface l'état d'un widget quand sa page n'est plus affichée : chaque
réglage est donc recopié dans une clé « durable » (``age``, ``demo_mode``…) que
le reste de l'application lit.
"""

from __future__ import annotations

import streamlit as st

from .. import state
from ..i18n import t
from . import garmin_page, method


def _persist(widget_key: str, key: str) -> None:
    st.session_state[key] = st.session_state[widget_key]


def _profile() -> None:
    st.number_input(t("set.age"), 15, 85, value=state.age(), step=1, key="_w_age", on_change=_persist, args=("_w_age", "age"))
    st.number_input(t("set.fcmax"), 0, 230, value=int(st.session_state.get("fc_max_custom", 0)), step=1, key="_w_fcmax", on_change=_persist, args=("_w_fcmax", "fc_max_custom"))
    st.caption(t("set.fcmax.used", v=state.fc_max()))
    st.slider(t("set.need"), 6.0, 10.0, value=state.sleep_need(), step=0.25, key="_w_need", on_change=_persist, args=("_w_need", "sleep_need"))


def _access() -> None:
    st.markdown(t("acc.demo") if state.is_demo() else t("acc.owner"))
    if state.password_protected():
        if state.is_demo():
            with st.form("unlock"):
                pwd = st.text_input(t("acc.pwd"), type="password", placeholder=t("acc.pwd"))
                if st.form_submit_button(t("acc.unlock"), type="primary") and pwd:
                    if state.unlock(pwd):
                        state.clear_cache()
                        st.rerun()
                    st.error(t("acc.bad"))
        elif st.button(f"🔒 {t('acc.lock')}"):
            state.lock()
            st.rerun()
    else:
        st.toggle(t("acc.toggle"), value=state.is_demo(), key="_w_demo", on_change=_persist, args=("_w_demo", "demo_mode"))
    if state.is_demo() and st.button(f"↺ {t('acc.reset')}"):
        state.reset_demo()
        st.rerun()

    st.divider()
    c1, c2 = st.columns(2)
    if c1.button(f"🗑️ {t('acc.undo')}", width="stretch"):
        ok, msg = state.storage().delete_last_session()
        state.clear_cache()
        (st.success if ok else st.warning)(msg)
    if c2.button(f"🔄 {t('acc.refresh')}", width="stretch"):
        state.clear_cache()
        st.rerun()
    st.caption(f"🗄️ {state.storage().label} · 🧠 IA {'Gemini' if state.coach().enabled else 'règles'}")


def render() -> None:
    tab_garmin, tab_profile, tab_access, tab_method = st.tabs([f"⌚ {t('set.garmin')}", f"👤 {t('set.profile')}", f"🔐 {t('set.access')}", f"📚 {t('set.method')}"])
    with tab_garmin:
        garmin_page.render(embedded=True)
    with tab_profile:
        _profile()
    with tab_access:
        _access()
    with tab_method:
        method.render(embedded=True)
