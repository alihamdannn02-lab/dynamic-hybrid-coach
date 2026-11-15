"""Page 4 — Coach IA & Programme : planification manuelle et génération IA."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from ... import schema
from ...ai import SessionContext, must_recover
from ...readiness import readiness_from_history
from ...training_load import acwr_status, daily_load, performance_manager, sessions_from_history
from .. import state

OBJECTIFS = [
    "Course : Sortie longue (Z2)",
    "Course : Fractionné / VMA",
    "Vélo : PMA / Seuil",
    "Vélo : Endurance fondamentale",
    "Natation : Technique & aérobie",
    "Trail : Renforcement spécifique (D+)",
    "Renforcement : Force maximale",
    "PPG : Core stability & prévention",
    "Cross-Training / Hyrox",
]


def _programme_rows(df: pd.DataFrame, semaine: int, jour: str, type_seance: str, source: str) -> list[list]:
    rows = []
    for _, r in df.iterrows():
        nom = str(r.get("Exercice", "")).strip()
        if not nom or nom == "nan":
            continue
        try:
            series = max(1, int(float(r.get("Séries") or 1)))
        except (TypeError, ValueError):
            series = 1
        try:
            poids = float(str(r.get("Charge (kg)", r.get("Poids (kg)", 0)) or 0).replace(",", "."))
        except (TypeError, ValueError):
            poids = 0.0
        rows.append([int(semaine), jour, type_seance, nom, series, str(r.get("Reps", "")), poids, "", source])
    return rows


def _planner() -> None:
    prog = state.load(schema.PROGRAMME)
    seances = list(dict.fromkeys(prog["Type_Seance"].dropna())) if not prog.empty else []
    exos = sorted(set(prog["Exercice_WOD"].dropna())) if not prog.empty else []

    with st.container(border=True):
        st.markdown("#### 1️⃣ Contexte")
        c1, c2, c3 = st.columns(3)
        semaine = c1.number_input("Semaine cible", min_value=1, step=1, value=state.current_week())
        jour = c2.selectbox("Jour", schema.JOURS)
        choix = c3.selectbox("Séance", ["➕ Nouvelle séance"] + seances)
        type_seance = st.text_input("Nom de la nouvelle séance") if choix == "➕ Nouvelle séance" else choix

    if not type_seance:
        return

    template = prog[(prog["Semaine"] == semaine - 1) & (prog["Type_Seance"] == type_seance)] if not prog.empty else prog
    st.markdown("#### 2️⃣ Contenu")
    if not template.empty:
        st.caption(f"Pré-rempli depuis la semaine {semaine - 1} : ajuste les charges (surcharge progressive) puis valide.")
        base = template[["Exercice_WOD", "Series_Cible", "Reps_Cible", "Poids_Cible_Kg"]].rename(
            columns={"Exercice_WOD": "Exercice", "Series_Cible": "Séries", "Reps_Cible": "Reps", "Poids_Cible_Kg": "Charge (kg)"}
        )
    else:
        base = pd.DataFrame([{"Exercice": exos[0] if exos else "", "Séries": 3, "Reps": "8", "Charge (kg)": 0.0}])
    base = base.reset_index(drop=True)
    base["Reps"] = base["Reps"].astype(str)

    edited = st.data_editor(
        base,
        num_rows="dynamic",
        hide_index=True,
        width="stretch",
        column_config={
            "Exercice": st.column_config.TextColumn("Exercice / bloc", required=True),
            "Séries": st.column_config.NumberColumn(min_value=1, step=1),
            "Reps": st.column_config.TextColumn("Reps / durée", help="ex : 8, 45 s, 20 min Z2"),
            "Charge (kg)": st.column_config.NumberColumn(min_value=0.0, step=0.5, format="%.1f"),
        },
        key=f"editor_{semaine}_{type_seance}",
    )
    if st.button("➕ Ajouter au programme", type="primary", width="stretch"):
        rows = _programme_rows(edited, semaine, jour, type_seance, "Manuel")
        if not rows:
            st.error("Ajoute au moins un exercice.")
        else:
            try:
                state.append(schema.PROGRAMME, rows)
            except Exception as exc:  # noqa: BLE001
                st.error(f"Erreur : {exc}")
            else:
                st.success(f"{len(rows)} mouvement(s) ajouté(s) au {jour} de la semaine {semaine}.")

    if not prog.empty:
        with st.expander(f"📅 Programme de la semaine {semaine}"):
            week = prog[prog["Semaine"] == semaine]
            if week.empty:
                st.caption("Rien de planifié pour l'instant.")
            else:
                week = week.assign(_o=week["Jour"].map({j: i for i, j in enumerate(schema.JOURS)})).sort_values("_o")
                st.dataframe(week[["Jour", "Type_Seance", "Exercice_WOD", "Series_Cible", "Reps_Cible", "Poids_Cible_Kg"]], hide_index=True, width="stretch")


def _context_defaults() -> dict:
    ck = state.load(schema.CHECKIN)
    out = {"sommeil": 7.0, "energie": 7, "douleurs": "Aucune", "readiness": None}
    if not ck.empty:
        last = ck.sort_values("Date").iloc[-1]
        out["sommeil"] = float(min(12.0, last["Heures_Sommeil"])) if pd.notna(last["Heures_Sommeil"]) else 7.0
        out["energie"] = int(last["Niveau_Energie"]) if pd.notna(last["Niveau_Energie"]) else 7
        out["douleurs"] = str(last["Muscles_Douloureux"] or "Aucune")
        r = readiness_from_history(ck)
        out["readiness"] = r.score if r else None
    realise = state.load(schema.REALISE)
    out["tsb"] = out["acwr"] = None
    out["recent"] = ""
    if not realise.empty:
        sessions = sessions_from_history(realise)
        daily = daily_load(sessions)
        pmc = performance_manager(daily)
        if len(pmc) >= 7:
            out["tsb"] = float(pmc.TSB.iloc[-1])
        out["acwr"] = acwr_status(daily).acwr
        recent = sessions[sessions["Sport_Discipline"] != "Repos"].tail(5)
        out["recent"] = "; ".join(f"{d:%d/%m} {t} ({int(m)} min, RPE {int(r)})" for d, t, m, r in zip(recent["Date"], recent["Type_Seance"], recent["Duree"], recent["Session_RPE"]))
    a = state.analytics()
    out["risk"] = a.risk.score if not a.risk.timeline.empty else None
    out["risk_drivers"] = ", ".join(f.name.lower() for f in a.risk.drivers)
    out["sleep_debt"] = a.sleep_summary.debt_h
    return out


def _generator() -> None:
    coach = state.coach()
    if not coach.enabled:
        st.info("🔌 `GEMINI_API_KEY` non configurée : le coach utilise sa bibliothèque de séances basée sur des règles physiologiques.")

    c1, c2 = st.columns(2)
    semaine = c1.number_input("Pour la semaine n°", min_value=1, step=1, value=state.current_week(), key="ia_sem")
    jour = c2.selectbox("Le jour", schema.JOURS, key="ia_jour")

    d = _context_defaults()
    w = st.session_state.get("garmin_wellness")
    with st.container(border=True):
        st.caption("Pré-rempli avec ton dernier check-in et ta charge d'entraînement.")
        a, b = st.columns(2)
        sommeil = a.number_input("Sommeil (h)", 0.0, 12.0, d["sommeil"], 0.5)
        energie = a.slider("Énergie (1-10)", 1, 10, d["energie"])
        douleurs = b.text_input("Douleurs / courbatures", d["douleurs"])
        objectif = b.selectbox("Séance souhaitée", OBJECTIFS)
        indicators = []
        if d["readiness"] is not None:
            indicators.append(f"Readiness **{d['readiness']}%**")
        if d["tsb"] is not None:
            indicators.append(f"TSB **{d['tsb']:+.0f}**")
        if d["acwr"] is not None:
            indicators.append(f"ACWR **{d['acwr']:.2f}**")
        if d["risk"] is not None:
            indicators.append(f"Risque blessure **{d['risk']}/100**")
        if d["sleep_debt"] is not None:
            indicators.append(f"Dette de sommeil **{d['sleep_debt']:.1f} h**")
        if w is not None and w.vfc_status:
            indicators.append(f"VFC Garmin **{w.vfc_status.title()}**")
        if indicators:
            st.markdown(" · ".join(indicators))

    ctx = SessionContext(
        sommeil=sommeil,
        energie=energie,
        douleurs=douleurs,
        objectif=objectif,
        readiness=d["readiness"],
        tsb=d["tsb"],
        acwr=d["acwr"],
        vfc_status=w.vfc_status if w else None,
        body_battery=w.body_battery if w else None,
        recent=d["recent"],
        risk=d["risk"],
        risk_drivers=d["risk_drivers"],
        sleep_debt=d["sleep_debt"],
    )
    if must_recover(ctx):
        st.warning("⚠️ Tes indicateurs imposent une séance de récupération, quel que soit l'objectif choisi.")

    if st.button("✨ Générer ma séance sur mesure", type="primary", width="stretch"):
        with st.spinner("Le coach analyse ta physiologie…"):
            seance, source = coach.generate_session(ctx)
        st.session_state["seance_ia"] = seance
        st.session_state["seance_ia_source"] = source
        if source == "règles" and coach.enabled and coach.last_error:
            st.caption(f"IA indisponible ({coach.last_error[:120]}…) — séance générée par règles.")

    seance = st.session_state.get("seance_ia")
    if not seance:
        return
    st.divider()
    st.markdown(f"### 🎯 {seance['titre']}")
    st.info(f"🗣️ {seance['message']}")
    df = pd.DataFrame(seance["exercices"])
    edited = st.data_editor(df, hide_index=True, width="stretch", num_rows="dynamic", key="ia_editor")
    st.caption(f"Source : {'Gemini' if st.session_state.get('seance_ia_source') == 'ia' else 'règles physiologiques'} · destination : {jour}, semaine {semaine}.")
    c1, c2 = st.columns(2)
    if c1.button("✅ Ajouter au programme", width="stretch"):
        rows = _programme_rows(edited, semaine, jour, seance["titre"], "IA")
        try:
            state.append(schema.PROGRAMME, rows)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur : {exc}")
        else:
            st.session_state["seance_ia"] = None
            st.success("Séance ajoutée au programme !")
            st.balloons()
    if c2.button("🔄 Propose-moi autre chose", width="stretch"):
        st.session_state["seance_ia"] = None
        st.rerun()


def render() -> None:
    st.title("🧠 Coach IA & Programme")
    tab_ia, tab_plan = st.tabs(["🤖 Génération IA", "📝 Planificateur"])
    with tab_ia:
        _generator()
    with tab_plan:
        _planner()
