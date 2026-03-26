import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from streamlit_image_coordinates import streamlit_image_coordinates

# ---- CONFIG ----
st.set_page_config(
    page_title="Dynamic Hybrid Coach",
    page_icon="",
    layout="wide"
)

# ---- CONNEXION GOOGLE SHEETS ----

@st.cache_resource
def connect_sheets():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    
    # 1. On récupère les secrets en tant que dictionnaire modifiable
    credentials_dict = dict(st.secrets["gcp_service_account"])
    
    # 2. LA LIGNE MAGIQUE : on remplace les faux retours à la ligne par de vrais retours à la ligne
    credentials_dict["private_key"] = credentials_dict["private_key"].replace("\\n", "\n")
    
    # 3. On crée les "creds" avec le dictionnaire corrigé
    creds = Credentials.from_service_account_info(
        credentials_dict,
        scopes=scopes
    )
    
    client = gspread.authorize(creds)
    return client

@st.cache_data(ttl=300)
def load_programme():
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    worksheet = sheet.get_worksheet(0)
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

def save_performance(lignes_donnees):
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    # On cible le nouvel onglet qu'on vient de créer
    worksheet = sheet.worksheet("Historique_Realise")
    # On ajoute toutes les lignes d'un coup
    worksheet.append_rows(lignes_donnees)

def save_checkin(ligne_donnees):
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    worksheet = sheet.worksheet("Historique_Checkin")
    worksheet.append_row(ligne_donnees)
    
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
        energie = st.slider("Niveau d'energie", 1, 10, 7)
        st.caption("🔋 1-3: Épuisé | 4-6: Normal | 7-8: En forme | 9-10: Prêt à battre des records")

    st.divider()
    
    st.subheader("🗺️ Carte corporelle des douleurs")
    st.write("Clique sur les zones musculaires où tu ressens des courbatures.")

    # On affiche l'image et on écoute les clics
    value = streamlit_image_coordinates("body_map.png", width=350, key="body_map")

    # Initialisation de la mémoire pour accumuler les clics
    if 'muscles_selectionnes' not in st.session_state:
        st.session_state['muscles_selectionnes'] = []

    muscle_identifie = None

    if value is not None:
        x = value['x']
        y = value['y']
        
        # Ce petit texte est crucial pour TOI : c'est lui qui te donne les coordonnées
        st.caption(f"📍 Clic détecté : X={x}, Y={y}")

        # --- DÉBUT DE LA CALIBRATION ---
        # Tu devras ajuster ces chiffres en regardant les X et Y affichés !
        
        # --- FACE AVANT ---
        if 90 < x < 150 and 70 < y < 110:
            muscle_identifie = "Pectoraux"
        elif 90 < x < 150 and 110 < y < 160:
            muscle_identifie = "Abdominaux"
        elif 90 < x < 150 and 180 < y < 250:
            muscle_identifie = "Quadriceps"
        elif (40 < x < 80 or 160 < x < 200) and 120 < y < 170:
            muscle_identifie = "Bras (Face)"
        
        # --- FACE ARRIÈRE ---
        elif 220 < x < 280 and 70 < y < 160:
            muscle_identifie = "Dos"
        elif 220 < x < 280 and 180 < y < 250:
            muscle_identifie = "Ischios"
        elif 220 < x < 280 and 260 < y < 320:
            muscle_identifie = "Mollets"
        elif (190 < x < 220 or 280 < x < 310) and 120 < y < 170:
            muscle_identifie = "Bras (Dos)"

        # Si un muscle a été trouvé, on l'ajoute à la liste s'il n'y est pas déjà
        if muscle_identifie and muscle_identifie not in st.session_state['muscles_selectionnes']:
            st.session_state['muscles_selectionnes'].append(muscle_identifie)

    muscles_douloureux = st.session_state['muscles_selectionnes']

    if muscles_douloureux:
        st.info(f"🩹 Muscles ciblés : {', '.join(muscles_douloureux)}")
        if st.button("🗑️ Effacer la sélection"):
            st.session_state['muscles_selectionnes'] = []
            st.rerun()
    else:
        st.caption("Aucun muscle sélectionné.")

    st.divider()

    # LE BOUTON VALIDER QU'IL FALLAIT GARDER :
    if st.button("Valider mon Check-in", type="primary"):
        date_du_jour = datetime.now().strftime("%Y-%m-%d")
        muscles_str = ", ".join(muscles_douloureux) if muscles_douloureux else "Aucun"
        
        # On prépare la ligne propre pour Google Sheets
        nouvelle_ligne_checkin = [
            date_du_jour, 
            float(sommeil), 
            int(vfc), 
            int(energie), 
            str(muscles_str)
        ]

        try:
            # On envoie à Google Sheets
            save_checkin(nouvelle_ligne_checkin)
            st.success(" Check-in enregistré dans la base de données ! Tu es prêt pour ta journée.")
            
            if sommeil < 6 or vfc < 45 or energie < 4:
                st.warning(" Ton niveau de récupération est faible. L'IA va adapter ta séance.")
            
        except Exception as e:
            st.error(f"Erreur lors de la sauvegarde : {e}")
            
# ---- PAGE 2 : SEANCE DU JOUR ----
elif page == "Ma Seance du Jour":
    st.header("Ma Seance du Jour")

    try:
        df = load_programme()

        jour_options = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
        jour_actuel = datetime.now().strftime("%A")
        jours_fr = {"Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
                    "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"}
        jour_defaut = jours_fr.get(jour_actuel, "Lundi")

        col1, col2 = st.columns(2)
        with col1:
            semaine = st.selectbox("Semaine", sorted(df["Semaine"].unique()))
        with col2:
            jour = st.selectbox("Jour", jour_options, index=jour_options.index(jour_defaut))

        seance_df = df[(df["Semaine"] == semaine) & (df["Jour"] == jour)]

        if seance_df.empty:
            st.info("Aucune seance prevue ce jour.")
        else:
            type_seance = seance_df["Type_Seance"].iloc[0]
            st.subheader(f"Seance : {type_seance}")
            st.divider()

            for _, row in seance_df.iterrows():
                with st.expander(f"{row['Exercice_WOD']} — {row['Series_Cible']} series x {row['Reps_Cible']} reps @ {row['Poids_Cible_Kg']} kg"):
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        poids_reel = st.number_input(f"Poids reel (kg)", min_value=0.0, step=0.5, key=f"poids_{row['Exercice_WOD']}")
                    with col2:
                        reps_reelles = st.number_input(f"Reps reelles", min_value=0, step=1, key=f"reps_{row['Exercice_WOD']}")
                    with col3:
                        rir = st.selectbox(f"RIR", [0, 1, 2, 3, 4], key=f"rir_{row['Exercice_WOD']}")
                    rpe = 10 - rir
                    st.metric("RPE", f"{rpe} / 10")

            st.divider()
            session_rpe = st.slider("Note globale de la seance (1-10)", 1, 10, 7)

            if st.button("Enregistrer la seance", type="primary"):
                lignes_a_sauvegarder = []
                date_du_jour = datetime.now().strftime("%Y-%m-%d")

                for _, row in seance_df.iterrows():
                    exo = row['Exercice_WOD']
                    poids = st.session_state[f"poids_{exo}"]
                    reps = st.session_state[f"reps_{exo}"]
                    rir = st.session_state[f"rir_{exo}"]
                    rpe_serie = 10 - rir
                    
                    # On s'assure que TOUT est dans un format que Google Sheets comprend (int, float, ou str)
                    semaine_clean = int(semaine)
                    poids_clean = float(poids)
                    reps_clean = int(reps)
                    rir_clean = int(rir)
                    rpe_serie_clean = int(rpe_serie)
                    session_rpe_clean = int(session_rpe)
                    
                    nouvelle_ligne = [
                        date_du_jour, 
                        semaine_clean, 
                        str(jour), 
                        str(type_seance), 
                        str(exo), 
                        poids_clean, 
                        reps_clean, 
                        rir_clean, 
                        rpe_serie_clean, 
                        session_rpe_clean
                    ]
                    lignes_a_sauvegarder.append(nouvelle_ligne)
                
                save_performance(lignes_a_sauvegarder)
                st.success("✅ Boom ! Seance enregistree avec succes dans Google Sheets.")
                st.balloons()

    except Exception as e:
        st.error(f"Erreur de connexion au Google Sheets : {e}")

# ---- PAGE 3 : STATS ----
elif page == "Mes Stats":
    st.header("Mes Stats")

    try:
        df = load_programme()
        st.success(f"Google Sheets connecte — {len(df)} exercices charges.")

        data_demo = {
            'Semaine': [1, 2, 3, 4, 5],
            'Session_RPE_Moyen': [7.2, 7.8, 6.9, 8.1, 7.5],
            'Sommeil_Moyen': [7.1, 6.8, 7.5, 6.2, 7.3],
            'VFC_Moyen': [55, 52, 58, 48, 56]
        }
        df_demo = pd.DataFrame(data_demo)

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("RPE Moyen", "7.5", "+0.3")
        with col2:
            st.metric("Sommeil Moyen", "7.2h", "-0.3h")
        with col3:
            st.metric("VFC Moyen", "55 ms", "+3ms")

        st.divider()
        st.subheader("Tendance RPE vs Sommeil")
        st.line_chart(df_demo.set_index('Semaine')[['Session_RPE_Moyen', 'Sommeil_Moyen']])

    except Exception as e:
        st.error(f"Erreur de connexion au Google Sheets : {e}")
