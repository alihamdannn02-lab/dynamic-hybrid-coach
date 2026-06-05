import streamlit as st
import pandas as pd
import numpy as np
import json
import re
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from streamlit_image_coordinates import streamlit_image_coordinates
import google.generativeai as genai
import plotly.express as px
import plotly.graph_objects as go
from datetime import timedelta
from plotly.subplots import make_subplots


# --- CONFIGURATION DE L'IA GEMINI ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    
    # Astuce de pro : On demande à Google quels modèles sont dispos pour ta clé !
    model_id = None
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            model_id = m.name
            if 'flash' in m.name: # On préfère la version Flash (plus rapide) si elle est dispo
                break
                
    if model_id:
        modele_ia = genai.GenerativeModel(model_id)
    else:
        st.warning("⚠️ Aucun modèle compatible trouvé pour cette clé API.")
        
except Exception as e:
    st.warning(f"⚠️ Débogage IA - Voici l'erreur exacte : {e}")
    
# ---- CONFIG ----
st.set_page_config(
    page_title="Enduraw - Daily Readiness",
    page_icon="⚡", # L'éclair fait plus "énergie/performance" que l'haltère
    layout="centered" # "centered" est BEAUCOUP mieux pour simuler une vue Mobile !
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
    worksheet = sheet.worksheet("Programme_Theorique") 
    data = worksheet.get_all_records()
    return pd.DataFrame(data)

@st.cache_data(ttl=300)
def load_historique_realise():
    try:
        client = connect_sheets()
        sheet = client.open("DB_Dynamic_Hybrid_Coach")
        worksheet = sheet.worksheet("Historique_Realise")
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=300)
def load_historique_checkin():
    try:
        client = connect_sheets()
        sheet = client.open("DB_Dynamic_Hybrid_Coach")
        worksheet = sheet.worksheet("Historique_Checkin")
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()
def save_nouveau_programme(ligne_donnees):
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    worksheet = sheet.worksheet("Programme_Theorique")
    worksheet.append_row(ligne_donnees)
    
def save_checkin(ligne_donnees):
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    worksheet = sheet.worksheet("Historique_Checkin")
    worksheet.append_row(ligne_donnees)

def save_performance(lignes_donnees):
    client = connect_sheets()
    sheet = client.open("DB_Dynamic_Hybrid_Coach")
    # On cible l'onglet où tu enregistres tes vraies performances
    worksheet = sheet.worksheet("Historique_Realise")
    # On utilise append_rows avec un "s" car on envoie parfois plusieurs lignes d'un coup (muscu)
    worksheet.append_rows(lignes_donnees)

def delete_last_session():
    try:
        client = connect_sheets()
        sheet = client.open("DB_Dynamic_Hybrid_Coach")
        worksheet = sheet.worksheet("Historique_Realise")
        
        # On récupère toutes les valeurs
        all_values = worksheet.get_all_values()
        
        if len(all_values) <= 1: # S'il n'y a que l'en-tête
            return False, "L'historique est déjà vide."

        # On identifie la date de la toute dernière ligne
        last_date = all_values[-1][0]
        
        # On compte combien de lignes ont cette même date à la fin du tableau
        count = 0
        for row in reversed(all_values):
            if row[0] == last_date:
                count += 1
            else:
                break
        
        # On calcule les indices des lignes à supprimer
        total_rows = len(all_values)
        start_row = total_rows - count + 1
        
        # Suppression dans Google Sheet
        worksheet.delete_rows(start_row, total_rows)
        return True, f"La séance du {last_date} ({count} lignes) a été annulée."
    except Exception as e:
        return False, f"Erreur : {e}"
        
def generer_seance_ia(energie, sommeil, courbatures, objectif):
    # On force l'IA à répondre avec un format JSON strict
    prompt = f"""Tu es le moteur d'intelligence artificielle d'Enduraw, un expert d'élite en physiologie du sport et entraînement d'endurance (Triathlon, Trail, Cyclisme).
    Voici l'état actuel de l'athlète : Sommeil: {sommeil}h, Énergie: {energie}/10, Douleurs musculaires localisées: {courbatures}, Objectif de la séance: {objectif}.
    
    Règles physiologiques strictes :
    1. Si l'énergie est < 5 ou le sommeil < 6h, impose STRICTEMENT une séance de récupération active (Active Recovery) ou du cardio en Zone 1 / LISS à basse intensité.
    2. Si l'athlète signale des douleurs (ex: Mollets, Genoux), adapte la séance. S'il veut du cardio, privilégie le cyclisme fluide sans impact plutôt que la course à pied pour protéger les articulations.
    3. Si l'objectif est du "Renforcement", propose des mouvements de PPG spécifiques à l'endurance (ex: Squat excentrique, Soulevé de terre partiel, Mollets sur step, Gainage dynamique).

    Tu DOIS répondre STRICTEMENT au format JSON, sans fioritures, balises ou texte périphérique.
    Format attendu :
    {{
        "titre": "Nom scientifique de la séance (ex: Endurance Fondamentale Z2, Force sous-maximale PPG)",
        "message": "Ton analyse de physiologiste et ton mot d'encouragement par rapport à ses constantes du matin",
        "exercices": [
            {{"nom": "Mouvement ou Bloc cardio (ex: Ligne de course Z2 ou Fentes bulgares)", "series": 3, "reps": 10, "poids": 0}}
        ]
    }}
    """
    
    try:
        reponse = modele_ia.generate_content(prompt)
        texte = reponse.text
        
        # Nettoyage de la réponse (l'IA met parfois des balises ```json autour)
        texte_propre = re.sub(r"```json\n|\n```", "", texte).strip()
        if texte_propre.startswith("```"): 
            texte_propre = re.sub(r"```.*\n|\n```", "", texte_propre).strip()
        
        # Transformation du texte en véritable Dictionnaire Python
        donnees = json.loads(texte_propre)
        return True, donnees
    except Exception as e:
        return False, f"Erreur de formatage du cerveau IA : {e}"

def sauvegarder_seance_ia_programme(titre, df_exos, semaine, jour):
    try:
        client = connect_sheets()
        sheet = client.open("DB_Dynamic_Hybrid_Coach")
        worksheet = sheet.worksheet("Programme_Theorique")
        
        lignes_a_ajouter = []
        for idx, row in df_exos.iterrows():
            lignes_a_ajouter.append([
                int(semaine), 
                str(jour),    # <--- On utilise maintenant le vrai jour !
                str(titre), 
                str(row["Exercice"]),
                int(row["Séries"]),
                int(row["Reps"]),
                float(row["Poids (kg)"]),
                "", 
                "IA" 
            ])
            
        worksheet.append_rows(lignes_a_ajouter)
        return True
    except Exception as e:
        return False

def get_derniere_seance(type_seance_nom):
    try:
        df = load_historique_realise()
        if df.empty:
            return {}
        df_seance = df[df["Type_Seance"] == type_seance_nom].copy()
        if df_seance.empty:
            return {}
        derniere_date = df_seance["Date"].max()
        df_last = df_seance[df_seance["Date"] == derniere_date]
        resultats = {}
        for _, row in df_last.iterrows():
            nom_base = str(row["Exercice"]).split(" (Série")[0]
            if nom_base not in resultats:
                resultats[nom_base] = {
                    "poids": float(row["Poids_Reel_Kg"]) if row["Poids_Reel_Kg"] else 0.0,
                    "reps": int(row["Reps_Reelles"]) if row["Reps_Reelles"] else 0
                }
        return resultats
    except:
        return {}        
        
# --- SCRIPT DE CALCUL DU READINESS SCORE ---
def calculer_readiness(sommeil, vfc, fcr, energie):
    # 1. Score de Sommeil (Optimale autour de 8h)
    if 7.5 <= sommeil <= 9.0:
        score_sommeil = 100
    elif 6.0 <= sommeil < 7.5:
        score_sommeil = 75
    elif sommeil > 9.0:
        score_sommeil = 80
    else:
        score_sommeil = 40 # Moins de 6h
        
    # 2. Score d'Énergie subjective
    score_energie = energie * 10 # Énergie de 1 à 10 -> Score de 10 à 100
    
    # 3. Score Physiologique (Combo FCR / VFC)
    # On simule une déviation par rapport à des valeurs de base théoriques
    # FCR cible = 45bpm (plus elle monte, plus le score baisse)
    score_fcr = max(0, 100 - (abs(fcr - 45) * 4))
    # VFC cible = 60ms (plus elle baisse, plus le score baisse)
    score_vfc = min(100, max(0, (vfc / 60) * 100))
    
    # Moyenne pondérée (les datas physiologiques comptent plus que le ressenti !)
    readiness = (score_sommeil * 0.25) + (score_energie * 0.20) + (score_fcr * 0.30) + (score_vfc * 0.25)
    return round(readiness)
    
# ---- HEADER ----
st.title("⚡ Enduraw - Athlete System")
st.subheader("Optimisation de la performance & Suivi de récupération")
st.divider()

# --- NAVIGATION SIDEBAR AMÉLIORÉE ---
with st.sidebar:
    st.title("Enduraw Athlete")
    st.markdown("## ⚡ Profil & Suivi")
    st.divider()
    
    page = st.radio(
        "Menu Principal",
        ["Morning Readiness", "Ma Séance du Jour", "Mes Insights (Data)", "Coach IA (Analyse)"],
        index=0
    )
    
    st.divider()
    st.info("Version 3.0 - Intelligence Artificielle activée")

# --- OPTION DE CORRECTION RAPIDE ---
st.sidebar.divider()
st.sidebar.write("⚠️ **Correction**")
if st.sidebar.button("🗑️ Annuler ma dernière séance"):
    success, message = delete_last_session()
    if success:
        # On vide le cache pour que les graphiques se mettent à jour
        st.cache_data.clear()
        st.sidebar.success(message)
        st.balloons()
    else:
        st.sidebar.error(message)
        
# --- CONNECTIVITÉ (API STRAVA/GARMIN) ---
st.sidebar.divider()
st.sidebar.markdown("### ⌚ Connectivité")
if st.sidebar.button("🔄 Synchroniser Garmin / Strava"):
    with st.spinner("Recherche de nouvelles activités via l'API Webhook..."):
        import time
        time.sleep(2) # Simule l'appel réseau
    st.sidebar.success("✅ 1 nouvelle activité synchronisée (Vélo : 45km)")
    st.sidebar.caption("Les métriques (TSS, Watts, D+) ont été mises à jour.")
        
# ---- PAGE 1 : CHECK-IN MATIN ----
if page == "Morning Readiness":
    st.markdown("### 🎙️ L'Assistant Rapide (Zéro Friction)")
    st.write("Pas envie de régler les curseurs ? Dis-moi comment tu te sens, je m'occupe du reste.")
    
    texte_checkin = st.text_area("Ta nuit en une phrase :", placeholder="Ex: J'ai dormi 7h, ma FC est à 42, VFC 65, je suis en pleine forme mais j'ai mal aux mollets.")
    
    if st.button("🪄 Remplir automatiquement", type="secondary"):
        with st.spinner("Analyse de tes constantes..."):
            prompt_nlp = f"""Extrais les données physiologiques de ce texte : "{texte_checkin}". 
            Renvoie STRICTEMENT un JSON avec ces clés : sommeil (float), fcr (int), vfc (int), energie (int de 1 à 10). 
            Si une donnée manque, mets 0."""
            try:
                reponse = modele_ia.generate_content(prompt_nlp)
                data_ia = json.loads(reponse.text.replace('```json', '').replace('```', '').strip())
                # On met à jour la mémoire de la page
                st.session_state['sommeil_auto'] = float(data_ia.get('sommeil', 7.5))
                st.session_state['fcr_auto'] = int(data_ia.get('fcr', 45))
                st.session_state['vfc_auto'] = int(data_ia.get('vfc', 60))
                st.session_state['energie_auto'] = int(data_ia.get('energie', 7))
                st.success("Curseurs ajustés ! Vérifie et valide en bas.")
            except:
                st.error("L'IA n'a pas pu lire tes constantes, utilise les curseurs.")
    st.header("⚡ Morning Readiness")
    st.markdown("Exprime ton état du jour en **15 secondes chrono**.")
    st.divider()

    st.subheader("📊 Constantes Physiologiques")
    col1, col2 = st.columns(2)
    with col1:
        sommeil = st.slider("💤 Heures de sommeil", 0.0, 12.0, 7.5, 0.5)
        fcr = st.number_input("❤️ FC Repos (bpm)", min_value=30, max_value=100, value=45, step=1)
    with col2:
        energie = st.slider("🔋 Énergie perçue (1-10)", 1, 10, 7)
        vfc = st.number_input("📉 VFC (ms)", min_value=10, max_value=150, value=60, step=1)
        
    st.caption("💡 *Astuce : Une baisse de VFC couplée à une hausse de FCR indique souvent une fatigue nerveuse.*")

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
            date_du_jour, float(sommeil), int(vfc), int(fcr), int(energie), str(muscles_str)
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
elif page == "Ma Séance du Jour":
    st.header("Ma Séance du Jour")

    
            
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

        # --- NOUVEAUTÉ : CHOIX DU JOUR RÉEL ---
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            semaine = st.selectbox("Semaine", sorted(df["Semaine"].unique()))
        with col_s2:
            # On calcule quel jour on est aujourd'hui pour le mettre par défaut
            jours_liste = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]
            jour_actuel_en = datetime.now().strftime("%A")
            jours_fr = {"Monday": "Lundi", "Tuesday": "Mardi", "Wednesday": "Mercredi", "Thursday": "Jeudi", "Friday": "Vendredi", "Saturday": "Samedi", "Sunday": "Dimanche"}
            aujourdhui_fr = jours_fr.get(jour_actuel_en, "Lundi")
            index_aujourdhui = jours_liste.index(aujourdhui_fr) if aujourdhui_fr in jours_liste else 0
            
            # L'athlète peut maintenant choisir la date de son log !
            vrai_jour_actuel = st.selectbox("📅 Réalisé le :", jours_liste, index=index_aujourdhui)

        seances_semaine = df[df["Semaine"] == semaine]
        options_seances = seances_semaine['Type_Seance'].unique()
        choix_seance = st.selectbox("🎯 Quelle séance as-tu faite ?", options_seances)
        
        seance_df = seances_semaine[seances_semaine["Type_Seance"] == choix_seance]

        if seance_df.empty:
            st.info("Aucune séance trouvée.")
        else:
            type_seance = seance_df["Type_Seance"].iloc[0]
            st.subheader(f"Détails : {type_seance}")
            st.divider()

            # --- DÉTECTION DU MODE (CORRIGÉE POUR L'ENDURANCE ÉLITE) ---
            type_seance_lower = str(type_seance).lower()
            
            # On ajoute ici tous les termes physiologiques de notre base de données !
            mots_cles_course = ["course", "run", "fractionné", "piste", "endurance", "z2", "aérobie", "vo2", "seuil", "liss", "capacité", "vélo", "sortie longue"]
            mots_cles_wod = ["hyrox", "wod", "circuit", "conditioning", "boxing", "boxe"]
            mots_cles_repos = ["repos", "rest", "recovery", "récupération", "off"]
            
            est_une_course = any(mot in type_seance_lower for mot in mots_cles_course)
            est_un_wod = any(mot in type_seance_lower for mot in mots_cles_wod)
            est_un_repos = any(mot in type_seance_lower for mot in mots_cles_repos)

            # =========================================================
            # MODE 1 : JOUR DE REPOS (ÉCRAN ZEN)
            # =========================================================
            if est_un_repos:
                st.success("🧘‍♂️ Journée de récupération (Active Recovery) détectée !")
                st.write("Profite de cette journée pour recharger tes batteries. Fais de la mobilité si besoin.")
                st.divider()
                
                session_rpe = st.slider("Note ta fatigue générale aujourd'hui (1 = En pleine forme, 10 = Épuisé)", 1, 10, 3)

                if st.button("Valider ma journée de repos", type="primary"):
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")
                    # On envoie des 0 partout, sauf pour le RPE et le nom de la séance
                    ligne_repos = [
                        date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), "Repos", 
                        0.0, 0, 0, 0, int(session_rpe),
                        0.0, 0, 0, 0, 0, 0, 0 
                    ]
                    try:
                        save_performance([ligne_repos])
                        st.cache_data.clear()
                        st.success(f"✅ Repos validé pour ce {vrai_jour_actuel} ! Beau travail cette semaine.")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erreur : {e}")

            # =========================================================
            # MODE 2 & 3 : CARDIO OU MUSCULATION
            # =========================================================
            # =========================================================
            # MODE 2 & 3 : CARDIO SÉPARÉ DU RENFORCEMENT (PPG)
            # =========================================================
            else:
                distance, duree_totale, z1, z2, z3, z4, z5 = 0.0, 0, 0, 0, 0, 0, 0
                format_wod = "Solo"
                texte_wod_decode = ""

                # --- 🏃‍♂️ INTERFACE CARDIO ÉLITE (ZONES CARDIAQUES) ---
                if est_une_course:
                    st.info("🏃‍♂️🚴‍♂️🏊‍♂️ Séance Aérobie / Endurance détectée !")
                    
                    # Sélecteur Triathlon / Trail
                    sport_realise = st.selectbox("Discipline", ["Course à pied", "Cyclisme", "Natation", "Trail / Ski Alpinisme"])
                    
                    # Rappel dynamique du programme
                    st.markdown("##### 📋 Rappel du plan théorique :")
                    for _, row in seance_df.iterrows():
                        st.markdown(f"- **{row['Exercice_WOD']}** *(Cible : {row['Reps_Cible']})*")
                    st.write("")
                    
                    # Métriques d'Élite (Dénivelé, Watts, Allure)
                    st.markdown("##### 📊 Métriques de la séance")
                    col1, col2, col3 = st.columns(3)
                    with col1: 
                        distance = st.number_input("Distance (km)", min_value=0.0, step=0.1, value=10.0)
                    with col2: 
                        duree_totale = st.number_input("Durée (min)", min_value=0, step=1, value=60)
                    with col3:
                        denivele = st.number_input("Dénivelé (m D+)", min_value=0, step=50, value=0)
                    
                    allure_watts = st.text_input("Allure moyenne (ex: 5:30 min/km) ou Puissance (ex: 220W)", placeholder="Optionnel")

                    # Distribution de l'intensité (Zones 1 à 5)
                    st.markdown("##### ❤️ Distribution de l'Intensité (Minutes par Zone)")
                    st.caption("Renseigne le temps passé dans chaque zone d'après ton cardiofréquencemètre.")
                    
                    cz1, cz2, cz3, cz4, cz5 = st.columns(5)
                    with cz1:
                        st.markdown("<div class='z1-titre'>Z1</div><span class='fcmax'>Récup</span>", unsafe_allow_html=True)
                        z1 = st.number_input("z1", 0, step=1, label_visibility="collapsed", key="z1")
                    with cz2:
                        st.markdown("<div class='z2-titre'>Z2</div><span class='fcmax'>Endur.</span>", unsafe_allow_html=True)
                        z2 = st.number_input("z2", 0, step=1, label_visibility="collapsed", key="z2")
                    with cz3:
                        st.markdown("<div class='z3-titre'>Z3</div><span class='fcmax'>Tempo</span>", unsafe_allow_html=True)
                        z3 = st.number_input("z3", 0, step=1, label_visibility="collapsed", key="z3")
                    with cz4:
                        st.markdown("<div class='z4-titre'>Z4</div><span class='fcmax'>Seuil</span>", unsafe_allow_html=True)
                        z4 = st.number_input("z4", 0, step=1, label_visibility="collapsed", key="z4")
                    with cz5:
                        st.markdown("<div class='z5-titre'>Z5</div><span class='fcmax'>VO2</span>", unsafe_allow_html=True)
                        z5 = st.number_input("z5", 0, step=1, label_visibility="collapsed", key="z5")
                    
                    total_zones = z1 + z2 + z3 + z4 + z5
                    st.markdown(f"<div style='text-align: right; color: gray; font-size: 0.85em; font-weight: bold;'>Total cumulé : {total_zones} min (cible théorique : {duree_totale} min)</div>", unsafe_allow_html=True)
                    st.divider()

                # --- 🔥 INTERFACE MÉTABOLIQUE SECONDAIRE (WOD / CROSS-TRAINING) ---
                elif est_un_wod:
                    st.info("🔥 Séance métabolique (Cross-Training / WOD) détectée !")
                    col1, col2 = st.columns(2)
                    with col1: 
                        duree_totale = st.number_input("Durée totale (min)", min_value=0, step=1, value=45)
                    with col2: 
                        format_wod = st.selectbox("Format", ["Solo", "Duo", "Team"])
                    
                    st.write("📸 Scanner le tableau de la Box")
                    photo_tableau = st.file_uploader("Upload la photo du WOD", type=['png', 'jpg', 'jpeg'])
                    if photo_tableau is not None:
                        st.success("✅ Image chargée !")
                        texte_wod_decode = st.text_area("Exercices détectés :", value="1000m Run\n50 Wall Balls...")
                    st.divider()

                # --- 🏋️‍♂️ INTERFACE RENFORCEMENT / PPG CLINIQUE ---
                else:
                    st.markdown("##### 🏋️‍♂️ Suivi des blocs de Préparation Physique Générale (PPG)")
                    st.caption("Renseigne tes charges et tes répétitions réelles pour chaque mouvement de force.")

                    # ---> LE CORRECTIF EST ICI (On recrée la mémoire) <---
                    historique_seance = {}
                    col_btn, _ = st.columns([1, 2])
                    with col_btn:
                        if st.button("📋 Pré-remplir avec mes anciennes charges"):
                            st.session_state["historique_preload"] = get_derniere_seance(str(type_seance))
                    
                    if "historique_preload" in st.session_state:
                        historique_seance = st.session_state["historique_preload"]
                        if historique_seance:
                            st.success("✅ Charges récupérées !")
                    # --------------------------------------------------------

                    df_realise = load_historique_realise()
                    for idx, row in seance_df.iterrows():
                        exo_nom = row['Exercice_WOD']
                        safe_key = f"{idx}_{str(exo_nom).replace(' ', '_')}"
                        
                        try:
                            nb_series = int(row['Series_Cible'])
                            if nb_series <= 0: nb_series = 1
                        except: nb_series = 1
                        
                        nom_exo_base = str(row['Exercice_WOD'])
                        # La suite de votre code reste identique...
                        if historique_seance and nom_exo_base in historique_seance:
                            poids_defaut = historique_seance[nom_exo_base]["poids"]
                            reps_defaut = historique_seance[nom_exo_base]["reps"]
                        else:
                            try: poids_defaut = float(row['Poids_Cible_Kg'])
                            except: poids_defaut = 0.0
                            try: reps_defaut = int(''.join(filter(str.isdigit, str(row['Reps_Cible']))))
                            except: reps_defaut = 0

                        with st.expander(f"⚙️ {exo_nom} — {nb_series} séries prévues", expanded=True):
                            # Moteur algorithmique de conseil de charge (Anti-crash intégré)
                            try:
                                if not df_realise.empty and len(df_realise.columns) > 7:
                                    dernieres_perfs = df_realise[df_realise.iloc[:, 4].astype(str).str.contains(exo_nom, na=False, regex=False)].tail(1)
                                    if not dernieres_perfs.empty:
                                        p_prec = dernieres_perfs.iloc[0, 5]
                                        r_prec = dernieres_perfs.iloc[0, 6]
                                        rir_prec = dernieres_perfs.iloc[0, 7]
                                        st.markdown(f"ℹ️ **Dernière réalisation :** {p_prec}kg x {r_prec} (RIR {rir_prec})")
                                        if int(rir_prec) >= 2:
                                            st.success(f"📈 **Conseil Coach :** Surcharge progressive recommandée : **+{round(float(p_prec)*0.05, 1)}kg**.")
                                        elif int(rir_prec) == 0:
                                            st.warning("⚖️ **Conseil Coach :** Échec atteint à la dernière session. Stabilise la charge et focus sur le contrôle moteur.")
                            except: pass
                            
                            st.write("")
                            col_h1, col_h2, col_h3, col_h4 = st.columns([1, 2, 2, 2])
                            with col_h1: st.markdown("<div style='color: gray; font-size: 0.85em; font-weight: bold;'>Série</div>", unsafe_allow_html=True)
                            with col_h2: st.markdown("<div style='color: gray; font-size: 0.85em; font-weight: bold;'>Charge (kg)</div>", unsafe_allow_html=True)
                            with col_h3: st.markdown("<div style='color: gray; font-size: 0.85em; font-weight: bold;'>Répétitions</div>", unsafe_allow_html=True)
                            with col_h4: st.markdown("<div style='color: gray; font-size: 0.85em; font-weight: bold;'>RIR (Marge)</div>", unsafe_allow_html=True)
                            
                            for serie in range(1, nb_series + 1):
                                col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
                                with col1:
                                    st.markdown(f"<div style='margin-top: 10px; font-weight: bold;'>#{serie}</div>", unsafe_allow_html=True)
                                with col2:
                                    st.number_input("Poids", min_value=0.0, step=0.5, value=poids_defaut, key=f"poids_{safe_key}_s{serie}", label_visibility="collapsed")
                                with col3:
                                    st.number_input("Reps", min_value=0, step=1, value=reps_defaut, key=f"reps_{safe_key}_s{serie}", label_visibility="collapsed")
                                with col4:
                                    st.selectbox("RIR", [0, 1, 2, 3, 4], index=2, key=f"rir_{safe_key}_s{serie}", label_visibility="collapsed", help="Reps in Reserve (Répétitions de réserve avant l'échec)")

                    st.divider()
                    duree_totale = st.number_input("⏱️ Durée totale de la séance de PPG (min)", min_value=0, step=1, value=45)

                # --- 🎛️ ÉVALUATION DE LA CHARGE INTERNE GLOBALE (BORG RPE) ---
                st.markdown("##### 🧠 Intensité Globale de la Séance (Charge Interne)")
                session_rpe = st.slider("Note ton niveau d'effort perçu (Échelle de Borg RPE)", 1, 10, 6)
                st.caption("📋 *1-2 : Très facile | 3-4 : Facile | 5-6 : Modéré / Endurance Fondamentale | 7-8 : Difficile / Seuil | 9-10 : Effort Maximal / PMA*")

                # --- 💾 LOGIQUE DE SAUVEGARDE UNIFIÉE ---
                st.write("")
                if st.button("💾 Valider et Enregistrer ma séance", type="primary", use_container_width=True):
                    lignes_a_sauvegarder = []
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")

                    # ==========================================
                    # CAS 1 : Enregistrement Cardio / Vo2 / WOD
                    # ==========================================
                    if est_une_course or est_un_wod:
                        titre_bilan = f"Bilan Endurance" if est_une_course else f"Bilan WOD | Format:{format_wod}"
                        if est_un_wod and texte_wod_decode:
                            titre_bilan += f" | {texte_wod_decode.replace(chr(10), ' / ')}"

                        # Sécurisation des variables (si c'est un WOD, le dénivelé n'existe pas)
                        sport_final = sport_realise if est_une_course else "Cross-Training"
                        denivele_final = denivele if est_une_course else 0
                        allure_final = allure_watts if est_une_course else ""

                        ligne_cardio = [
                            date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), titre_bilan, 
                            0.0, 0, 0, 0, int(session_rpe), 
                            float(distance), int(duree_totale), int(z1), int(z2), int(z3), int(z4), int(z5),
                            # ---> NOS 3 NOUVELLES COLONNES ÉLITES <---
                            str(sport_final), int(denivele_final), str(allure_final)
                        ]
                        lignes_a_sauvegarder.append(ligne_cardio)

                    # ==========================================
                    # CAS 2 : Enregistrement de Force / PPG
                    # ==========================================
                    else:
                        for idx, row in seance_df.iterrows():
                            exo_nom = row['Exercice_WOD']
                            safe_key = f"{idx}_{str(exo_nom).replace(' ', '_')}"
                            
                            try:
                                nb_series = int(row['Series_Cible'])
                                if nb_series <= 0: nb_series = 1
                            except: nb_series = 1
                            
                            for serie in range(1, nb_series + 1):
                                # Sécurité : si l'utilisateur n'a pas touché au champ, on le récupère
                                poids = st.session_state.get(f"poids_{safe_key}_s{serie}", 0.0)
                                reps = st.session_state.get(f"reps_{safe_key}_s{serie}", 0)
                                rir = st.session_state.get(f"rir_{safe_key}_s{serie}", 2)
                                rpe_serie = 10 - rir
                                
                                nom_exo_complet = f"{exo_nom} (Série {serie})"
                                ligne_exo = [
                                    date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), str(nom_exo_complet), 
                                    float(poids), int(reps), int(rir), int(rpe_serie), int(session_rpe),
                                    0.0, int(duree_totale), 0, 0, 0, 0, 0,
                                    # ---> NOS 3 NOUVELLES COLONNES (Remplies par défaut pour la muscu) <---
                                    "Renforcement / PPG", 0, ""
                                ]
                                lignes_a_sauvegarder.append(ligne_exo)
                    
                    # Envoi vers Google Sheets & Flush du cache
                    try:
                        save_performance(lignes_a_sauvegarder)
                        st.cache_data.clear()
                        st.success(f"✅ Entraînement de {sport_final if est_une_course else 'PPG'} enregistré avec succès !")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erreur lors de l'écriture sur Google Sheets : {e}")

    except Exception as e:
        st.error(f"Erreur d'accès au calendrier de l'athlète : {e}")
        
#----PAGE 3 : MES STATS----      

elif page == "Mes Insights (Data)":
    st.header("📊 Cockpit Performance & Readiness")
    
    # --- CHARGEMENT DES DONNÉES ---
    df_realise = load_historique_realise()
    df_checkin = load_historique_checkin()

    # --- AFFICHAGE DU READINESS SCORE ---
    if not df_checkin.empty:
        # On récupère la toute dernière ligne (le check-in du jour)
        dernier_checkin = df_checkin.iloc[-1]
        
        # ⚠️ ATTENTION AUX INDEX : Ajustez selon l'ordre des colonnes dans votre Google Sheets
        # Si vos colonnes sont : Date, Sommeil, VFC, FCR, Energie, Muscles
        try:
            # 1. On récupère la valeur brute
            brut_sommeil = str(dernier_checkin.iloc[1])
            # 2. On remplace la virgule par un point, puis on convertit en float
            val_sommeil = float(brut_sommeil.replace(',', '.'))
            
            val_vfc = int(dernier_checkin.iloc[2])
            val_fcr = int(dernier_checkin.iloc[3]) 
            val_energie = int(dernier_checkin.iloc[4])
            
            # On appelle notre algorithme
            score = calculer_readiness(val_sommeil, val_vfc, val_fcr, val_energie)
            
            # --- JAUGE PLOTLY FUTURISTE ---
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = score,
                number = {'suffix': "%", 'font': {'size': 50, 'color': "white"}},
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': "Readiness Score Global", 'font': {'size': 20, 'color': 'gray'}},
                gauge = {
                    'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "white"},
                    'bar': {'color': "white", 'thickness': 0.2},
                    'bgcolor': "rgba(0,0,0,0)",
                    'borderwidth': 0,
                    'steps': [
                        {'range': [0, 50], 'color': "rgba(255, 75, 75, 0.4)"},  # Rouge
                        {'range': [50, 75], 'color': "rgba(255, 215, 0, 0.4)"}, # Jaune
                        {'range': [75, 100], 'color': "rgba(88, 214, 141, 0.4)"} # Vert
                    ],
                }
            ))
            fig_gauge.update_layout(paper_bgcolor="rgba(0,0,0,0)", height=350, margin=dict(t=50, b=0, l=0, r=0))
            
            # Affichage dans l'application
            col_gauge, col_texte = st.columns([1, 1])
            with col_gauge:
                st.plotly_chart(fig_gauge, use_container_width=True)
            with col_texte:
                st.markdown("<br><br>", unsafe_allow_html=True)
                if score >= 75:
                    st.success("🟢 **Feu vert !** Tes constantes sont excellentes. Tu peux encaisser une grosse charge d'entraînement aujourd'hui.")
                elif score >= 50:
                    st.warning("🟡 **Attention !** Récupération moyenne. Privilégie une séance d'endurance fondamentale (Zone 2) ou réduis l'intensité.")
                else:
                    st.error("🔴 **Alerte Fatigue !** Tes constantes sont dans le rouge. L'algorithme recommande du repos actif ou un jour off pour éviter la blessure.")
        except Exception as e:
            st.error(f"Erreur technique détaillée : {e}")

    st.divider()

    if df_realise.empty:
        st.info("Aucune donnée d'entraînement enregistrée pour le moment.")
    else:
        # --- PRÉPARATION DES DONNÉES ---
        df_realise['Date'] = pd.to_datetime(df_realise.iloc[:, 0])
        df_realise['Semaine'] = pd.to_numeric(df_realise.iloc[:, 1], errors='coerce')
        df_realise['Poids'] = pd.to_numeric(df_realise.iloc[:, 5], errors='coerce').fillna(0)
        df_realise['Reps'] = pd.to_numeric(df_realise.iloc[:, 6], errors='coerce').fillna(0)
        df_realise['Session_RPE'] = pd.to_numeric(df_realise.iloc[:, 9], errors='coerce').fillna(0)
        df_realise['Duree_Cardio'] = pd.to_numeric(df_realise.iloc[:, 11], errors='coerce').fillna(0)
        
        # ---> LECTURE DES NOUVELLES DONNÉES ÉLITE (Sport, D+) <---
        try:
            df_realise['Sport'] = df_realise.iloc[:, 17].astype(str)
            df_realise['Denivele'] = pd.to_numeric(df_realise.iloc[:, 18], errors='coerce').fillna(0)
        except:
            df_realise['Sport'] = "Cross-Training"
            df_realise['Denivele'] = 0
            
        # Grouper par Date, Semaine et Sport pour avoir 1 ligne = 1 séance
        seances = df_realise.groupby(['Date', 'Semaine', 'Sport']).agg(
            Session_RPE=('Session_RPE', 'max'),
            Duree_Cardio=('Duree_Cardio', 'max'),
            Denivele_Total=('Denivele', 'max'),
            Duree_Seance=('Duree_Cardio', lambda x: 45 if x.max() == 0 else x.max())
        ).reset_index()
        
        # CALCUL DE BORG (sRPE : RPE x Durée)
        seances['Charge_Borg'] = seances['Session_RPE'] * seances['Duree_Seance']
        
        semaine_actuelle = int(seances['Semaine'].max())
        seances_semaine_actuelle = seances[seances['Semaine'] == semaine_actuelle]
        
        # --- SECTION 1 : LES VRAIS KPI (Triathlon / Trail Ready) ---
        st.subheader("📌 Vue d'ensemble (Semaine actuelle)")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        # 1. Nbr de séances
        nb_seances_tot = len(seances)
        nb_seances_sem = len(seances_semaine_actuelle)
        col1.metric("Séances (Sem)", f"{nb_seances_sem}")
        
        # 2. Temps passé
        temps_semaine_heures = seances_semaine_actuelle['Duree_Seance'].sum() / 60
        col2.metric("Volume (Sem)", f"{temps_semaine_heures:.1f} h")
        
        # 3. Dénivelé cumulé (Nouveau !)
        dplus_semaine = seances_semaine_actuelle['Denivele_Total'].sum()
        col3.metric("Dénivelé (D+)", f"{int(dplus_semaine)} m")
        
        # 4. RPE Moyen
        rpe_moyen_sem = seances_semaine_actuelle['Session_RPE'].mean() if not seances_semaine_actuelle.empty else 0
        col4.metric("RPE Moyen", f"{rpe_moyen_sem:.1f} / 10")
        
        # 5. Sommeil Moyen
        sommeil_moyen = 0
        douleurs_recentes = "Aucune"
        if not df_checkin.empty:
            df_checkin['Date'] = pd.to_datetime(df_checkin.iloc[:, 0])
            df_checkin['Sommeil'] = pd.to_numeric(df_checkin.iloc[:, 1], errors='coerce')
            sommeil_moyen = df_checkin.tail(7)['Sommeil'].mean()
            douleurs_recentes = df_checkin.iloc[-1, 5] 
            col5.metric("Sommeil (7j)", f"{sommeil_moyen:.1f} h")
        else:
            col5.metric("Sommeil", "N/A")
# --- SECTION : VOLUME PAR DISCIPLINE (Triathlon / Hybride) ---
        st.subheader("🏊‍♂️ 🚴‍♂️ 🏃‍♂️ Volume par Discipline")
        
        # On s'assure que la colonne Sport_Discipline existe bien
        if 'Sport_Discipline' in seances_semaine_actuelle.columns:
            volume_par_sport = seances_semaine_actuelle.groupby('Sport_Discipline')['Duree_Seance'].sum().reset_index()
            
            if not volume_par_sport.empty and volume_par_sport['Duree_Seance'].sum() > 0:
                volume_par_sport['Heures'] = volume_par_sport['Duree_Seance'] / 60
                
                fig_sports = px.bar(
                    volume_par_sport,
                    x='Heures', y='Sport_Discipline', orientation='h',
                    text=volume_par_sport['Heures'].apply(lambda x: f"{x:.1f}h"),
                    color='Sport_Discipline',
                    color_discrete_sequence=['#00F0FF', '#FF4B4B', '#00FF00', '#FFD700', '#9D00FF']
                )
                
                fig_sports.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=250, margin=dict(l=0, r=0, t=10, b=0),
                    showlegend=False, xaxis_title="Heures d'entraînement", yaxis_title=""
                )
                fig_sports.update_traces(textposition='outside')
                st.plotly_chart(fig_sports, use_container_width=True)
            else:
                st.caption("Aucun volume enregistré cette semaine.")
        else:
            st.caption("La colonne Sport n'est pas encore synchronisée.")
        
        st.divider()
        
        # --- SECTION 2 : MODÉLISATION BANISTER (CTL / ATL / TSB) ---
        st.subheader("🧬 Modélisation de la Forme (Banister / TrainingPeaks)")
        st.caption("Évolution de ta Condition (Fitness), ta Fatigue, et ton État de Forme (TSB).")
        
        # On trie les séances chronologiquement
        seances = seances.sort_values(by='Date').reset_index(drop=True)
        
        # 1. Calcul de la charge (TSS proxy) - TOUJOURS EFFECTUÉ, même avec 1 seule séance !
        if not seances.empty:
            seances['TSS'] = seances['Charge_Borg'] * 1.5 
        
        if len(seances) > 3: # Il faut un minimum de données pour lisser la courbe
            # 2. Algorithme des Moyennes Mobiles Exponentielles (EMA)
            seances['Fitness_CTL'] = seances['TSS'].ewm(span=42, adjust=False).mean()
            seances['Fatigue_ATL'] = seances['TSS'].ewm(span=7, adjust=False).mean()
            seances['Forme_TSB'] = seances['Fitness_CTL'].shift(1) - seances['Fatigue_ATL'].shift(1)
            seances = seances.fillna(0) # Nettoie le premier jour
            
            fig_banister = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Aire bleue de Fitness
            fig_banister.add_trace(go.Scatter(
                x=seances['Date'], y=seances['Fitness_CTL'], name="Fitness (CTL)",
                mode='lines', line=dict(color='#1E90FF', width=2), fill='tozeroy', fillcolor='rgba(30, 144, 255, 0.2)'
            ), secondary_y=False)
            
            # Ligne rouge de Fatigue
            fig_banister.add_trace(go.Scatter(
                x=seances['Date'], y=seances['Fatigue_ATL'], name="Fatigue (ATL)",
                mode='lines', line=dict(color='#FF4B4B', width=2, dash='dot')
            ), secondary_y=False)
            
            # Ligne jaune/verte de Forme (TSB)
            fig_banister.add_trace(go.Scatter(
                x=seances['Date'], y=seances['Forme_TSB'], name="Forme (TSB)",
                mode='lines', line=dict(color='#FFD700', width=3)
            ), secondary_y=True)
            
            # Zones de Forme
            fig_banister.add_hrect(y0=-10, y1=10, fillcolor="#00FF00", opacity=0.1, secondary_y=True, annotation_text="Pic de Forme")
            fig_banister.add_hrect(y0=-30, y1=-10, fillcolor="#FFA500", opacity=0.1, secondary_y=True, annotation_text="Zone d'Entraînement")
            fig_banister.add_hrect(y0=-100, y1=-30, fillcolor="#FF0000", opacity=0.1, secondary_y=True, annotation_text="Risque Surcharge")

            fig_banister.update_layout(template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", hovermode="x unified", legend=dict(orientation="h", y=1.1))
            st.plotly_chart(fig_banister, use_container_width=True)
        else:
            st.info("📊 Continue d'enregistrer des séances. Le modèle de Banister s'activera après quelques jours de données.")

        # --- SECTION 3 : PRÉDICTIONS INTELLIGENTES (L'Atout Data Science) ---
        st.subheader("🔮 Algorithmes Prédictifs (Live)")
        col_pred1, col_pred2 = st.columns(2)
        
        with col_pred1:
            # SÉCURITÉ : on vérifie que la colonne Forme_TSB existe bien
            tsb_actuel = seances['Forme_TSB'].iloc[-1] if 'Forme_TSB' in seances.columns else 0
            
            if tsb_actuel < -30:
                risque, couleur_r = "ÉLEVÉ (75%)", "#FF4B4B"
                conseil = "⚠️ Ton corps ne compense plus la fatigue. Divise le volume par 2 aujourd'hui."
            elif -30 <= tsb_actuel < -10:
                risque, couleur_r = "MODÉRÉ (30%)", "#FFA500"
                conseil = "⚡ Surcharge optimale. Continue, mais surveille ton sommeil."
            else:
                risque, couleur_r = "FAIBLE (5%)", "#00FF00"
                conseil = "✅ Fraîcheur optimale. Tu es prêt pour une intensité maximale (PMA/Seuil)."
            
            st.markdown(f"<h4 style='color:{couleur_r};'>Probabilité de Blessure : {risque}</h4>", unsafe_allow_html=True)
            st.write(conseil)
            
        with col_pred2:
            # SÉCURITÉ : on lit la colonne TSS qui est maintenant toujours générée
            tss_hier = seances['TSS'].iloc[-1] if 'TSS' in seances.columns else 0
            ttr_heures = max(12, min(72, tss_hier * 0.4)) 
            st.markdown(f"<h4>Temps de Récupération Estimé (TTR)</h4>", unsafe_allow_html=True)
            st.metric(label="Régénération métabolique complète dans :", value=f"{int(ttr_heures)} Heures")
            
# --- SECTION 4 : SURCHARGE PROGRESSIVE (Design Premium) ---
        st.subheader("🏋️‍♂️ Suivi de Préparation Physique (PPG)")
        st.caption("Évolution des charges sur les exercices de renforcement musculaire (Force & Prévention).")
        
        # Le code est caché dans ce menu déroulant
        with st.expander("Afficher l'analyse de progression détaillée 📈"):
            liste_exos = [exo for exo in df_realise.iloc[:, 4].unique() if "Bilan" not in str(exo)]
            
            if liste_exos:
                exo_choisi = st.selectbox("Sélectionne un mouvement de PPG :", liste_exos)
                
                df_exo = df_realise[df_realise.iloc[:, 4] == exo_choisi].copy()
                prog_exo = df_exo.groupby('Date').agg(Poids_Max=('Poids', 'max'), Reps_Totales=('Reps', 'sum')).reset_index()
                
                fig_prog = make_subplots(specs=[[{"secondary_y": True}]])
                
                # Aire remplie sous la courbe pour le volume (Reps)
                fig_prog.add_trace(go.Scatter(
                    x=prog_exo['Date'], y=prog_exo['Reps_Totales'], 
                    name="Répétitions Totales", 
                    fill='tozeroy', mode='lines',
                    line=dict(color='rgba(255, 255, 255, 0.2)', width=1),
                    fillcolor='rgba(255, 255, 255, 0.05)'
                ), secondary_y=False)
                
                # Ligne de Poids max avec dégradé et lissage
                fig_prog.add_trace(go.Scatter(
                    x=prog_exo['Date'], y=prog_exo['Poids_Max'], 
                    name="Poids Max Soulevé (kg)", 
                    mode="lines+markers", 
                    line=dict(color="#FF4B4B", width=3, shape='spline'),
                    marker=dict(size=8, color="#0e1117", line=dict(color="#FF4B4B", width=2))
                ), secondary_y=True)
                
                fig_prog.update_layout(
                    template="plotly_dark",
                    paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    height=350,
                    margin=dict(l=0, r=0, t=10, b=0),
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                    hovermode="x unified"
                )
                fig_prog.update_yaxes(showgrid=False, secondary_y=False)
                fig_prog.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)', secondary_y=True)
                st.plotly_chart(fig_prog, use_container_width=True)

        st.divider()
        

        # --- SECTION 5 : ZONES CARDIAQUES (Donut Futuriste) ---
        st.subheader("❤️ Répartition de l'Endurance (Zones Cardiaques)")
        z1 = pd.to_numeric(df_realise.iloc[:, 12], errors='coerce').sum()
        z2 = pd.to_numeric(df_realise.iloc[:, 13], errors='coerce').sum()
        z3 = pd.to_numeric(df_realise.iloc[:, 14], errors='coerce').sum()
        z4 = pd.to_numeric(df_realise.iloc[:, 15], errors='coerce').sum()
        z5 = pd.to_numeric(df_realise.iloc[:, 16], errors='coerce').sum()
        
        if (z1 + z2 + z3 + z4 + z5) > 0:
            # Palette de couleurs progressives du froid (Z1) au chaud (Z5)
            colors = ['#1E90FF', '#00FA9A', '#FFD700', '#FF8C00', '#FF1493']
            labels = ['Zone 1 (Récup)', 'Zone 2 (Endurance)', 'Zone 3 (Tempo)', 'Zone 4 (Seuil)', 'Zone 5 (VO2 Max)']
            
            fig_zones = go.Figure(data=[go.Pie(
                labels=labels, values=[z1, z2, z3, z4, z5], 
                hole=0.6, # Trou plus large pour un effet "Anneau"
                marker=dict(colors=colors, line=dict(color='#0e1117', width=2)),
                textinfo='percent',
                hoverinfo='label+value+percent'
            )])
            
            fig_zones.update_layout(
                template="plotly_dark",
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                height=350,
                margin=dict(l=0, r=0, t=10, b=0),
                annotations=[dict(text='CARDIO<br>ZONES', x=0.5, y=0.5, font_size=16, showarrow=False, font_color='white')]
            )
            st.plotly_chart(fig_zones, use_container_width=True)
        else:
            st.caption("Aucune donnée de fréquence cardiaque enregistrée pour le moment.")
                    
# ---- PAGE 4 : CRÉATEUR DE PROGRAMME ----
elif page == "Coach IA (Analyse)":
    st.header("🛠️ Gestion du Programme")
    
    tab1, tab2 = st.tabs([" Saisie Rapide (Historique)", "🤖 Génération par l'IA"])

    # ---------------------------------------------------------
    # ONGLET 1 : PLANIFICATION MANUELLE (Design Premium)
    # ---------------------------------------------------------
    with tab1:
        st.markdown("### 📝 Planificateur de cycle")
        st.write("Ajoute de nouveaux blocs de travail à ton calendrier d'entraînement.")
        
        # --- BLOC 1 : LE CONTEXTE ---
        with st.container():
            st.markdown("#### 1️⃣ Contexte de la séance")
            try:
                df = load_programme()
                liste_seances = df["Type_Seance"].dropna().unique().tolist()
                liste_exos = df["Exercice_WOD"].dropna().unique().tolist()
                semaine_actuelle = int(df["Semaine"].max()) if not df.empty else 1
            except:
                liste_seances, liste_exos, semaine_actuelle = [], [], 1

            options_seances = ["-- Nouvelle séance --"] + liste_seances
            options_exos = ["-- Nouvel exercice --"] + liste_exos

            col1, col2, col3 = st.columns(3)
            with col1:
                semaine = st.number_input("Semaine cible", min_value=1, step=1, value=semaine_actuelle)
            with col2:
                jour = st.selectbox("Jour théorique", ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"])
            with col3:
                choix_seance = st.selectbox("Type de séance", options_seances)
                if choix_seance == "-- Nouvelle séance --":
                    type_seance = st.text_input("📝 Nommer la séance (ex: Capacité Aérobie, Force Max)")
                else:
                    type_seance = choix_seance

        st.write("") # Petit espace respirable

        # --- OPTION CACHÉE : DUPLICATION (Évite de polluer l'écran) ---
        if type_seance and type_seance != "-- Nouvelle séance --":
            with st.expander("⚡ Optionnel : Dupliquer depuis une semaine précédente", expanded=False):
                try:
                    df_prog = load_programme()
                    semaine_prec = semaine - 1
                    df_modele = df_prog[(df_prog["Semaine"] == semaine_prec) & (df_prog["Type_Seance"] == type_seance)].copy()
                    
                    if not df_modele.empty:
                        st.info(f"📋 **{len(df_modele)} mouvements** trouvés en Semaine {semaine_prec}.")
                        df_editable = df_modele[["Exercice_WOD", "Series_Cible", "Reps_Cible", "Poids_Cible_Kg"]].rename(columns={
                            "Exercice_WOD": "Exercice", "Series_Cible": "Séries", "Reps_Cible": "Reps", "Poids_Cible_Kg": "Charge (kg)"
                        }).reset_index(drop=True)
                        df_editable["Reps"] = df_editable["Reps"].astype(str)
                        
                        df_modifie = st.data_editor(df_editable, use_container_width=True, hide_index=True, num_rows="dynamic")
                        
                        if st.button("Valider la duplication", type="primary"):
                            lignes = []
                            for _, row in df_modifie.iterrows():
                                if pd.notna(row["Exercice"]) and str(row["Exercice"]).strip() != "":
                                    lignes.append([int(semaine), str(jour), str(type_seance), str(row["Exercice"]), 
                                                   int(row["Séries"]) if pd.notna(row["Séries"]) else 1, str(row["Reps"]), 
                                                   float(row["Charge (kg)"]) if pd.notna(row["Charge (kg)"]) else 0.0])
                            if lignes:
                                save_performance(lignes) # Remplacez par save_nouveau_programme(lignes) si vous avez une fonction bulk, sinon une boucle.
                                for ligne in lignes: save_nouveau_programme(ligne)
                                load_programme.clear()
                                st.success("✅ Duplication réussie !")
                    else:
                        st.caption(f"Aucun modèle trouvé pour la Semaine {semaine_prec}.")
                except: pass

        # --- BLOC 2 : AJOUT MANUEL D'EXERCICE ---
        st.write("")
        with st.container():
            st.markdown("#### 2️⃣ Ajouter un mouvement")
            type_seance_lower = str(type_seance).lower() if type_seance else ""
            mots_cles_cardio = ["course", "run", "fractionné", "piste", "endurance", "z2", "aérobie", "seuil", "vo2"]
            est_cardio = any(mot in type_seance_lower for mot in mots_cles_cardio)

            if est_cardio:
                st.info("🏃‍♂️ Bloc métabolique / Cardio détecté.")
                col_a, col_b = st.columns(2)
                with col_a:
                    exercice = st.text_input("Détails du bloc", value="Endurance fondamentale Z2")
                with col_b:
                    duree = st.number_input("Durée totale estimée (min)", min_value=1, step=1, value=60)
                series, reps, poids = 0, f"{duree} min", 0.0
            else:
                st.info("🏋️‍♂️ Bloc de Renforcement / PPG détecté.")
                choix_exo = st.selectbox("Mouvement de PPG", options_exos)
                if choix_exo == "-- Nouvel exercice --":
                    exercice = st.text_input("📝 Nom du mouvement (ex: Back Squat)")
                else:
                    exercice = choix_exo

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    series = st.number_input("Séries", min_value=1, step=1, value=3)
                with col_b:
                    reps = st.text_input("Répétitions / Temps", value="8")
                with col_c:
                    poids = st.number_input("Charge (kg)", min_value=0.0, step=0.5, value=0.0)

            # BOUTON DE SAUVEGARDE ESTHÉTIQUE
            st.write("")
            if st.button("➕ Ajouter ce mouvement au calendrier", type="primary", use_container_width=True):
                if not type_seance or not exercice:
                    st.error("⚠️ Le nom de la séance et du mouvement sont obligatoires.")
                else:
                    nouvelle_ligne_prog = [int(semaine), str(jour), str(type_seance), str(exercice), int(series), str(reps), float(poids)]
                    try:
                        save_nouveau_programme(nouvelle_ligne_prog) 
                        load_programme.clear()
                        st.success(f"✅ Mouvement ajouté à la semaine {semaine} !")
                    except Exception as e:
                        st.error(f"Erreur : {e}")

    # ---------------------------------------------------------
    # ONGLET 2 : LE COACH IA (DYNAMIQUE)
    # ---------------------------------------------------------
    with tab2:
        st.subheader("🧠 Générer une séance avec l'IA")
        
        # Le contrôle de la destination explicite !
        st.markdown("##### 📍 Où veux-tu planifier cette séance ?")
        col_dest1, col_dest2 = st.columns(2)
        with col_dest1:
            try:
                semaine_act_ia = int(load_programme()["Semaine"].max())
            except:
                semaine_act_ia = 1
            ia_semaine = st.number_input("Pour la Semaine n°", min_value=1, step=1, value=semaine_act_ia, key="ia_sem")
        with col_dest2:
            ia_jour = st.selectbox("Le jour", ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"], key="ia_jour")
        st.divider()
        
        # INITIALISATION DE LA MÉMOIRE (SESSION STATE)
        if "seance_ia_generee" not in st.session_state:
            st.session_state.seance_ia_generee = None
            
        # --- BLOC RÉCUPÉRATION DU CHECK-IN (Celui qui avait disparu !) ---
        df_checkin = load_historique_checkin()
        sommeil_defaut, energie_defaut, courbatures_defaut = 7.0, 7, "Aucune"
        if not df_checkin.empty:
            dernier_checkin = df_checkin.iloc[-1]
            try:
                # On nettoie la virgule pour le sommeil
                brut_sommeil = str(dernier_checkin.get("Heures_Sommeil", "7.0")).replace(',', '.')
                sommeil_defaut = float(brut_sommeil)
                sommeil_defaut = min(sommeil_defaut, 12.0) # Sécurité Streamlit max 12
                
                energie_defaut = int(dernier_checkin.get("Niveau_Energie", 7))
                energie_defaut = min(energie_defaut, 10)
                
                courbatures_defaut = str(dernier_checkin.get("Muscles_Douloureux", "Aucune"))
            except Exception as e: 
                pass
        # -----------------------------------------------------------------

        st.info("💡 Les données ci-dessous sont basées sur ton dernier Check-in. Modifie-les si besoin.")
        
        col_ia1, col_ia2 = st.columns(2)
        with col_ia1:
            ia_sommeil = st.number_input("Sommeil (h)", min_value=0.0, max_value=12.0, value=sommeil_defaut, step=0.5)
            ia_energie = st.slider("Énergie (1-10)", 1, 10, energie_defaut)
        with col_ia2:
            ia_courbatures = st.text_input("Douleurs / Courbatures ?", value=courbatures_defaut)
            # NOUVEAU VOCABULAIRE TRIATHLON / ÉLITE
            ia_objectif = st.selectbox("Type de séance voulu", [
                "Course : Sortie Longue (Z2)", 
                "Course : Fractionné / VMA",
                "Vélo : PMA / Seuil",
                "Vélo : Endurance Fondamentale",
                "Natation : Technique & Aérobie",
                "Trail : Renforcement Spécifique (D+)"
            ])
        
        # BOUTON DE GÉNÉRATION
        if st.button("✨ Générer ma séance sur mesure", type="primary"):
            with st.spinner("Le coach analyse tes données... 🧠"):
                success, resultat = generer_seance_ia(ia_energie, ia_sommeil, ia_courbatures, ia_objectif)
                if success:
                    st.session_state.seance_ia_generee = resultat
                    st.rerun() 
                else:
                    st.error(resultat)
        
        # --- L'IA A FAIT UNE PROPOSITION : ON AFFICHE LES RÉSULTATS ---
        if st.session_state.seance_ia_generee:
            seance = st.session_state.seance_ia_generee
            st.divider()
            st.markdown(f"### 🎯 {seance.get('titre', 'Séance IA')}")
            st.info(f"🗣️ **Coach :** {seance.get('message', '')}")
            
            df_exos = pd.DataFrame(seance.get("exercices", []))
            if not df_exos.empty:
                df_exos.columns = ["Exercice", "Séries", "Reps", "Poids (kg)"]
                st.dataframe(df_exos, use_container_width=True, hide_index=True)
            
            st.write(f"**Cette séance sera ajoutée à ton programme le {ia_jour} de la Semaine {ia_semaine}.**")
            col_action1, col_action2 = st.columns(2)
            
            with col_action1:
                if st.button("✅ L'accepter et l'ajouter au calendrier"):
                    with st.spinner("Sauvegarde en cours..."):
                        # ON UTILISE ia_semaine et ia_jour ICI !
                        if sauvegarder_seance_ia_programme(seance.get('titre', 'Séance IA'), df_exos, ia_semaine, ia_jour):
                            st.success(f"✅ Séance ajoutée au {ia_jour} de la Semaine {ia_semaine} !")
                            st.session_state.seance_ia_generee = None 
                            load_programme.clear() 
                            st.balloons()
                        else:
                            st.error("Erreur lors de la sauvegarde.")
                            
            with col_action2:
                if st.button("🔄 Non, propose-moi autre chose"):
                    st.session_state.seance_ia_generee = None
                    st.rerun()
