"""Dynamic Hybrid Coach — point d'entrée Streamlit.

Lancement : ``streamlit run app.py``. Quatre pages seulement :
Aujourd'hui (la décision), Entraînement, Analyses (le détail) et Réglages.
"""

from __future__ import annotations

import streamlit as st

from coach import __version__
from coach.ui import state, theme
from coach.ui.i18n import LANGS, t
from coach.ui.pages import analyses, settings, today, training

st.set_page_config(page_title="Dynamic Hybrid Coach", page_icon="⚡", layout="wide", initial_sidebar_state="collapsed")
theme.inject()

st.session_state.setdefault("lang", "FR")

PAGES = {
    "today": st.Page(today.render, title=t("nav.today"), icon="🏠", url_path="aujourdhui", default=True),
    "training": st.Page(training.render, title=t("nav.training"), icon="🏃", url_path="entrainement"),
    "analyses": st.Page(analyses.render, title=t("nav.analyses"), icon="📈", url_path="analyses"),
    "settings": st.Page(settings.render, title=t("nav.settings"), icon="⚙️", url_path="reglages"),
}
st.session_state["_pages"] = PAGES

nav = st.navigation(list(PAGES.values()), position="top")

_, right = st.columns([6, 1])
with right:
    choice = st.segmented_control("Langue", LANGS, default=st.session_state["lang"], key="_w_lang", label_visibility="collapsed")
    if choice and choice != st.session_state["lang"]:
        st.session_state["lang"] = choice
        st.rerun()

nav.run()

badge = theme.pill("🧪 Démo" if state.is_demo() else "👤 Mes données", theme.AMBER if state.is_demo() else theme.GREEN)
st.markdown(
    f"<div style='margin-top:40px; color:#8B949E; font-size:0.8rem'>{badge} v{__version__} · {t('app.footer')} <b>Ali HAMDAN</b> · "
    "<a href='https://www.linkedin.com/in/alihamdan2002/' target='_blank'>LinkedIn</a></div>",
    unsafe_allow_html=True,
)
