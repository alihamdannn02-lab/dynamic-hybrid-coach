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
        
        # Suppression dans Google Sheets
        worksheet.delete_rows(start_row, total_rows)
        return True, f"La séance du {last_date} ({count} lignes) a été annulée."
    except Exception as e:
        return False, f"Erreur : {e}"
        
def generer_seance_ia(energie, sommeil, courbatures, objectif):
    # On force l'IA à répondre avec un format JSON strict
    prompt = f"""Tu es un coach sportif d'élite expert en entraînement hybride.
    Voici l'état du client : Sommeil: {sommeil}h, Énergie: {energie}/10, Douleurs: {courbatures}, Objectif: {objectif}.
    
    Règles de sécurité : Si l'énergie est < 5 ou le sommeil < 6h, impose de la récupération active ou du cardio très léger. Évite les muscles douloureux.
    
    Tu DOIS répondre STRICTEMENT au format JSON. Ne renvoie aucun autre texte avant ou après.
    Voici le format exact attendu :
    {{
        "titre": "Titre de la séance",
        "message": "Ton mot d'encouragement personnalisé",
        "exercices": [
            {{"nom": "Nom de l'exercice 1", "series": 4, "reps": 10, "poids": 20}},
            {{"nom": "Nom de l'exercice 2", "series": 3, "reps": 12, "poids": 0}}
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
        
# ---- HEADER ----
st.title("Dynamic Hybrid Coach")
st.subheader("Ton coach personnel : Entrainement Hybride")
st.divider()

# --- NAVIGATION SIDEBAR AMÉLIORÉE ---
with st.sidebar:
    st.title("Hybrid Coach")
    st.markdown("## 🏋️‍♂️")
    st.divider()
    
    page = st.radio(
        "Menu Principal",
        [" Check-in Matinal", "Ma Séance du Jour", "Mes Stats", "Coach IA & Programme"],
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
        
# ---- PAGE 1 : CHECK-IN MATINAL ----
if page == " Check-in Matinal":
    st.header(" Check-in Matinal")
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

        semaine = st.selectbox("Semaine", sorted(df["Semaine"].unique()))
        seances_semaine = df[df["Semaine"] == semaine]
        options_seances = seances_semaine['Type_Seance'].unique()
        choix_seance = st.selectbox("🎯 Quelle séance veux-tu faire ?", options_seances)
        
        seance_df = seances_semaine[seances_semaine["Type_Seance"] == choix_seance]
        jour_theorique = seance_df["Jour"].iloc[0]
        seance_df = seance_df[seance_df["Jour"] == jour_theorique]

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

            # --- DÉTECTION DU MODE ---
            type_seance_lower = str(type_seance).lower()
            mots_cles_course = ["course", "run", "fractionné", "piste", "endurance", "z2"]
            mots_cles_wod = ["hyrox", "wod", "circuit", "conditioning", "boxing", "boxe"]
            
            # NOUVEAU : Les mots clés pour la récupération !
            mots_cles_repos = ["repos", "rest", "recovery", "récupération", "off"]
            
            est_une_course = any(mot in type_seance_lower for mot in mots_cles_course)
            est_un_wod = any(mot in type_seance_lower for mot in mots_cles_wod)
            est_un_repos = any(mot in type_seance_lower for mot in mots_cles_repos)

            # --- BOUTON COPIER SEMAINE DERNIÈRE ---
            historique_seance = {}
            if not est_une_course and not est_un_wod and not est_un_repos:
                col_btn1, _ = st.columns([1, 3])
                with col_btn1:
                    if st.button("📋 Pré-remplir depuis ma dernière séance"):
                        st.session_state["historique_preload"] = get_derniere_seance(str(type_seance))
                if "historique_preload" in st.session_state:
                    historique_seance = st.session_state["historique_preload"]
                    if historique_seance:
                        st.success(f"✅ {len(historique_seance)} exercices chargés depuis ta dernière séance !")

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
            else:
                distance, duree_totale, z1, z2, z3, z4, z5 = 0.0, 0, 0, 0, 0, 0, 0
                format_wod = "Solo"
                texte_wod_decode = ""

                # --- BLOC CARDIO ---
                if est_une_course or est_un_wod:
                    duree_cible_str = str(seance_df["Reps_Cible"].iloc[0])
                    duree_cible = 30 
                    try:
                        chiffres = ''.join(filter(str.isdigit, duree_cible_str))
                        if chiffres: duree_cible = int(chiffres)
                    except: pass

                    if est_une_course:
                        st.info("🏃‍♂️ Séance de course détectée !")
                        col1, col2 = st.columns(2)
                        with col1: distance = st.number_input("Distance (km)", min_value=0.0, step=0.1, value=5.0)
                        with col2: duree_totale = st.number_input("Durée totale (min)", min_value=0, step=1, value=duree_cible)
                    else:
                        st.info("🔥 Séance métabolique (Hyrox / Boxe / WOD) détectée !")
                        col1, col2 = st.columns(2)
                        with col1: duree_totale = st.number_input("Durée totale (min)", min_value=0, step=1, value=duree_cible)
                        with col2: format_wod = st.selectbox("Format", ["Solo", "Duo", "Team"])

                    st.write("❤️ **Zones de fréquence cardiaque**")
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
                    
                    total_zones = z1 + z2 + z3 + z4 + z5
                    st.markdown(f"<div style='text-align: right; color: gray; margin-top: 10px;'>Total : {total_zones} min</div>", unsafe_allow_html=True)

                    if est_un_wod:
                        st.write("📸 Scanner le tableau de la Box")
                        photo_tableau = st.file_uploader("Upload la photo du WOD", type=['png', 'jpg', 'jpeg'])
                        if photo_tableau is not None:
                            st.success("✅ Image chargée !")
                            texte_wod_decode = st.text_area("Exercices détectés :", value="1000m Run\n50 Wall Balls\n1000m Row...")
                    st.divider()

                # --- BLOC MUSCU ---
                if not est_une_course and not est_un_wod:
                    st.write("### 🏋️‍♂️ Détail des exercices")
                    st.caption("Renseigne tes performances pour chaque série.")

                    df_realise = load_historique_realise()
                    for idx, row in seance_df.iterrows():
                        exo_nom = row['Exercice_WOD']
                        safe_key = f"{idx}_{str(exo_nom).replace(' ', '_')}"
                        
                        try:
                            nb_series = int(row['Series_Cible'])
                            if nb_series <= 0: nb_series = 1
                        except:
                            nb_series = 1
                            
                        nom_exo_base = str(row['Exercice_WOD'])
                        if historique_seance and nom_exo_base in historique_seance:
                            poids_defaut = historique_seance[nom_exo_base]["poids"]
                            reps_defaut = historique_seance[nom_exo_base]["reps"]
                        else:
                            try: poids_defaut = float(row['Poids_Cible_Kg'])
                            except: poids_defaut = 0.0
                            try: reps_defaut = int(''.join(filter(str.isdigit, str(row['Reps_Cible']))))
                            except: reps_defaut = 0

                        with st.expander(f"{exo_nom} — {nb_series} séries x {row['Reps_Cible']} reps @ {row['Poids_Cible_Kg']} kg", expanded=True):
            
                            # --- SECTION CONSEIL DE PROGRESSION (À COLLER ICI) ---
                            # On cherche la dernière perf pour cet exercice spécifique
                            dernieres_perfs = df_realise[df_realise.iloc[:, 4].str.contains(exo_nom, na=False)].tail(1)
            
                            if not dernieres_perfs.empty:
                                p_prec = dernieres_perfs.iloc[0, 5]
                                r_prec = dernieres_perfs.iloc[0, 6]
                                rir_prec = dernieres_perfs.iloc[0, 7]
                
                                st.markdown(f"ℹ️ **Dernière séance :** {p_prec}kg x {r_prec} (RIR {rir_prec})")
                
                                # Algorithme de recommandation
                                try:
                                    if int(rir_prec) >= 2:
                                        st.success(f"📈 **Conseil Coach :** Tu avais de la marge ! Tente **+{round(float(p_prec)*0.05, 1)}kg** ou **+2 reps**.")
                                    elif int(rir_prec) == 0:
                                        st.warning("⚖️ **Conseil Coach :** Tu étais à l'échec. Maintien le poids, focus technique.")
                                except: pass
            
                            st.divider()
                            col_h1, col_h2, col_h3, col_h4 = st.columns([1, 2, 2, 2])
                            with col_h1: st.markdown("<div style='color: gray; font-size: 0.9em;'>Série</div>", unsafe_allow_html=True)
                            with col_h2: st.markdown("<div style='color: gray; font-size: 0.9em;'>Poids (kg)</div>", unsafe_allow_html=True)
                            with col_h3: st.markdown("<div style='color: gray; font-size: 0.9em;'>Reps</div>", unsafe_allow_html=True)
                            with col_h4: st.markdown("<div style='color: gray; font-size: 0.9em;'>RIR</div>", unsafe_allow_html=True)
                            
                            for serie in range(1, nb_series + 1):
                                col1, col2, col3, col4 = st.columns([1, 2, 2, 2])
                                with col1:
                                    st.markdown(f"<div style='margin-top: 10px; font-weight: bold;'>#{serie}</div>", unsafe_allow_html=True)
                                with col2:
                                    st.number_input("Poids", min_value=0.0, step=0.5, value=poids_defaut, key=f"poids_{safe_key}_s{serie}", label_visibility="collapsed")
                                with col3:
                                    st.number_input("Reps", min_value=0, step=1, value=reps_defaut, key=f"reps_{safe_key}_s{serie}", label_visibility="collapsed")
                                with col4:
                                    st.selectbox("RIR", [0, 1, 2, 3, 4], index=2, key=f"rir_{safe_key}_s{serie}", label_visibility="collapsed")

                st.divider()
                duree_muscu = st.number_input("⏱️ Durée de la séance (min)", min_value=0, step=1, value=60)
                session_rpe = st.slider("Note globale de la séance (RPE)", 1, 10, 7)
                st.caption("🔥 1-2: Très facile | 3-4: Facile | 5-6: Modéré | 7-8: Difficile | 9: Très difficile | 10: Effort maximal")

                # --- SAUVEGARDE CARDIO & MUSCU ---
                if st.button("Enregistrer la séance", type="primary"):
                    lignes_a_sauvegarder = []
                    date_du_jour = datetime.now().strftime("%Y-%m-%d")

                    if est_une_course or est_un_wod:
                        titre_bilan = "Bilan Course" if est_une_course else f"Bilan WOD | Format:{format_wod}"
                        if est_un_wod and texte_wod_decode:
                            titre_bilan += f" | {texte_wod_decode.replace(chr(10), ' / ')}"

                        ligne_cardio = [
                            date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), titre_bilan, 
                            0.0, 0, 0, 0, int(session_rpe), 
                            float(distance), int(duree_totale), int(z1), int(z2), int(z3), int(z4), int(z5)
                        ]
                        lignes_a_sauvegarder.append(ligne_cardio)

                    if not est_une_course and not est_un_wod:
                        for idx, row in seance_df.iterrows():
                            exo_nom = row['Exercice_WOD']
                            safe_key = f"{idx}_{str(exo_nom).replace(' ', '_')}"
                            
                            try:
                                nb_series = int(row['Series_Cible'])
                                if nb_series <= 0: nb_series = 1
                            except:
                                nb_series = 1
                            
                            for serie in range(1, nb_series + 1):
                                poids = st.session_state[f"poids_{safe_key}_s{serie}"]
                                reps = st.session_state[f"reps_{safe_key}_s{serie}"]
                                rir = st.session_state[f"rir_{safe_key}_s{serie}"]
                                rpe_serie = 10 - rir
                                
                                nom_exo_complet = f"{exo_nom} (Série {serie})"
                                
                                ligne_exo = [
                                    date_du_jour, int(semaine), vrai_jour_actuel, str(type_seance), str(nom_exo_complet), 
                                    float(poids), int(reps), int(rir), int(rpe_serie), int(session_rpe),
                                    0.0, int(duree_muscu), 0, 0, 0, 0, 0 
                                ]
                                lignes_a_sauvegarder.append(ligne_exo)
                    
                    try:
                        save_performance(lignes_a_sauvegarder)
                        st.cache_data.clear()
                        st.success(f"✅ Séance enregistrée avec succès pour ce {vrai_jour_actuel} !")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Erreur lors de la sauvegarde : {e}")

    except Exception as e:
        st.error(f"Erreur de connexion au programme : {e}")
        
#----PAGE 3 : MES STATS----       

elif page == "Mes Stats":
    st.header("📊 Cockpit Performance & Récupération")
    
    # --- CHARGEMENT DES DONNÉES ---
    df_realise = load_historique_realise()
    df_checkin = load_historique_checkin()

    if df_realise.empty:
        st.info("Aucune donnée d'entraînement enregistrée pour le moment.")
    else:
        # --- PRÉPARATION DES DONNÉES (Basée sur tes indices de colonnes exacts) ---
        df_realise['Date'] = pd.to_datetime(df_realise.iloc[:, 0])
        df_realise['Semaine'] = pd.to_numeric(df_realise.iloc[:, 1], errors='coerce')
        df_realise['Poids'] = pd.to_numeric(df_realise.iloc[:, 5], errors='coerce').fillna(0)
        df_realise['Reps'] = pd.to_numeric(df_realise.iloc[:, 6], errors='coerce').fillna(0)
        df_realise['Session_RPE'] = pd.to_numeric(df_realise.iloc[:, 9], errors='coerce').fillna(0)
        df_realise['Duree_Cardio'] = pd.to_numeric(df_realise.iloc[:, 11], errors='coerce').fillna(0)
        
        # Grouper par Date et Semaine pour avoir 1 ligne = 1 séance
        seances = df_realise.groupby(['Date', 'Semaine']).agg(
            Session_RPE=('Session_RPE', 'max'),
            Duree_Cardio=('Duree_Cardio', 'max'),
            # Si Duree_Cardio est 0, c'est de la muscu : on estime à 60 min par défaut pour le calcul
            Duree_Seance=('Duree_Cardio', lambda x: 60 if x.max() == 0 else x.max())
        ).reset_index()
        
        # CALCUL DE BORG (sRPE : RPE x Durée)
        seances['Charge_Borg'] = seances['Session_RPE'] * seances['Duree_Seance']
        
        semaine_actuelle = int(seances['Semaine'].max())
        seances_semaine_actuelle = seances[seances['Semaine'] == semaine_actuelle]

        # --- SECTION 1 : LES VRAIS KPI ---
        st.subheader("📌 Vue d'ensemble (Semaine actuelle)")
        col1, col2, col3, col4 = st.columns(4)
        
        # 1. Nbr de séances
        nb_seances_tot = len(seances)
        nb_seances_sem = len(seances_semaine_actuelle)
        col1.metric("Séances (Semaine)", f"{nb_seances_sem}", f"Total historique: {nb_seances_tot}")
        
        # 2. Temps passé
        temps_total_heures = seances['Duree_Seance'].sum() / 60
        temps_semaine_heures = seances_semaine_actuelle['Duree_Seance'].sum() / 60
        col2.metric("Temps d'effort (Semaine)", f"{temps_semaine_heures:.1f} h", f"Total: {temps_total_heures:.1f} h")
        
        # 3. RPE Moyen
        rpe_moyen_sem = seances_semaine_actuelle['Session_RPE'].mean() if not seances_semaine_actuelle.empty else 0
        col3.metric("RPE Moyen (Semaine)", f"{rpe_moyen_sem:.1f} / 10")
        
        # 4. Sommeil Moyen
        sommeil_moyen = 0
        douleurs_recentes = "Aucune"
        if not df_checkin.empty:
            df_checkin['Date'] = pd.to_datetime(df_checkin.iloc[:, 0])
            df_checkin['Sommeil'] = pd.to_numeric(df_checkin.iloc[:, 1], errors='coerce')
            sommeil_moyen = df_checkin.tail(7)['Sommeil'].mean() # Moyenne sur 7 jours
            douleurs_recentes = df_checkin.iloc[-1, 4] # Colonne des muscles douloureux du dernier check-in
            col4.metric("Sommeil Moyen (7j)", f"{sommeil_moyen:.1f} h")
        else:
            col4.metric("Sommeil Moyen", "N/A")

        st.divider()

        # --- SECTION 2 : ACWR (Design Premium) ---
        st.subheader("🛡️ Risque de Blessure & Surcharge (Méthode de Borg)")
        
        charge_hebdo = seances.groupby('Semaine')['Charge_Borg'].sum().reset_index()
        charge_hebdo['Charge_Chronique'] = charge_hebdo['Charge_Borg'].rolling(window=4, min_periods=1).mean()
        charge_hebdo['ACWR'] = charge_hebdo['Charge_Borg'] / charge_hebdo['Charge_Chronique']
        
        fig_acwr = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Barres de charge avec un rouge sombre transparent
        fig_acwr.add_trace(go.Bar(
            x=charge_hebdo['Semaine'], y=charge_hebdo['Charge_Borg'], 
            name="Charge Hebdo", 
            marker=dict(color='rgba(255, 75, 75, 0.4)', line=dict(color='#FF4B4B', width=1)),
            hovertemplate="Semaine %{x}<br>Charge: %{y}<extra></extra>"
        ), secondary_y=False)
        
        # Ligne de Ratio ACWR lissée (spline) avec marqueurs
        fig_acwr.add_trace(go.Scatter(
            x=charge_hebdo['Semaine'], y=charge_hebdo['ACWR'], 
            name="Ratio ACWR", 
            mode="lines+markers", 
            line=dict(color="#00F0FF", width=3, shape='spline'), # Cyan néon fluide
            marker=dict(size=8, color="#00F0FF", symbol='circle')
        ), secondary_y=True)
        
        # Zones de sécurité esthétiques
        fig_acwr.add_hrect(y0=0.8, y1=1.3, fillcolor="#00FF00", opacity=0.05, secondary_y=True, line_width=0)
        fig_acwr.add_hrect(y0=1.5, y1=3.0, fillcolor="#FF0000", opacity=0.05, secondary_y=True, line_width=0)
        
        # Design général ultra-clean
        fig_acwr.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", # Fond transparent
            height=400,
            margin=dict(l=0, r=0, t=30, b=0),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            hovermode="x unified"
        )
        fig_acwr.update_yaxes(showgrid=False, secondary_y=False)
        fig_acwr.update_yaxes(showgrid=True, gridcolor='rgba(255,255,255,0.1)', secondary_y=True)
        st.plotly_chart(fig_acwr, use_container_width=True)

        st.divider()

        # --- SECTION 3 : CONSEILS DU COACH (Basé sur Data) ---
        st.subheader("🗣️ Analyse Stratégique du Coach IA")
        col_c1, col_c2 = st.columns(2)
        
        with col_c1:
            ratio_actuel = charge_hebdo.iloc[-1]['ACWR'] if not charge_hebdo.empty else 1
            if ratio_actuel > 1.5:
                st.error("🚨 **SURENTRAÎNEMENT DÉTECTÉ :** Ton ratio ACWR a explosé. Tu augmentes ton volume trop vite. **Lève le pied cette semaine (Deload) !**")
            elif ratio_actuel < 0.8:
                st.warning("📉 **SOUS-ENTRAÎNEMENT :** Ta charge de travail baisse par rapport au mois dernier. Tu risques de perdre tes acquis.")
            else:
                st.success("✅ **PROGRESSION PARFAITE :** Ton ratio de charge est dans le 'Sweet Spot' (0.8 - 1.3). Continue cette surcharge progressive douce.")
                
        with col_c2:
            st.info(f"🤕 **Douleurs récentes signalées :** {douleurs_recentes}")
            if sommeil_moyen > 0 and sommeil_moyen < 7:
                st.warning(f"⚠️ Ton sommeil moyen ({sommeil_moyen:.1f}h) est un frein majeur à la récupération de tes tissus musculaires.")

        st.divider()

        # --- SECTION 4 : SURCHARGE PROGRESSIVE (Design Premium) ---
        st.subheader("📈 Surcharge Progressive par Exercice")
        
        liste_exos = [exo for exo in df_realise.iloc[:, 4].unique() if "Bilan" not in str(exo)]
        
        if liste_exos:
            exo_choisi = st.selectbox("Sélectionne un exercice pour analyser ta progression :", liste_exos)
            
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
elif page == "Coach IA & Programme":
    st.header("🛠️ Gestion du Programme")
    
    tab1, tab2 = st.tabs([" Saisie Rapide (Historique)", "🤖 Génération par l'IA"])

    # ---------------------------------------------------------
    # ONGLET 1 : SAISIE INTELLIGENTE BASÉE SUR TON HISTORIQUE
    # ---------------------------------------------------------
    with tab1:
        st.write("Ajoute un exercice ou une séance complète dans ton programme.")
        
        # --- NOUVEAUTÉ : VERROUILLAGE DE LA SEMAINE ---
        try:
            df = load_programme()
            liste_seances = df["Type_Seance"].dropna().unique().tolist()
            liste_exos = df["Exercice_WOD"].dropna().unique().tolist()
            
            # On cherche la semaine la plus avancée dans ton programme
            semaine_actuelle = int(df["Semaine"].max()) if not df.empty else 1
        except:
            liste_seances = []
            liste_exos = []
            semaine_actuelle = 1

        options_seances = ["-- Nouvelle séance --"] + liste_seances
        options_exos = ["-- Nouvel exercice --"] + liste_exos

        # LIGNE 1 : Le contexte (Semaine, Jour, Nom de la séance)
        col1, col2, col3 = st.columns(3)
        with col1:
            # On utilise "semaine_actuelle" comme minimum et valeur par défaut !
            semaine_proposee = semaine_actuelle + 1  # On propose toujours la semaine suivante
            semaine = st.number_input("Semaine n°", min_value=1, step=1, value=semaine_actuelle)
            
        with col2:
            jour = st.selectbox("Jour théorique", ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"])
        with col3:
            choix_seance = st.selectbox("Nom de la séance", options_seances)
            if choix_seance == "-- Nouvelle séance --":
                type_seance = st.text_input("📝 Nom (ex: Upper Body, Hyrox, Course)")
            else:
                type_seance = choix_seance

        st.divider()

        st.divider()

        # --- DUPLICATION AUTOMATIQUE DE LA SEMAINE PRÉCÉDENTE ---
        if type_seance and type_seance != "-- Nouvelle séance --":
            try:
                df_prog = load_programme()
                semaine_prec = semaine - 1
                df_modele = df_prog[
                    (df_prog["Semaine"] == semaine_prec) & 
                    (df_prog["Type_Seance"] == type_seance)
                ].copy()
                
                if not df_modele.empty:
                    st.info(f"📋 **{len(df_modele)} exercices** trouvés en Semaine {semaine_prec} pour {type_seance}")
                    
                    # --- PRÉPARATION DU TABLEAU ÉDITABLE ---
                    df_editable = df_modele[["Exercice_WOD", "Series_Cible", "Reps_Cible", "Poids_Cible_Kg"]].rename(columns={
                        "Exercice_WOD": "Exercice",
                        "Series_Cible": "Séries",
                        "Reps_Cible": "Reps",
                        "Poids_Cible_Kg": "Poids (kg)"
                    }).reset_index(drop=True)

                    # --- LA LIGNE MAGIQUE POUR FIXER L'ERREUR ---
                    # On force 'Reps' en texte pour que Streamlit accepte le TextColumn
                    df_editable["Reps"] = df_editable["Reps"].astype(str)
                    
                    st.caption("✏️ Modifie directement le tableau avant de dupliquer")
                    df_modifie = st.data_editor(
                        df_editable,
                        use_container_width=True,
                        hide_index=True,
                        num_rows="dynamic",
                        column_config={
                            "Exercice": st.column_config.TextColumn("Exercice", width="large"),
                            "Séries": st.column_config.NumberColumn("Séries", min_value=1, max_value=10, step=1),
                            "Reps": st.column_config.TextColumn("Reps"),
                            "Poids (kg)": st.column_config.NumberColumn("Poids (kg)", min_value=0.0, step=0.5),
                        }
                    )
                    
                    if st.button("⚡ Dupliquer cette séance modifiée dans la Semaine " + str(semaine), type="primary"):
                        lignes = []
                        for _, row in df_modifie.iterrows():
                            # On vérifie que la ligne n'est pas vide
                            if pd.notna(row["Exercice"]) and str(row["Exercice"]).strip() != "":
                                lignes.append([
                                    int(semaine),
                                    str(jour),
                                    str(type_seance),
                                    str(row["Exercice"]),
                                    int(row["Séries"]) if pd.notna(row["Séries"]) else 1,
                                    str(row["Reps"]),
                                    float(row["Poids (kg)"]) if pd.notna(row["Poids (kg)"]) else 0.0
                                ])
                        
                        if lignes:
                            try:
                                client = connect_sheets()
                                sheet = client.open("DB_Dynamic_Hybrid_Coach")
                                worksheet = sheet.worksheet("Programme_Theorique")
                                worksheet.append_rows(lignes)
                                load_programme.clear() # On vide le cache pour voir les changements
                                st.success(f"✅ {len(lignes)} exercices dupliqués en Semaine {semaine} !")
                                st.balloons()
                            except Exception as e:
                                st.error(f"Erreur lors de l'écriture : {e}")
                else:
                    st.caption(f"Aucun modèle trouvé en Semaine {semaine_prec} pour {type_seance}.")
            except Exception as e:
                st.caption(f"Impossible de charger le modèle : {e}")

        st.divider()

        # --- LE CERVEAU DYNAMIQUE ---

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
                    
                    # ✅ ON VIDE LA MÉMOIRE DE LA LECTURE SPÉCIFIQUEMENT
                    load_programme.clear()
                    
                    st.success(f"✅ Ajouté avec succès à ta semaine {semaine} !")
                    st.balloons()
                except Exception as e:
                    st.error(f"Erreur de connexion : {e}")

    # ---------------------------------------------------------
    # ONGLET 2 : LE COACH IA (DYNAMIQUE)
    # ---------------------------------------------------------
    with tab2:
        st.subheader("🧠 Générer une séance avec l'IA")
        
        # On affiche un petit rappel de la destination
        st.warning(f"📍 Destination : **Semaine {semaine} - {jour}**")
        
        # INITIALISATION DE LA MÉMOIRE (SESSION STATE)
        if "seance_ia_generee" not in st.session_state:
            st.session_state.seance_ia_generee = None
            
        # Récupération du dernier Check-in (si existant)
        df_checkin = load_historique_checkin()
        sommeil_defaut, energie_defaut, courbatures_defaut = 7.0, 7, "Aucune"
        if not df_checkin.empty:
            dernier_checkin = df_checkin.iloc[-1]
            try:
                sommeil_defaut = float(dernier_checkin.get("Heures_Sommeil", 7.0))
                energie_defaut = int(dernier_checkin.get("Niveau_Energie", 7))
                courbatures_defaut = str(dernier_checkin.get("Muscles_Douloureux", "Aucune"))
            except: pass

        st.info("💡 Les données ci-dessous sont basées sur ton dernier Check-in. Modifie-les si besoin.")
        
        col_ia1, col_ia2 = st.columns(2)
        with col_ia1:
            ia_sommeil = st.number_input("Sommeil (h)", min_value=0.0, max_value=12.0, value=sommeil_defaut, step=0.5)
            ia_energie = st.slider("Énergie (1-10)", 1, 10, energie_defaut)
        with col_ia2:
            ia_courbatures = st.text_input("Douleurs / Courbatures ?", value=courbatures_defaut)
            ia_objectif = st.selectbox("Type de séance voulu", ["Hyrox / WOD", "Renforcement Haut du corps", "Renforcement Bas du corps", "Cardio LISS (Zone 2)", "Récupération Active"])
        
        # BOUTON DE GÉNÉRATION
        if st.button("✨ Générer ma séance sur mesure", type="primary"):
            with st.spinner("Le coach réfléchit à ton programme... 🧠"):
                success, resultat = generer_seance_ia(ia_energie, ia_sommeil, ia_courbatures, ia_objectif)
                if success:
                    # On stocke le résultat dans la mémoire de la page !
                    st.session_state.seance_ia_generee = resultat
                    st.rerun() # On rafraîchit pour afficher la suite
                else:
                    st.error(resultat)
        
        # --- L'IA A FAIT UNE PROPOSITION : ON AFFICHE LES BOUTONS ---
        if st.session_state.seance_ia_generee:
            seance = st.session_state.seance_ia_generee
            st.divider()
            st.markdown(f"### 🎯 {seance.get('titre', 'Séance IA')}")
            st.info(f"🗣️ **Coach :** {seance.get('message', '')}")
            
            # On transforme le JSON des exercices en tableau Pandas
            df_exos = pd.DataFrame(seance.get("exercices", []))
            if not df_exos.empty:
                df_exos.columns = ["Exercice", "Séries", "Reps", "Poids (kg)"]
                st.dataframe(df_exos, use_container_width=True, hide_index=True)
            
            st.write(f"**Cette séance sera ajoutée à ton programme le {jour} de la Semaine {semaine}.**")
            col_action1, col_action2 = st.columns(2)
            
            with col_action1:
                if st.button("✅ L'accepter et l'ajouter"):
                    with st.spinner("Sauvegarde en cours..."):
                        # ON PASSE LES DEUX VARIABLES ICI
                        if sauvegarder_seance_ia_programme(seance.get('titre', 'Séance IA'), df_exos, semaine, jour):
                            st.success(f"✅ Séance ajoutée au {jour} de la Semaine {semaine} !")
                            st.session_state.seance_ia_generee = None 
                            st.cache_data.clear() 
                            st.balloons()
                        else:
                            st.error("Erreur lors de la sauvegarde.")
                            
            with col_action2:
                if st.button("🔄 Non, propose-moi autre chose"):
                    st.session_state.seance_ia_generee = None # On vide la mémoire
                    st.rerun() # Rafraîchissement automatique
