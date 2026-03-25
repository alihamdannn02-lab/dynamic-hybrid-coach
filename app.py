import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# ---- CONFIG ----
st.set_page_config(
    page_title="Dynamic Hybrid Coach",
    page_icon="",
    layout="wide"
)

# ---- HEADER ----
st.title("Dynamic Hybrid Coach")
st.subheader("Ton coach personnel : Entrainement Hybride")
st.divider()

# ---- SIDEBAR ----
st.sidebar.title("Navigation")
page = st.sidebar.radio("", [
    "Check-in Matinal",
    "Ma Seance du Jour",
    "Mes Stats"
])

# ---- PAGE 1 : CHECK-IN MATINAL ----
if page == "Check-in Matinal":
    st.header("Check-in Matinal")
    st.write("Comment tu te sens ce matin ?")

    col1, col2, col3 = st.columns(3)

    with col1:
        sommeil = st.slider("Heures de sommeil", 0.0, 12.0, 7.0, 0.5)
    with col2:
        vfc = st.slider("VFC (manuellement)", 20, 100, 55)
    with col3:
        energie = st.slider("Niveau d'energie (1-10)", 1, 10, 7)

    st.divider()
    st.subheader("Muscles douloureux aujourd'hui ?")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        ischios = st.checkbox("Ischios")
        quadriceps = st.checkbox("Quadriceps")
    with col2:
        lombaires = st.checkbox("Lombaires")
        epaules = st.checkbox("Epaules")
    with col3:
        pectoraux = st.checkbox("Pectoraux")
        biceps = st.checkbox("Biceps")
    with col4:
        triceps = st.checkbox("Triceps")
        mollets = st.checkbox("Mollets")

    muscles_douloureux = []
    if ischios: muscles_douloureux.append("Ischios")
    if quadriceps: muscles_douloureux.append("Quadriceps")
    if lombaires: muscles_douloureux.append("Lombaires")
    if epaules: muscles_douloureux.append("Epaules")
    if pectoraux: muscles_douloureux.append("Pectoraux")
    if biceps: muscles_douloureux.append("Biceps")
    if triceps: muscles_douloureux.append("Triceps")
    if mollets: muscles_douloureux.append("Mollets")

    st.divider()

    if st.button("Valider mon Check-in", type="primary"):
        st.session_state['checkin'] = {
            'sommeil': sommeil,
            'vfc': vfc,
            'energie': energie,
            'muscles_douloureux': muscles_douloureux,
            'date': datetime.now().strftime('%Y-%m-%d')
        }

        if sommeil < 6 or vfc < 45 or energie < 4:
            st.warning("Ton niveau de recuperation est faible. L'IA va adapter ta séance.")
        else:
            st.success("Check-in enregistre. Tu es en forme pour t'entrainer.")

        if muscles_douloureux:
            st.info(f"Muscles douloureux detectes : {', '.join(muscles_douloureux)}")

# ---- PAGE 2 : SEANCE DU JOUR ----
elif page == "Ma Seance du Jour":
    st.header("Ma Seance du Jour")
    st.write("Selectionne ta seance et enregistre tes performances.")

    type_seance = st.selectbox("Type de seance", [
        "Upper_Body_1",
        "Lower_Body",
        "Calisthenics_Grip",
        "Hybrid_Conditioning",
        "Upper_Body_2",
        "Endurance",
        "Repos"
    ])

    st.divider()

    if type_seance in ["Upper_Body_1", "Lower_Body", "Calisthenics_Grip", "Upper_Body_2"]:
        st.subheader("Saisie Musculation")

        exercice = st.text_input("Exercice")
        col1, col2, col3 = st.columns(3)
        with col1:
            poids = st.number_input("Poids reel (kg)", min_value=0.0, step=0.5)
        with col2:
            reps = st.number_input("Repetitions", min_value=0, step=1)
        with col3:
            rir = st.selectbox("RIR (reps en reserve)", [0, 1, 2, 3, 4])

        rpe = 10 - rir
        st.metric("RPE calcule automatiquement", f"{rpe} / 10")

    elif type_seance == "Hybrid_Conditioning":
        st.subheader("Saisie WOD / Hyrox")

        format_seance = st.radio("Format", ["Solo", "Duo", "Team"])
        tags = st.multiselect("Mouvements effectues", [
            "Rameur", "SkiErg", "BikeErg", "Sled Push", "Sled Pull",
            "Burpees", "Wall Balls", "Farmers Carry", "Course",
            "Sandbag", "Box Jump", "Double Unders"
        ])
        pace = st.text_input("Pace / Watts moyens (optionnel)", placeholder="ex: 1:55 /500m ou 220W")

    elif type_seance == "Endurance":
        st.subheader("Saisie Course / Cardio")
        duree = st.number_input("Duree (minutes)", min_value=0, step=5)
        pace = st.text_input("Allure moyenne", placeholder="ex: 5:30 min/km")

    st.divider()
    session_rpe = st.slider("Session RPE — Note globale de la seance (1-10)", 1, 10, 7)

    if st.button("Enregistrer la seance", type="primary"):
        st.success("Seance enregistree avec succes.")
        st.balloons()

# ---- PAGE 3 : STATS ----
elif page == "Mes Stats":
    st.header("Mes Stats")
    st.info("Le dashboard PowerBI sera connecte ici. En attendant, voici un apercu.")

    data_demo = {
        'Semaine': [1, 2, 3, 4, 5],
        'Session_RPE_Moyen': [7.2, 7.8, 6.9, 8.1, 7.5],
        'Sommeil_Moyen': [7.1, 6.8, 7.5, 6.2, 7.3],
        'VFC_Moyen': [55, 52, 58, 48, 56]
    }
    df_demo = pd.DataFrame(data_demo)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("RPE Moyen (semaine)", "7.5", "+0.3")
    with col2:
        st.metric("Sommeil Moyen", "7.2h", "-0.3h")
    with col3:
        st.metric("VFC Moyen", "55 ms", "+3ms")

    st.divider()
    st.subheader("Tendance RPE vs Sommeil")
    st.line_chart(df_demo.set_index('Semaine')[['Session_RPE_Moyen', 'Sommeil_Moyen']])
