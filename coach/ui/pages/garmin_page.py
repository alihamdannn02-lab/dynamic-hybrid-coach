"""Page 5 — Garmin Connect : connexion, récupération et import des activités."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from ... import schema
from ...garmin import GarminError, activity_to_row
from ...training_load import estimate_tss
from .. import state


def _login_form() -> None:
    garmin = state.garmin()
    err = st.session_state.pop("garmin_autologin_error", None)
    if err:
        st.warning(f"Connexion automatique échouée : {err}")

    if garmin.awaiting_mfa:
        with st.form("garmin_mfa"):
            st.markdown("#### 🔐 Vérification en deux étapes")
            st.caption("Garmin vient de t'envoyer un code (e-mail ou SMS).")
            code = st.text_input("Code de vérification", max_chars=8)
            ok = st.form_submit_button("Valider", type="primary")
        if ok and code:
            try:
                garmin.submit_mfa(code)
            except GarminError as exc:
                st.error(str(exc))
            else:
                st.rerun()
        return

    with st.form("garmin_login"):
        st.markdown("#### Connexion à Garmin Connect")
        email = st.text_input("E-mail Garmin")
        password = st.text_input("Mot de passe", type="password")
        is_cn = st.checkbox("Compte Garmin Chine (garmin.cn)")
        ok = st.form_submit_button("Se connecter", type="primary")
    st.caption(
        "🔒 Ton mot de passe n'est ni stocké ni journalisé : il sert uniquement à obtenir un jeton de session, "
        "conservé dans la mémoire de ton navigateur. Garmin ne propose pas d'API publique aux particuliers ; "
        "l'application utilise le même protocole que l'app mobile Garmin Connect."
    )
    if ok:
        if not email or not password:
            st.error("E-mail et mot de passe requis.")
            return
        with st.spinner("Connexion à Garmin…"):
            try:
                garmin.login(email, password, is_cn=is_cn)
            except GarminError as exc:
                st.error(str(exc))
                return
        st.rerun()


def _wellness() -> None:
    garmin = state.garmin()
    st.subheader("💤 Récupération")
    c1, c2 = st.columns([2, 1], vertical_alignment="bottom")
    day = c1.date_input("Nuit du", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
    if c2.button("Actualiser", width="stretch"):
        with st.spinner("Lecture…"):
            try:
                st.session_state["garmin_wellness"] = garmin.fetch_wellness(day)
            except GarminError as exc:
                st.error(str(exc))
    w = st.session_state.get("garmin_wellness")
    if not w:
        st.caption("Clique sur « Actualiser » pour récupérer sommeil, VFC, FC repos et Body Battery.")
        return
    m = st.columns(3)
    m[0].metric("Sommeil", f"{w.sommeil_h} h" if w.sommeil_h else "—", f"Score {w.score_sommeil}" if w.score_sommeil else None, delta_color="off")
    m[1].metric("VFC (nuit)", f"{w.vfc} ms" if w.vfc else "—", f"{w.vfc_status.title()} · 7 j {w.vfc_hebdo} ms" if w.vfc_status and w.vfc_hebdo else None, delta_color="off")
    m[2].metric("FC repos", f"{w.fcr} bpm" if w.fcr else "—")
    m = st.columns(3)
    m[0].metric("Body Battery", w.body_battery if w.body_battery is not None else "—")
    m[1].metric("Training Readiness", w.training_readiness if w.training_readiness is not None else "—", (w.training_readiness_level or "").title() or None, delta_color="off")
    m[2].metric("Stress moyen", w.stress if w.stress is not None else "—")
    if w.errors:
        st.caption("Indisponible : " + ", ".join(w.errors))
    if w.has_data and w.date == date.today().isoformat() and st.button("➡️ Utiliser pour mon check-in du jour"):
        for key, val, cast in (("ck_sommeil", w.sommeil_h, float), ("ck_fcr", w.fcr, int), ("ck_vfc", w.vfc, int), ("ck_energie", w.energie_suggeree, int)):
            if val is not None:
                st.session_state[key] = cast(val)
        st.session_state["ck_source"] = "Garmin"
        st.switch_page(st.session_state["_pages"]["readiness"])


def _activities() -> None:
    garmin = state.garmin()
    st.subheader("🏃 Activités")
    c1, c2, c3 = st.columns([1, 1, 1], vertical_alignment="bottom")
    start = c1.date_input("Du", value=date.today() - timedelta(days=7), format="DD/MM/YYYY")
    end = c2.date_input("Au", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
    if c3.button("🔄 Charger", width="stretch"):
        with st.spinner("Récupération des activités…"):
            try:
                st.session_state["garmin_activities"] = garmin.fetch_activities(start, end)
            except GarminError as exc:
                st.error(str(exc))
                return

    acts = st.session_state.get("garmin_activities")
    if acts is None:
        st.caption("Charge tes activités pour les importer dans ton historique (zones cardiaques, D+, allure, RPE inclus).")
        return
    if not acts:
        st.info("Aucune activité sur cette période.")
        return

    already = state.imported_activity_ids()
    table = pd.DataFrame(
        [
            {
                "Importer": a.activity_id not in already,
                "Date": a.start.strftime("%d/%m %H:%M"),
                "Activité": a.name,
                "Sport": a.sport,
                "Durée (min)": a.duration_min,
                "Km": a.distance_km,
                "D+": a.elevation_m,
                "FC moy": a.avg_hr,
                "RPE": a.rpe,
                "TSS est.": round(estimate_tss(a.duration_min, a.rpe or 5)),
                "Statut": "✅ déjà importée" if a.activity_id in already else "nouvelle",
            }
            for a in acts
        ]
    )
    edited = st.data_editor(
        table,
        hide_index=True,
        width="stretch",
        disabled=[c for c in table.columns if c not in ("Importer", "RPE")],
        column_config={
            "Importer": st.column_config.CheckboxColumn(),
            "RPE": st.column_config.NumberColumn(min_value=1, max_value=10, step=0.5, help="Estimé depuis Garmin (auto-évaluation ou zones FC). Modifiable."),
        },
        key="garmin_import_editor",
    )
    semaine = st.number_input("Semaine du programme à associer", min_value=1, step=1, value=state.current_week())
    selected = [(a, row) for a, (_, row) in zip(acts, edited.iterrows()) if row["Importer"] and a.activity_id not in already]
    if st.button(f"📥 Importer {len(selected)} activité(s)", type="primary", disabled=not selected, width="stretch"):
        rows = []
        for a, row in selected:
            if pd.notna(row["RPE"]):
                a.rpe = float(row["RPE"])
            rows.append(activity_to_row(a, semaine))
        try:
            state.append(schema.REALISE, rows)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur d'écriture : {exc}")
        else:
            st.success(f"{len(rows)} activité(s) importée(s) : elles alimentent maintenant le Cockpit Performance.")
            st.rerun()


def _session_tools() -> None:
    garmin = state.garmin()
    with st.expander("⚙️ Session & déploiement"):
        st.markdown(
            "Pour te reconnecter automatiquement (et éviter le MFA à chaque démarrage, notamment sur Streamlit Cloud), "
            "copie ce jeton dans tes secrets sous la clé `GARMIN_TOKENS`. **Il donne accès à ton compte Garmin : "
            "ne le partage jamais et ne le commite pas.**"
        )
        if st.toggle("Afficher le jeton de session"):
            st.code(garmin.tokens() or "", language="json")
        if st.button("Se déconnecter de Garmin"):
            garmin.logout()
            for k in ("garmin_wellness", "garmin_activities"):
                st.session_state.pop(k, None)
            st.rerun()


def render() -> None:
    st.title("⌚ Garmin Connect")
    garmin = state.garmin()
    if not garmin.connected:
        _login_form()
        return
    st.success(f"Connecté à Garmin Connect — {garmin.display_name}")
    _wellness()
    st.divider()
    _activities()
    st.divider()
    _session_tools()
