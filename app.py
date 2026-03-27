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
    
    st.subheader("Carte corporelle des douleurs")
    
    # --- LA LÉGENDE POUR AIDER L'UTILISATEUR ---
    st.info("**Zones cliquables :**\n"
            "* **Face :** Cou, Épaules, Pecs (Haut/Bas), Biceps, Abdos, Quadriceps, Genoux.\n"
            "* **Dos :** Haut du dos, Bas du dos, Triceps, Fessiers, Ischios, Mollets.")

    # INITIALISATION DES MÉMOIRES
    if 'muscles_selectionnes' not in st.session_state:
        st.session_state['muscles_selectionnes'] = []
    if 'dernier_clic' not in st.session_state:
        st.session_state['dernier_clic'] = None
    # L'astuce magique pour forcer l'effacement de l'image :
    if 'map_key' not in st.session_state:
        st.session_state['map_key'] = 0

    # On ajoute la clé dynamique à l'image
    value = streamlit_image_coordinates("body_map.png", width=600, key=f"body_map_{st.session_state['map_key']}")

    muscle_identifie = None

    if value is not None:
        coords_actuelles = (value['x'], value['y'])
        
        if coords_actuelles != st.session_state['dernier_clic']:
            st.session_state['dernier_clic'] = coords_actuelles
            x, y = coords_actuelles
            
            # st.caption(f"📍 Clic détecté : X={x}, Y={y}") # Tu peux effacer cette ligne si tu n'en as plus besoin

            # --- TA CALIBRATION SUR MESURE ---
            if x < 300: # --- FACE AVANT ---
                if 120 < y < 165 and (60 < x < 100 or 190 < x < 240): muscle_identifie = "Épaules (Face)"
                elif 130 < y < 165 and 100 <= x <= 190: muscle_identifie = "Pectoraux (Haut)"
                elif 165 <= y < 195 and 100 <= x <= 190: muscle_identifie = "Pectoraux (Bas)"
                elif 180 < y < 240 and (55 < x < 95 or 195 < x < 235): muscle_identifie = "Biceps"
                elif 200 < y < 280 and 110 < x < 180: muscle_identifie = "Abdominaux"
                elif 280 <= y < 420 and 100 < x < 190: muscle_identifie = "Quadriceps" # Ajout logique entre abdos et genoux
                elif 430 < y < 490 and 95 < x < 195: muscle_identifie = "Genoux"

            else: # --- FACE ARRIÈRE ---
                if 80 < y < 125 and 410 < x < 480: muscle_identifie = "Cou / Trapèzes"
                elif 125 <= y < 195 and 400 < x < 490: muscle_identifie = "Haut du dos"
                elif 180 < y < 240 and (340 < x < 410 or 490 < x < 550): muscle_identifie = "Triceps"
                elif 195 <= y < 280 and 400 < x < 490: muscle_identifie = "Bas du dos (Lombaires)"
                elif 290 < y < 360 and 400 < x < 510: muscle_identifie = "Fessiers"
                elif 370 < y < 450 and 390 < x < 490: muscle_identifie = "Ischios (Hamstrings)"
                elif 470 < y < 540 and 390 < x < 490: muscle_identifie = "Mollets"

            if muscle_identifie and muscle_identifie not in st.session_state['muscles_selectionnes']:
                st.session_state['muscles_selectionnes'].append(muscle_identifie)

    muscles_douloureux = st.session_state['muscles_selectionnes']

    if muscles_douloureux:
        st.info(f"Muscles ciblés : {', '.join(muscles_douloureux)}")
        if st.button("🗑️ Effacer la sélection"):
            # LE CORRECTIF EST ICI
            st.session_state['muscles_selectionnes'] = []
            st.session_state['dernier_clic'] = None
            st.session_state['map_key'] += 1 # On change la clé de l'image !
            st.rerun()
    else:
        st.caption("Aucun muscle sélectionné.")

    st.divider()

    if st.button("Valider mon Check-in", type="primary"):
        date_du_jour = datetime.now().strftime("%Y-%m-%d")
        muscles_str = ", ".join(muscles_douloureux) if muscles_douloureux else "Aucun"
        
        nouvelle_ligne_checkin = [
            date_du_jour, float(sommeil), int(vfc), int(energie), str(muscles_str)
        ]

        try:
            save_checkin(nouvelle_ligne_checkin)
            st.success("Check-in enregistré dans la base de données ! Tu es prêt pour ta journée.")
            st.balloons()
            
            if sommeil < 6 or vfc < 45 or energie < 4:
                st.warning("Ton niveau de récupération est faible. L'IA va adapter ta séance.")
            
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
            st.info("Aucune seance prevue ce jour. Repose-toi bien !")
        else:
            type_seance = seance_df["Type_Seance"].iloc[0]
            st.subheader(f"Seance : {type_seance}")
            st.divider()

            # --- LE CERVEAU DE L'APP : 3 MODES ---
            type_seance_lower = str(type_seance).lower()
            
            mots_cles_course = ["course", "run", "fractionné", "piste", "endurance", "z2"]
            mots_cles_wod = ["hyrox", "wod", "circuit", "conditioning"]
            
            est_une_course = any(mot in type_seance_lower for mot in mots_cles_course)
            est_un_wod = any(mot in type_seance_lower for mot in mots_cles_wod)

            if est_une_course:
                # ---------------------------------------------------------
                # MODE 1 : COURSE À PIED (Longue ou Fractionné)
                # ---------------------------------------------------------
                st.info("🏃‍♂️ Séance de course détectée !")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    distance = st.number_input("Distance (km)", min_value=0.0, step=0.1, value=5.0)
                with col2:
                    duree_run = st.number_input("Durée totale (min)", min_value=0, step=1, value=30)
                with col3:
                    fc_moyenne = st.number_input("FC Moyenne (bpm)", min_value=40, max_value=220, step=1, value=140)
                
                details_course = st.text_input("Détails (ex: 4x1000m, ou 20min Z2 + 10min Z4)", placeholder="Tes temps de passage ou zones...")
                
                st.divider()
                session_rpe = st.slider("Note globale de la seance (1-10)", 1, 10, 7)

                if st.button("Enregistrer la Course", type="primary"):
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")
                    # Ruse : Poids = Distance, Reps = Durée, RIR = FC
                    ligne_run = [
                        date_du_jour, int(semaine), str(jour), str(type_seance), 
                        f"Run: {details_course}", # Exercice
                        float(distance), # Poids (détourné)
                        int(duree_run), # Reps (détourné)
                        int(fc_moyenne), # RIR (détourné)
                        0, # RPE Serie
                        int(session_rpe)
                    ]
                    try:
                        save_performance([ligne_run])
                        st.success(f"✅ Course enregistrée : {distance} km dans la besace !")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

            elif est_un_wod:
                # ---------------------------------------------------------
                # MODE 2 : WOD & HYROX
                # ---------------------------------------------------------
                st.info("🔥 Séance métabolique détectée !")
                
                col1, col2 = st.columns(2)
                with col1:
                    duree_wod = st.number_input("Durée totale (en minutes)", min_value=0, step=1, value=45)
                with col2:
                    format_wod = st.selectbox("Format de la séance", ["Solo", "Duo", "Team"])
                
                score_wod = st.text_input("Score ou Résumé (ex: 4 tours + 15 reps, ou temps final)")
                
                st.write("📸 Scanner le tableau de la Box")
                photo_tableau = st.file_uploader("Upload la photo du WOD", type=['png', 'jpg', 'jpeg'])
                if photo_tableau is not None:
                    st.success("Image chargée ! (L'analyse IA OCR arrivera dans la prochaine version)")

                st.divider()
                session_rpe = st.slider("Note globale de la seance (1-10)", 1, 10, 8)

                if st.button("Enregistrer le WOD", type="primary"):
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")
                    ligne_wod = [
                        date_du_jour, int(semaine), str(jour), str(type_seance), 
                        f"Format {format_wod} - {score_wod}", 
                        0.0, int(duree_wod), 0, 0, int(session_rpe)
                    ]
                    try:
                        save_performance([ligne_wod])
                        st.success("✅ Boom ! WOD enregistré avec succès.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

            else:
                # ---------------------------------------------------------
                # MODE 3 : MUSCULATION CLASSIQUE
                # ---------------------------------------------------------
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

                if st.button("Enregistrer la seance muscu", type="primary"):
                    lignes_a_sauvegarder = []
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")

                    for _, row in seance_df.iterrows():
                        exo = row['Exercice_WOD']
                        poids = st.session_state[f"poids_{exo}"]
                        reps = st.session_state[f"reps_{exo}"]
                        rir = st.session_state[f"rir_{exo}"]
                        rpe_serie = 10 - rir
                        
                        nouvelle_ligne = [
                            date_du_jour, int(semaine), str(jour), str(type_seance), str(exo), 
                            float(poids), int(reps), int(rir), int(rpe_serie), int(session_rpe)
                        ]
                        lignes_a_sauvegarder.append(nouvelle_ligne)
                    
                    try:
                        save_performance(lignes_a_sauvegarder)
                        st.success("✅ Boom ! Séance de force enregistrée avec succès.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    except Exception as e:
        st.error(f"Erreur de connexion au programme : {e}")

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
