"""Page 2 — Ma Séance du Jour : saisie de la séance réalisée."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from ... import schema
from ...training_load import estimate_tss, hr_zones
from .. import state

KW_CARDIO = ["course", "run", "fractionné", "piste", "endurance", "z1", "z2", "aérobie", "vo2", "vma", "pma", "seuil", "liss", "capacité", "vélo", "natation", "trail", "sortie longue", "intervalle"]
KW_WOD = ["hyrox", "wod", "circuit", "conditioning", "boxing", "boxe", "emom", "amrap"]
KW_REST = ["repos", "rest", "recovery", "récupération", "off"]


def classify(type_seance: str) -> str:
    t = str(type_seance).lower()
    if any(k in t for k in KW_REST):
        return "repos"
    if any(k in t for k in KW_WOD):
        return "wod"
    if any(k in t for k in KW_CARDIO):
        return "cardio"
    return "force"


def last_performance(realise: pd.DataFrame, type_seance: str) -> dict[str, dict]:
    """Charges/reps de la dernière occurrence de cette séance (pour le pré-remplissage)."""
    if realise.empty:
        return {}
    df = realise[realise["Type_Seance"] == type_seance]
    if df.empty:
        return {}
    df = df[df["Date"] == df["Date"].max()]
    out: dict[str, dict] = {}
    for _, row in df.iterrows():
        base = str(row["Exercice"]).split(" (Série")[0]
        out.setdefault(base, {"poids": _f(row["Poids_Reel_Kg"]), "reps": int(_f(row["Reps_Reelles"])), "rir": int(_f(row["RIR"]))})
    return out


def _f(value) -> float:
    """Nombre sûr (NaN / vide → 0)."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if v != v else v


def _series(value) -> int:
    return max(1, int(_f(value)))


def _digits(value) -> int:
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    return int(digits[:3]) if digits else 0


def _rpe_block(default: int = 6) -> int:
    st.markdown("##### 🧠 Effort perçu de la séance (RPE de Borg CR-10)")
    rpe = st.slider("RPE", 1, 10, default, label_visibility="collapsed")
    st.caption("1-2 très facile · 3-4 facile · 5-6 modéré (Z2) · 7-8 difficile (seuil) · 9-10 maximal")
    return rpe


def _zones_inputs(duree: int) -> list[int]:
    st.markdown("##### ❤️ Temps par zone cardiaque (min)")
    zones = hr_zones(state.fc_max())
    cols = st.columns(5)
    values = []
    for i, (col, z) in enumerate(zip(cols, zones), start=1):
        with col:
            name = z["zone"].split(" · ")
            st.markdown(f"<div class='zone-title' style='color:{z['color']}'>{name[0]}</div><span class='zone-sub'>{name[1]}<br>{z['min']}-{z['max']} bpm</span>", unsafe_allow_html=True)
            values.append(st.number_input(f"z{i}", min_value=0, step=1, label_visibility="collapsed", key=f"z{i}"))
    total = sum(values)
    color = "#58D68D" if total == duree else "#8B949E"
    st.markdown(f"<div style='text-align:right; color:{color}; font-size:0.85em'>Total : {total} / {duree} min</div>", unsafe_allow_html=True)
    return values


def render() -> None:
    st.title("🏃 Ma Séance du Jour")
    programme = state.load(schema.PROGRAMME)
    if programme.empty:
        st.info("Ton programme est vide. Crée des séances dans **Coach IA & Programme** (ou charge les données de démo depuis la barre latérale).")
        return

    weeks = sorted(int(w) for w in programme["Semaine"].dropna().unique())
    c1, c2, c3 = st.columns([1, 1, 1])
    semaine = c1.selectbox("Semaine du programme", weeks, index=len(weeks) - 1)
    jour_reel = c2.selectbox("📅 Réalisée le", schema.JOURS, index=date.today().weekday())
    date_seance = c3.date_input("Date", value=date.today(), format="DD/MM/YYYY")

    semaine_df = programme[programme["Semaine"] == semaine]
    options = list(dict.fromkeys(semaine_df["Type_Seance"].dropna()))
    jour_prevu = semaine_df[semaine_df["Jour"] == jour_reel]["Type_Seance"]
    default_idx = options.index(jour_prevu.iloc[0]) if not jour_prevu.empty and jour_prevu.iloc[0] in options else 0
    type_seance = st.selectbox("🎯 Quelle séance as-tu faite ?", options, index=default_idx)
    seance_df = semaine_df[semaine_df["Type_Seance"] == type_seance]
    kind = classify(type_seance)
    dstr = date_seance.isoformat()
    base = [dstr, int(semaine), jour_reel, str(type_seance)]
    rows: list[list] = []

    st.divider()
    if kind == "repos":
        st.success("🧘 Journée de récupération : mobilité, marche, sommeil. Les adaptations se construisent aujourd'hui.")
        fatigue = st.slider("Fatigue générale (1 = en pleine forme, 10 = épuisé)", 1, 10, 3)
        rows = [base + ["Repos", 0, 0, 0, 0, fatigue, 0, 0, 0, 0, 0, 0, 0, "Repos", 0, ""]]
        label = "Valider ma journée de repos"

    elif kind == "cardio":
        st.info("🏃🚴🏊 Séance d'endurance")
        sport = st.selectbox("Discipline", ["Course à pied", "Cyclisme", "Natation", "Trail / Ski Alpinisme"])
        with st.expander("📋 Plan théorique", expanded=True):
            for _, r in seance_df.iterrows():
                st.markdown(f"- **{r['Exercice_WOD']}** — cible : {r['Reps_Cible']}")
        m1, m2, m3 = st.columns(3)
        distance = m1.number_input("Distance (km)", min_value=0.0, step=0.1, value=10.0)
        duree = m2.number_input("Durée (min)", min_value=0, step=1, value=60)
        dplus = m3.number_input("Dénivelé (m D+)", min_value=0, step=50, value=0)
        allure = st.text_input("Allure moyenne ou puissance", placeholder="ex : 5:30 min/km ou 220 W")
        zones = _zones_inputs(int(duree))
        rpe = _rpe_block(6)
        rows = [base + ["Bilan Endurance", 0, 0, 0, 0, rpe, distance, duree, *zones, sport, dplus, allure]]
        st.caption(f"Charge estimée : **{estimate_tss(duree, rpe):.0f} TSS**")
        label = "💾 Enregistrer ma séance"

    elif kind == "wod":
        st.info("🔥 Séance métabolique (Cross-Training / Hyrox)")
        m1, m2 = st.columns(2)
        duree = m1.number_input("Durée totale (min)", min_value=0, step=1, value=45)
        fmt = m2.selectbox("Format", ["Solo", "Duo", "Team"])
        photo = st.file_uploader("📸 Photo du tableau de la box (optionnel)", type=["png", "jpg", "jpeg", "webp"])
        coach = state.coach()
        if photo is not None and st.session_state.get("wod_photo_id") != photo.file_id:
            st.session_state["wod_photo_id"] = photo.file_id
            if coach.enabled:
                with st.spinner("Lecture du tableau par l'IA…"):
                    text = coach.read_wod_image(photo.getvalue(), photo.type or "image/jpeg")
                if text:
                    st.session_state["wod_text"] = text
                else:
                    st.warning("Lecture impossible, saisis le WOD à la main.")
            else:
                st.caption("Configure `GEMINI_API_KEY` pour la lecture automatique du tableau.")
        wod = st.text_area("Contenu du WOD", key="wod_text", placeholder="For Time : 1000 m Run / 50 Wall Balls / …")
        rpe = _rpe_block(8)
        titre = f"Bilan WOD | Format:{fmt}" + (f" | {wod.replace(chr(10), ' / ')}" if wod.strip() else "")
        rows = [base + [titre, 0, 0, 0, 0, rpe, 0, duree, 0, 0, 0, 0, 0, "Cross-Training", 0, ""]]
        st.caption(f"Charge estimée : **{estimate_tss(duree, rpe):.0f} TSS**")
        label = "💾 Enregistrer ma séance"

    else:
        st.markdown("##### 🏋️ Préparation Physique Générale")
        realise = state.load(schema.REALISE)
        last = last_performance(realise, str(type_seance))
        prefill = st.toggle("📋 Pré-remplir avec mes dernières charges", value=bool(last), disabled=not last)
        exercises = []
        for idx, r in seance_df.iterrows():
            nom = str(r["Exercice_WOD"])
            n = _series(r["Series_Cible"])
            key = f"{idx}_{nom.replace(' ', '_')}"
            prev = last.get(nom)
            poids0 = prev["poids"] if prefill and prev else _f(r["Poids_Cible_Kg"])
            reps0 = prev["reps"] if prefill and prev else _digits(r["Reps_Cible"])
            with st.expander(f"⚙️ {nom} — {n} × {r['Reps_Cible']}", expanded=True):
                if prev:
                    msg = f"Dernière fois : **{prev['poids']} kg × {prev['reps']}** (RIR {prev['rir']})"
                    if prev["rir"] >= 2 and prev["poids"] > 0:
                        msg += f" → 📈 surcharge progressive conseillée : **+{max(0.5, round(prev['poids'] * 0.025 * 2) / 2):g} kg**"
                    elif prev["rir"] == 0:
                        msg += " → ⚖️ échec atteint : stabilise la charge"
                    st.markdown(msg)
                h = st.columns([1, 2, 2, 2])
                for col, title in zip(h, ["Série", "Charge (kg)", "Reps", "RIR"]):
                    col.caption(title)
                for s in range(1, n + 1):
                    c = st.columns([1, 2, 2, 2])
                    c[0].markdown(f"**#{s}**")
                    p = c[1].number_input("Poids", min_value=0.0, step=0.5, value=float(poids0), key=f"p_{key}_{s}_{prefill}", label_visibility="collapsed")
                    rp = c[2].number_input("Reps", min_value=0, step=1, value=int(reps0), key=f"r_{key}_{s}_{prefill}", label_visibility="collapsed")
                    rir = c[3].selectbox("RIR", [0, 1, 2, 3, 4], index=2, key=f"rir_{key}_{s}", label_visibility="collapsed")
                    exercises.append((nom, s, p, rp, rir))
        duree = st.number_input("⏱️ Durée totale (min)", min_value=0, step=1, value=50)
        rpe = _rpe_block(7)
        rows = [base + [f"{nom} (Série {s})", p, rp, rir, 10 - rir, rpe, 0, duree, 0, 0, 0, 0, 0, "Renforcement / PPG", 0, ""] for nom, s, p, rp, rir in exercises]
        tonnage = sum(p * rp for _, _, p, rp, _ in exercises)
        st.caption(f"Tonnage : **{tonnage:,.0f} kg** · Charge estimée : **{estimate_tss(duree, rpe):.0f} TSS**".replace(",", " "))
        label = "💾 Enregistrer ma séance"

    st.write("")
    if st.button(label, type="primary", width="stretch"):
        try:
            state.append(schema.REALISE, rows)
        except Exception as exc:  # noqa: BLE001
            st.error(f"Erreur d'écriture : {exc}")
        else:
            st.success(f"Séance enregistrée ({len(rows)} ligne{'s' if len(rows) > 1 else ''}).")
            st.balloons()
