
# ⚡ Dynamic - Athlete System

Application de suivi de performance et de coaching hybride basée sur l'IA (Gemini).

## 🎯 Problématique
Les athlètes d'endurance font face à une surcharge d'informations mais manquent d'outils simples pour corréler leur charge d'entraînement (TSS) avec leur état de forme physiologique (Readiness).

## 🚀 Fonctionnalités
- **Check-in NLP :** Saisie intelligente de l'état de forme (Sommeil, VFC, Énergie) par langage naturel.
- **Coaching IA :** Génération de séances personnalisées en fonction des douleurs et de l'énergie.
- **Analytics :** Visualisation de la charge via le modèle de Banister (Fitness/Fatigue/Forme).
- **Suivi PPG :** Suivi de surcharge progressive pour la prévention des blessures.

## 🛠️ Stack Technique
- **Frontend/App :** Streamlit
- **Backend/Data :** Python, Pandas, Numpy
- **IA :** Google Gemini API (Génératif)
- **Data Storage :** Google Sheets API
- **DataViz :** Plotly

## 📈 Axes d'amélioration (Vision V2)
- Intégration OAuth2 via Strava/Garmin API pour automatisation.
- Modèle ML de prédiction de blessures basé sur l'historique de la VFC.
