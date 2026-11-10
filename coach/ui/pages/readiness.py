"""Page 1 — Morning Readiness : check-in matinal (Garmin, NLP ou manuel)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import streamlit as st

from ... import schema
from ...ai import MUSCLES
from ...garmin import GarminError
from ...readiness import compute_baseline, compute_readiness
from .. import state, theme

BODY_MAP = Path(__file__).resolve().parents[3] / "body_map.png"

DEFAULTS = {"ck_sommeil": 7.5, "ck_fcr": 50, "ck_vfc": 60, "ck_energie": 7, "ck_douleurs": []}


def _apply(values: dict, source: str) -> None:
    mapping = {"sommeil": ("ck_sommeil", float), "fcr": ("ck_fcr", int), "vfc": ("ck_vfc", int), "energie": ("ck_energie", int)}
    for key, (state_key, cast) in mapping.items():
        if values.get(key) is not None:
            st.session_state[state_key] = cast(values[key])
    if values.get("douleurs"):
        st.session_state["ck_douleurs"] = list(values["douleurs"])
    st.session_state["ck_source"] = source


def _garmin_block() -> None:
    garmin = state.garmin()
    with st.container(border=True):
        c1, c2 = st.columns([3, 1], vertical_alignment="center")
        c1.markdown("#### ⌚ Garmin Connect")
        if not garmin.connected:
            c1.caption("Connecte ta montre pour remplir automatiquement sommeil, VFC, FC de repos et Body Battery.")
            if c2.button("Connecter", width="stretch"):
                st.switch_page(st.session_state["_pages"]["garmin"])
            return
        c1.caption(f"Connecté — {garmin.display_name}")
        if c2.button("📥 Importer ma nuit", type="primary", width="stretch"):
            with st.spinner("Lecture des données Garmin…"):
                try:
                    w = garmin.fetch_wellness(date.today())
                except GarminError as exc:
                    st.error(str(exc))
                    return
            st.session_state["garmin_wellness"] = w
            if w.has_data:
                _apply({"sommeil": w.sommeil_h, "fcr": w.fcr, "vfc": w.vfc, "energie": w.energie_suggeree}, "Garmin")
                st.rerun()
            else:
                st.warning("Aucune donnée de récupération pour cette nuit : la montre a-t-elle synchronisé ?")

        w = st.session_state.get("garmin_wellness")
        if w and w.date == date.today().isoformat():
            m = st.columns(4)
            m[0].metric("Sommeil", f"{w.sommeil_h} h" if w.sommeil_h else "—", f"score {w.score_sommeil}" if w.score_sommeil else None, delta_color="off")
            m[1].metric("VFC nuit", f"{w.vfc} ms" if w.vfc else "—", w.vfc_status.title() if w.vfc_status else None, delta_color="off")
            m[2].metric("Body Battery", w.body_battery if w.body_battery is not None else "—")
            m[3].metric("Training Readiness", w.training_readiness if w.training_readiness is not None else "—", (w.training_readiness_level or "").title() or None, delta_color="off")
            if w.errors:
                st.caption("Non disponible sur ce modèle / cette nuit : " + ", ".join(w.errors))


def _nlp_block() -> None:
    coach = state.coach()
    with st.expander("🎙️ Assistant rapide — dicte ta nuit en une phrase", expanded=not state.garmin().connected):
        texte = st.text_area(
            "Ta nuit en une phrase",
            placeholder="Ex : J'ai dormi 7h30, FC repos 44, VFC 68, je suis en forme mais j'ai mal aux mollets.",
            label_visibility="collapsed",
        )
        if st.button("🪄 Remplir automatiquement", disabled=not texte.strip()):
            with st.spinner("Analyse sémantique…"):
                values, source = coach.extract_checkin(texte, state.age())
            if not any(values.get(k) is not None for k in ("sommeil", "fcr", "vfc", "energie")) and not values.get("douleurs"):
                st.warning("Je n'ai trouvé aucune valeur exploitable dans ce texte.")
            else:
                _apply(values, "NLP")
                st.session_state["nlp_source"] = source
                st.rerun()
        if st.session_state.get("nlp_source") == "règles":
            st.caption("ℹ️ Extraction par règles (IA non configurée ou indisponible).")


def render() -> None:
    st.title("⚡ Morning Readiness")
    st.markdown("<p class='hero'>Tes constantes du matin, comparées à <b>ta</b> ligne de base.</p>", unsafe_allow_html=True)

    for k, v in DEFAULTS.items():
        st.session_state.setdefault(k, v)

    _garmin_block()
    _nlp_block()

    st.subheader("📊 Constantes physiologiques")
    c1, c2 = st.columns(2)
    with c1:
        sommeil = st.slider("💤 Heures de sommeil", 0.0, 12.0, step=0.25, key="ck_sommeil")
        fcr = st.number_input("❤️ FC de repos (bpm)", min_value=30, max_value=110, step=1, key="ck_fcr")
    with c2:
        energie = st.slider("🔋 Énergie perçue (1-10)", 1, 10, key="ck_energie")
        vfc = st.number_input("📉 VFC (ms, RMSSD)", min_value=5, max_value=250, step=1, key="ck_vfc")

    history = state.load(schema.CHECKIN)
    today = date.today().isoformat()
    prev = history[history["Date"].dt.strftime("%Y-%m-%d") != today] if not history.empty else history
    baseline = compute_baseline(prev)
    r = compute_readiness(sommeil, vfc, fcr, energie, baseline)

    with st.container(border=True):
        g, t = st.columns([1, 1.3], vertical_alignment="center")
        g.plotly_chart(theme.gauge(r.score, "Readiness (aperçu)"), config={"displayModeBar": False}, key="gauge_preview")
        with t:
            st.markdown(r.advice)
            if baseline.personal:
                st.caption(f"Baseline personnelle ({baseline.n} j) : VFC {baseline.vfc:.0f} ms · FCR {baseline.fcr:.0f} bpm")
                dv, df = vfc - baseline.vfc, fcr - baseline.fcr
                st.caption(f"Aujourd'hui : VFC {dv:+.0f} ms · FCR {df:+.0f} bpm vs baseline")
            else:
                st.caption(f"Normes de référence utilisées — la baseline personnelle s'active après 5 check-ins ({baseline.n}/5).")
            st.caption("💡 VFC ↓ + FCR ↑ = signal classique de fatigue du système nerveux autonome.")

    st.subheader("📍 Zones de douleur")
    with st.expander("Voir la carte du corps"):
        if BODY_MAP.exists():
            st.image(str(BODY_MAP), width=420)
    douleurs = st.multiselect("Zones tendues / douloureuses", MUSCLES, key="ck_douleurs", placeholder="Aucune")

    if st.button("✅ Valider mon check-in", type="primary", width="stretch"):
        w = st.session_state.get("garmin_wellness")
        from_garmin = w is not None and w.date == today and st.session_state.get("ck_source") == "Garmin"
        row = [
            today,
            float(sommeil),
            int(vfc),
            int(fcr),
            int(energie),
            ", ".join(douleurs) if douleurs else "Aucun",
            state.age(),
            w.body_battery if from_garmin and w.body_battery is not None else "",
            w.score_sommeil if from_garmin and w.score_sommeil is not None else "",
            st.session_state.get("ck_source", "Manuel"),
        ]
        try:
            state.append(schema.CHECKIN, [row])
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur lors de la sauvegarde : {exc}")
        else:
            st.success(f"Check-in enregistré — Readiness {r.score}%.")
            if r.status == "red":
                st.warning("Récupération faible : le Coach IA adaptera ta séance.")
