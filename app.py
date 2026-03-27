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
    st.write("Clique sur les zones musculaires précises où tu ressens des courbatures.")

    # INITIALISATION DES MÉMOIRES (Session State)
    if 'muscles_selectionnes' not in st.session_state:
        st.session_state['muscles_selectionnes'] = []
    # Mémoire de sécurité pour éviter le bug de l'effacement
    if 'dernier_clic' not in st.session_state:
        st.session_state['dernier_clic'] = None

    # AFFICHAGE DE L'IMAGE (Largeur augmentée à 600 pour plus de confort)
    # Important : on utilise une nouvelle 'key' pour reset le composant
    value = streamlit_image_coordinates("body_map.png", width=600, key="body_map_v2")

    muscle_identifie = None

    if value is not None:
        coords_actuelles = (value['x'], value['y'])
        
        # SÉCURITÉ : On ne traite le clic que s'il est NOUVEAU
        if coords_actuelles != st.session_state['dernier_clic']:
            # On enregistre ce clic comme étant le dernier traité
            st.session_state['dernier_clic'] = coords_actuelles
            x, y = coords_actuelles
            
            # Ce texte te permet de calibrer, ne l'enlève pas tout de suite !
            st.caption(f"📍 Clic détecté : X={x}, Y={y}")

            # --- DÉBUT DE LA CALIBRATION ULTRA-DÉTAILLÉE ---
            #⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️
            # TOUS LES CHIFFRES CI-DESSOUS SONT DES EXEMPLES (basés sur width=600)
            # TU DOIS LES REMPLACER PAR TES VRAIES COORDONNÉES !
            #⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️⚠️
            
            # --- STRUCTURE DE LA LOGIQUE ---
            # Pour width=600, la face avant est approx (x < 300) et la face arrière (x > 300)
            
            # --- FACE AVANT (approx x < 300) ---
            if x < 300:
                if y < 50: muscle_identifie = "Cou / Trapèzes sup"
                elif 50 < y < 80:
                    if (80 < x < 130) or (170 < x < 220): muscle_identifie = "Épaules (Shoulders)"
                    elif 130 < x < 170: muscle_identifie = "Pectoraux (Haut)"
                elif 80 < y < 120:
                    if 130 < x < 170: muscle_identifie = "Pectoraux (Bas)"
                elif 120 < y < 180:
                    if 130 < x < 170: muscle_identifie = "Abdominaux"
                    elif (100 < x < 130) or (170 < x < 200): muscle_identifie = "Obliques"
                elif 180 < y < 220:
                    if 120 < x < 180: muscle_identifie = "Quadriceps (Haut)"
                elif 220 < y < 280:
                    if 120 < x < 180: muscle_identifie = "Quadriceps (Bas)"
                
                # --- BRAS FACE ---
                elif (30 < x < 80) or (220 < x < 270):
                    if 80 < y < 130: muscle_identifie = "Biceps"
                    elif 130 < y < 190: muscle_identifie = "Avant-bras (Face)"
            
            # --- FACE ARRIÈRE (approx x > 300) ---
            else: 
                if y < 60: muscle_identifie = "Haut du dos (Trapèzes)"
                elif 60 < y < 100:
                    if 430 < x < 470: muscle_identifie = "Milieu du dos"
                    elif (380 < x < 430) or (470 < x < 520): muscle_identifie = "Épaules (Postérieur)"
                elif 100 < y < 150:
                    if 410 < x < 490: muscle_identifie = "Grands Dorsaux (Lats)"
                elif 150 < y < 190:
                    if 430 < x < 470: muscle_identifie = "Bas du dos (Lombaires)"
                elif 190 < y < 230:
                    if 410 < x < 490: muscle_identifie = "Fessiers (Glutes)"
                elif 230 < y < 280:
                    if 410 < x < 490: muscle_identifie = "Ischios (Hamstrings)"
                elif 280 < y < 350:
                    if 420 < x < 480: muscle_identifie = "Mollets (Calves)"

                # --- BRAS DOS ---
                elif (330 < x < 380) or (520 < x < 570):
                    if 80 < y < 130: muscle_identifie = "Triceps"
                    elif 130 < y < 190: muscle_identifie = "Avant-bras (Dos)"

            # Si on a identifié un muscle, on l'ajoute à la liste s'il n'y est pas déjà
            if muscle_identifie and muscle_identifie not in st.session_state['muscles_selectionnes']:
                st.session_state['muscles_selectionnes'].append(muscle_identifie)
                st.toast(f"✅ {muscle_identifie} ajouté") # Notification discrète

    # RÉCUPÉRATION ET AFFICHAGE DE LA SÉLECTION
    muscles_douloureux = st.session_state['muscles_selectionnes']

    if muscles_douloureux:
        st.info(f"🩹 Muscles ciblés : {', '.join(muscles_douloureux)}")
        if st.button("🗑️ Effacer la sélection musculaires"):
            st.session_state['muscles_selectionnes'] = []
            st.session_state['dernier_clic'] = None # IMPORTANT : On reset la sécurité aussi
            st.rerun()
    else:
        st.caption("Aucun muscle sélectionné.")

    st.divider()

    # LE BOUTON VALIDER RESTE ICI
    if st.button("Valider mon Check-in", type="primary"):
        date_du_jour = datetime.now().strftime("%Y-%m-%d")
        muscles_str = ", ".join(muscles_douloureux) if muscles_douloureux else "Aucun"
        
        nouvelle_ligne_checkin = [
            date_du_jour, float(sommeil), int(vfc), int(energie), str(muscles_str)
        ]

        try:
            save_checkin(nouvelle_ligne_checkin)
            st.success("✅ Check-in enregistré dans la base de données ! Tu es prêt pour ta journée.")
            st.balloons()
            
            if sommeil < 6 or vfc < 45 or energie < 4:
                st.warning("⚠️ Ton niveau de récupération est faible. L'IA va adapter ta séance.")
            
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
