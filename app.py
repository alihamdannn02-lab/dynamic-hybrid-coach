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

def save_nouveau_programme(ligne_donnees):
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    
    # ⚠️ IMPORTANT : J'ai mis "Programme_Base" ici. 
    # Si ton onglet Google Sheets s'appelle juste "Programme" ou autre chose, 
    # n'oublie pas de changer le nom exact entre les guillemets !
    worksheet = sheet.worksheet("Programme_Base")
    
    # On utilise append_row (sans "s" à la fin) car on envoie une seule ligne à la fois
    worksheet.append_row(ligne_donnees)
    
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
    "Mes Stats", 
    "Créateur de Programme"
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
        st.caption(" 1-3: Épuisé | 4-6: Normal | 7-8: En forme | 9-10: Prêt à battre des records")

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
            
            # st.caption(f"📍Clic détecté : X={x}, Y={y}") # Tu peux effacer cette ligne si tu n'en as plus besoin

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

    # --- INJECTION DE CSS POUR LE DESIGN DES ZONES CARDIAQUES ---
    st.markdown("""
        <style>
        .z1-titre { color: #5dade2; text-align: center; font-weight: bold; margin-bottom: 0px;}
        .z2-titre { color: #58d68d; text-align: center; font-weight: bold; margin-bottom: 0px;}
        .z3-titre { color: #f4d03f; text-align: center; font-weight: bold; margin-bottom: 0px;}
        .z4-titre { color: #e67e22; text-align: center; font-weight: bold; margin-bottom: 0px;}
        .z5-titre { color: #e74c3c; text-align: center; font-weight: bold; margin-bottom: 0px;}
        .fcmax { font-size: 0.8em; color: gray; text-align: center; display: block; margin-bottom: 10px;}
        </style>
    """, unsafe_allow_html=True)

    try:
        df = load_programme()

        # --- SÉLECTION DE LA SÉANCE ---
        semaine = st.selectbox("Semaine", sorted(df["Semaine"].unique()))
        seances_semaine = df[df["Semaine"] == semaine]
        options_seances = seances_semaine['Type_Seance'].unique()
        choix_seance = st.selectbox("Quelle séance veux-tu faire ?", options_seances)
        
        seance_df = seances_semaine[seances_semaine["Type_Seance"] == choix_seance]
        jour_theorique = seance_df["Jour"].iloc[0]
        seance_df = seance_df[seance_df["Jour"] == jour_theorique]

        # --- VRAI JOUR POUR LA SAUVEGARDE ---
        jour_actuel_en = datetime.now().strftime("%A")
        jours_fr = {"Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi",
                    "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"}
        vrai_jour_actuel = jours_fr.get(jour_actuel_en, "Lundi")

        if seance_df.empty:
            st.info("Aucune séance trouvée.")
        else:
            type_seance = seance_df["Type_Seance"].iloc[0]
            st.subheader(f"Détails : {type_seance}")
            st.divider()

            type_seance_lower = str(type_seance).lower()
            mots_cles_course = ["course", "run", "fractionné", "piste", "endurance", "z2"]
            mots_cles_wod = ["hyrox", "wod", "circuit", "conditioning"]
            
            est_une_course = any(mot in type_seance_lower for mot in mots_cles_course)
            est_un_wod = any(mot in type_seance_lower for mot in mots_cles_wod)

            if est_une_course or est_un_wod:
                # --- INTERFACE COMMUNE HYROX ET COURSE ---
                if est_une_course:
                    st.info(" Séance de course détectée !")
                    col1, col2 = st.columns(2)
                    with col1: distance = st.number_input("Distance (km)", min_value=0.0, step=0.1, value=5.0)
                    with col2: duree_totale = st.number_input("Durée totale (min)", min_value=0, step=1, value=30)
                else:
                    st.info("Séance métabolique détectée !")
                    col1, col2 = st.columns(2)
                    with col1: duree_totale = st.number_input("Durée totale (min)", min_value=0, step=1, value=45)
                    with col2: format_wod = st.selectbox("Format", ["Solo", "Duo", "Team"])
                    distance = 0.0 # Pas de distance stricte pour le WOD global

                # --- LE BEAU DESIGN DES ZONES CARDIAQUES ---
                st.write(" **Zones de fréquence cardiaque**")
                st.caption("Minutes passées dans chaque zone. Le total devrait correspondre à la durée de ta séance.")
                
                cz1, cz2, cz3, cz4, cz5 = st.columns(5)
                with cz1:
                    st.markdown("<div class='z1-titre'>Z1</div><span class='fcmax'>50-60%</span>", unsafe_allow_html=True)
                    z1 = st.number_input("z1", 0, step=1, label_visibility="collapsed", key="z1")
                with cz2:
                    st.markdown("<div class='z2-titre'>Z2</div><span class='fcmax'>60-70%</span>", unsafe_allow_html=True)
                    z2 = st.number_input("z2", 0, step=1, label_visibility="collapsed", key="z2")
                with cz3:
                    st.markdown("<div class='z3-titre'>Z3</div><span class='fcmax'>70-80%</span>", unsafe_allow_html=True)
                    z3 = st.number_input("z3", 0, step=1, label_visibility="collapsed", key="z3")
                with cz4:
                    st.markdown("<div class='z4-titre'>Z4</div><span class='fcmax'>80-90%</span>", unsafe_allow_html=True)
                    z4 = st.number_input("z4", 0, step=1, label_visibility="collapsed", key="z4")
                with cz5:
                    st.markdown("<div class='z5-titre'>Z5</div><span class='fcmax'>90-100%</span>", unsafe_allow_html=True)
                    z5 = st.number_input("z5", 0, step=1, label_visibility="collapsed", key="z5")
                
                # Calculateur en temps réel
                total_zones = z1 + z2 + z3 + z4 + z5
                st.markdown(f"<div style='text-align: right; color: gray; margin-top: 10px;'>Total : {total_zones} min</div>", unsafe_allow_html=True)
                
                if total_zones > duree_totale:
                    st.warning("⚠️ Attention : La somme de tes zones est supérieure à la durée totale de la séance !")

                # --- ZONE SPÉCIFIQUE WOD (Photo) ---
                texte_wod_decode = ""
                if est_un_wod:
                    st.write("📸 Scanner le tableau de la Box")
                    photo_tableau = st.file_uploader("Upload la photo du WOD", type=['png', 'jpg', 'jpeg'])
                    if photo_tableau is not None:
                        st.success(" Image chargée !")
                        texte_wod_decode = st.text_area("Exercices détectés par l'IA (corrige si besoin) :", value="1000m Run\n50 Wall Balls\n1000m Row...")

                st.divider()
                session_rpe = st.slider("Note globale de la séance (RPE)", 1, 10, 7)
                st.caption("1-2: Très facile | 3-4: Facile | 5-6: Modéré | 7-8: Difficile | 9: Très difficile | 10: Effort maximal")

                # --- BOUTON DE SAUVEGARDE COMMUN COURSE/WOD ---
                if st.button("Enregistrer la séance", type="primary"):
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")
                    
                    # LOGIQUE SÉPARÉE POUR LA COLONNE "EXERCICE"
                    if est_une_course:
                        details_exo = "Course"
                    else:
                        if texte_wod_decode:
                            details_exo = f"{format_wod} - {texte_wod_decode.replace('\n', ' / ')}"
                        else:
                            details_exo = f"{format_wod}"

                    # LA LIGNE AVEC LES 7 NOUVELLES COLONNES À LA FIN
                    ligne_sauvegarde = [
                        date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), details_exo, 
                        0.0, 0, 0, 0, int(session_rpe), # Les 5 colonnes muscu mises à 0
                        float(distance), int(duree_totale), int(z1), int(z2), int(z3), int(z4), int(z5) # Les 7 colonnes Cardio
                    ]
                    
                    try:
                        save_performance([ligne_sauvegarde])
                        st.success(f"Séance enregistrée pour ce {vrai_jour_actuel} !")
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
                            poids_reel = st.number_input(f"Poids réel (kg)", min_value=0.0, step=0.5, key=f"poids_{row['Exercice_WOD']}")
                        with col2:
                            reps_reelles = st.number_input(f"Reps réelles", min_value=0, step=1, key=f"reps_{row['Exercice_WOD']}")
                        with col3:
                            rir = st.selectbox(f"RIR", [0, 1, 2, 3, 4], key=f"rir_{row['Exercice_WOD']}")
                        rpe = 10 - rir
                        st.metric("RPE", f"{rpe} / 10")

                st.divider()
                session_rpe = st.slider("Note globale de la séance (RPE)", 1, 10, 7)
                st.caption("🔥 1-2: Très facile | 3-4: Facile | 5-6: Modéré | 7-8: Difficile | 9: Très difficile | 10: Effort maximal")

                if st.button("Enregistrer la séance muscu", type="primary"):
                    lignes_a_sauvegarder = []
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")

                    for _, row in seance_df.iterrows():
                        exo = row['Exercice_WOD']
                        poids = st.session_state[f"poids_{exo}"]
                        reps = st.session_state[f"reps_{exo}"]
                        rir = st.session_state[f"rir_{exo}"]
                        rpe_serie = 10 - rir
                        
                        # POUR LA MUSCU, ON MET LES 7 NOUVELLES COLONNES À ZÉRO POUR GARDER LE TABLEAU ALIGNÉ
                        nouvelle_ligne = [
                            date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), str(exo), 
                            float(poids), int(reps), int(rir), int(rpe_serie), int(session_rpe),
                            0.0, 0, 0, 0, 0, 0, 0 # Distance, Durée, Z1..Z5
                        ]
                        lignes_a_sauvegarder.append(nouvelle_ligne)
                    
                    try:
                        save_performance(lignes_a_sauvegarder)
                        st.success(f"✅ Séance de force enregistrée avec succès pour ce {vrai_jour_actuel}.")
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

# ---- PAGE 4 : CRÉATEUR DE PROGRAMME ----
elif page == "Créateur de Programme":
    st.header("🛠️ Gestion du Programme")
    
    tab1, tab2 = st.tabs(["✍️ Saisie Rapide (Historique)", "🤖 Génération par l'IA"])

    # ---------------------------------------------------------
    # ONGLET 1 : SAISIE INTELLIGENTE BASÉE SUR TON HISTORIQUE
    # ---------------------------------------------------------
    with tab1:
        st.write("Ajoute un exercice ou une séance complète dans ton programme.")
        
        try:
            df = load_programme()
            liste_seances = df["Type_Seance"].dropna().unique().tolist()
            liste_exos = df["Exercice_WOD"].dropna().unique().tolist()
        except:
            liste_seances = []
            liste_exos = []

        options_seances = ["-- Nouvelle séance --"] + liste_seances
        options_exos = ["-- Nouvel exercice --"] + liste_exos

        # LIGNE 1 : Le contexte (Semaine, Jour, Nom de la séance)
        col1, col2, col3 = st.columns(3)
        with col1:
            semaine = st.number_input("Semaine n°", min_value=1, step=1, value=1)
        with col2:
            jour = st.selectbox("Jour théorique", ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"])
        with col3:
            choix_seance = st.selectbox("Nom de la séance", options_seances)
            if choix_seance == "-- Nouvelle séance --":
                type_seance = st.text_input("📝 Nom (ex: Upper Body, Hyrox, Course)")
            else:
                type_seance = choix_seance

        st.divider()

        # --- LE CERVEAU DYNAMIQUE ---
        # On vérifie en temps réel si tu as tapé un mot clé Cardio/Hyrox
        type_seance_lower = str(type_seance).lower() if type_seance else ""
        mots_cles_cardio_wod = ["hyrox", "wod", "circuit", "conditioning", "boxing", "boxe", "course", "run", "fractionné", "piste", "endurance", "z2"]
        est_cardio_wod = any(mot in type_seance_lower for mot in mots_cles_cardio_wod)

        # LIGNE 2 : Les détails (qui s'adaptent selon la séance)
        if est_cardio_wod:
            # INTERFACE HYROX / COURSE
            st.info("🔥 Séance métabolique / Cardio détectée ! L'interface s'adapte.")
            col_a, col_b = st.columns(2)
            with col_a:
                exercice = st.text_input("Détails / Format", value="WOD Global", help="Ex: Course 5km, WOD Solo, Sac de frappe...")
            with col_b:
                duree = st.number_input("Durée totale estimée (min)", min_value=1, step=1, value=45)
            
            # On force les valeurs "muscu" à 0 pour garder le Google Sheets propre
            series = 0
            reps = f"{duree} min"
            poids = 0.0
            
        else:
            # INTERFACE MUSCU CLASSIQUE
            st.info("🏋️‍♂️ Séance de Musculation détectée.")
            choix_exo = st.selectbox("Exercice", options_exos)
            if choix_exo == "-- Nouvel exercice --":
                exercice = st.text_input("📝 Nom du NOUVEL exercice (ex: Développé couché)")
            else:
                exercice = choix_exo

            col_a, col_b, col_c = st.columns(3)
            with col_a:
                series = st.number_input("Séries cibles", min_value=1, step=1, value=4)
            with col_b:
                reps = st.text_input("Reps", value="10")
            with col_c:
                poids = st.number_input("Poids cible (kg)", min_value=0.0, step=0.5, value=0.0)

        # BOUTON DE SAUVEGARDE
        if st.button("➕ Ajouter au Programme (Google Sheets)", type="primary"):
            if not type_seance or not exercice:
                st.error("⚠️ Le nom de la séance et de l'exercice sont obligatoires.")
            else:
                nouvelle_ligne_prog = [
                    int(semaine), str(jour), str(type_seance), 
                    str(exercice), int(series), str(reps), float(poids)
                ]
                try:
                    save_nouveau_programme(nouvelle_ligne_prog) 
                    st.success(f"✅ Ajouté avec succès à ta semaine {semaine} !")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erreur de connexion : {e}")

    # ---------------------------------------------------------
    # ONGLET 2 : LE COACH IA (Préparation)
    # ---------------------------------------------------------
    with tab2:
        st.subheader("🧠 Générateur de Séance IA")
        st.info("L'IA va bientôt pouvoir analyser ton Check-in Matinal, croiser ça avec tes anciens exercices, et te pondre la séance hybride parfaite pour aujourd'hui.")
        
        objectif_ia = st.selectbox("Quel est l'objectif du jour ?", ["Gérer la fatigue (Active Recovery)", "Exploser les chronos (Conditioning)", "Force pure (Hypertrophie/Force)"])
        
        if st.button("✨ Générer ma séance", type="primary"):
            st.success("Connexion à l'IA en cours d'installation...")
            st.write("### 🤖 Proposition de l'IA (Simulation) :")
            st.write("**Type :** Hybrid Conditioning")
            st.write("**Échauffement :** 10 min Z1 + Mobilité")
            st.write("**WOD (AMRAP 15 min) :**")
            st.write("- 400m Run")
            st.write("- 15 Kettlebell Swings")
            st.write("- 10 Burpees")
