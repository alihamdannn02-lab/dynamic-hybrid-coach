"""Dynamic Hybrid Coach — point d'entrée Streamlit.

Lancement : ``streamlit run app.py``
Sans secret configuré, l'application démarre en mode local (CSV) avec la
possibilité de charger un jeu de données de démonstration.
"""

from __future__ import annotations

import streamlit as st

from coach import __version__, demo
from coach.storage import LocalStorage
from coach.ui import state, theme
from coach.ui.pages import coach_ia, garmin_page, insights, readiness, session

st.set_page_config(page_title="Dynamic Hybrid Coach", page_icon="⚡", layout="wide", initial_sidebar_state="expanded")
theme.inject()

PAGES = {
    "readiness": st.Page(readiness.render, title="Morning Readiness", icon="⚡", default=True),
    "session": st.Page(session.render, title="Ma Séance du Jour", icon="🏃", url_path="seance"),
    "insights": st.Page(insights.render, title="Cockpit Performance", icon="📊", url_path="insights"),
    "coach": st.Page(coach_ia.render, title="Coach IA & Programme", icon="🧠", url_path="coach"),
    "garmin": st.Page(garmin_page.render, title="Garmin Connect", icon="⌚", url_path="garmin"),
}
st.session_state["_pages"] = PAGES


def sidebar() -> None:
    with st.sidebar:
        st.markdown("## ⚡ Dynamic Hybrid Coach")

        with st.expander("👤 Profil athlète", expanded=False):
            st.number_input("Âge", min_value=15, max_value=85, step=1, key="age", value=st.session_state.get("age", 25))
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

        garmin = state.garmin()
        storage = state.storage()
        status = [
            theme.pill(f"⌚ Garmin {'connecté' if garmin.connected else 'déconnecté'}", theme.GREEN if garmin.connected else theme.MUTED),
            theme.pill(f"🗄️ {storage.label}", theme.ACCENT if not state.is_local() else theme.AMBER),
            theme.pill(f"🧠 IA {'Claude' if state.coach().enabled else 'règles'}", theme.GREEN if state.coach().enabled else theme.MUTED),
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

        if isinstance(storage, LocalStorage):
            with st.expander("🧪 Mode démo"):
                st.caption("Aucune base Google Sheets configurée : les données sont stockées localement en CSV.")
                if st.button("Charger 8 semaines de données de démo", width="stretch"):
                    demo.seed(storage, age=state.age())
                    state.clear_cache()
                    st.rerun()

        st.divider()
        st.caption(f"v{__version__} · POC par **Ali HAMDAN** · [LinkedIn](https://www.linkedin.com/in/alihamdan2002/)")


sidebar()
st.navigation(list(PAGES.values())).run()
