"""Dynamic Hybrid Coach — point d'entrée Streamlit.

Lancement : ``streamlit run app.py``
Sans secret configuré, l'application s'ouvre sur un stockage local (CSV) ; le
mode démo (athlète simulé) est accessible depuis la barre latérale.
"""

from __future__ import annotations

import streamlit as st

from coach import __version__
from coach.ui import state, theme
from coach.ui.pages import coach_ia, garmin_page, home, insights, method, predictions, readiness, risk_page, session, sleep_page

st.set_page_config(page_title="Dynamic Hybrid Coach", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
theme.inject()

PAGES = {
    "home": st.Page(home.render, title="Accueil", icon="🏠", default=True),
    "readiness": st.Page(readiness.render, title="Check-in du matin", icon="⚡", url_path="checkin"),
    "session": st.Page(session.render, title="Ma séance du jour", icon="🏃", url_path="seance"),
    "insights": st.Page(insights.render, title="Cockpit performance", icon="📊", url_path="insights"),
    "sleep": st.Page(sleep_page.render, title="Sommeil & VFC", icon="😴", url_path="sommeil"),
    "risk": st.Page(risk_page.render, title="Risque de blessure", icon="🛡️", url_path="risque"),
    "predict": st.Page(predictions.render, title="Prédictions", icon="🔮", url_path="predictions"),
    "coach": st.Page(coach_ia.render, title="Coach IA & programme", icon="🧠", url_path="coach"),
    "garmin": st.Page(garmin_page.render, title="Garmin Connect", icon="⌚", url_path="garmin"),
    "method": st.Page(method.render, title="Méthodologie & sources", icon="📚", url_path="methodologie"),
}
st.session_state["_pages"] = PAGES

SECTIONS = {
    "": [PAGES["home"]],
    "Au quotidien": [PAGES["readiness"], PAGES["session"]],
    "Analyses": [PAGES["insights"], PAGES["sleep"], PAGES["risk"], PAGES["predict"]],
    "Outils": [PAGES["coach"], PAGES["garmin"], PAGES["method"]],
}


def _access_controls() -> None:
    if state.password_protected():
        if state.is_demo():
            with st.expander("🔐 Accès athlète"):
                pwd = st.text_input("Mot de passe", type="password", label_visibility="collapsed", placeholder="Mot de passe")
                if st.button("Déverrouiller mes données", width="stretch") and pwd:
                    if state.unlock(pwd):
                        state.clear_cache()
                        st.rerun()
                    else:
                        st.error("Mot de passe incorrect.")
        elif st.button("🔒 Verrouiller (repasser en démo)", width="stretch"):
            state.lock()
            st.rerun()
    else:
        st.toggle("🧪 Mode démo (athlète simulé)", key="demo_mode", help="Explore l'application avec 12 semaines de données simulées, sans toucher à tes données réelles.")
    if state.is_demo() and st.button("↺ Réinitialiser la démo", width="stretch"):
        state.reset_demo()
        st.rerun()


def sidebar() -> None:
    with st.sidebar:
        st.markdown("## ⚡ Dynamic Hybrid Coach")
        _access_controls()

        with st.expander("👤 Profil athlète", expanded=False):
            st.number_input("Âge", min_value=15, max_value=85, step=1, key="age", value=state.age())
            st.number_input(
                "FC max (bpm) — 0 = estimation",
                min_value=0,
                max_value=230,
                step=1,
                key="fc_max_custom",
                value=st.session_state.get("fc_max_custom", 0),
                help="Laisse 0 pour utiliser la formule de Tanaka (208 − 0,7 × âge).",
            )
            st.caption(f"FC max utilisée : **{state.fc_max()} bpm**")
            st.slider("Besoin de sommeil (h / nuit)", 6.0, 10.0, step=0.25, key="sleep_need", value=state.sleep_need())

        garmin = state.garmin()
        storage = state.storage()
        status = [
            theme.pill("🧪 Démo" if state.is_demo() else "👤 Mes données", theme.AMBER if state.is_demo() else theme.GREEN),
            theme.pill(f"⌚ Garmin {'connecté' if garmin.connected else 'déconnecté'}", theme.GREEN if garmin.connected else theme.MUTED),
            *([] if state.is_demo() else [theme.pill(f"🗄️ {storage.label}", theme.ACCENT if not state.is_local() else theme.AMBER)]),
            theme.pill(f"🧠 IA {'Gemini' if state.coach().enabled else 'règles'}", theme.GREEN if state.coach().enabled else theme.MUTED),
        ]
        st.markdown("<div style='line-height:2'>" + "".join(status) + "</div>", unsafe_allow_html=True)

        st.divider()
        with st.expander("⚠️ Correction"):
            if st.button("🗑️ Annuler ma dernière séance", width="stretch"):
                ok, msg = storage.delete_last_session()
                state.clear_cache()
                (st.success if ok else st.error)(msg)
            if st.button("🔄 Rafraîchir les données", width="stretch"):
                state.clear_cache()
                st.rerun()

        st.divider()
        st.caption(f"v{__version__} · Conçu et développé par **Ali HAMDAN** · [LinkedIn](https://www.linkedin.com/in/alihamdan2002/)")


sidebar()
st.navigation(SECTIONS).run()
