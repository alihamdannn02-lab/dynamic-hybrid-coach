# ⚡ Dynamic Hybrid Coach

**De la montre à la décision du jour.** Une application de science du sport qui connecte
Garmin, modélise la charge, la VFC et le sommeil, estime le risque de blessure et
**prédit** la récupération de l'athlète, avec une méthode publiée derrière chaque chiffre.

[![CI](https://github.com/alihamdannn02-lab/dynamic-hybrid-coach/actions/workflows/ci.yml/badge.svg)](https://github.com/alihamdannn02-lab/dynamic-hybrid-coach/actions/workflows/ci.yml)

## 🎯 Le problème
Les athlètes d'endurance croulent sous les données (montre, ressenti, séances) mais
manquent d'un outil qui les **relie** pour répondre chaque matin : *je pousse, je maintiens
ou je récupère ?* Et surtout : *qu'est-ce qui, dans mes données, explique cette réponse ?*

## 🚀 Ce que fait l'application

| Module | Ce qu'il apporte |
|---|---|
| 🏠 **Décision du jour** | Readiness, risque de blessure, forme (TSB), VFC et sommeil réunis en une recommandation argumentée. |
| 😴 **Sommeil & VFC** | Dette de sommeil, régularité des horaires, architecture (profond / REM), jetlag social. VFC analysée selon Plews/Buchheit : ln rMSSD, moyenne 7 j, plage normale personnelle, CV. Mesure de **ton** effet sommeil → VFC. |
| 🛡️ **Risque de blessure** | Indice explicable à 6 facteurs (ACWR EWMA, monotonie, VFC, FC repos, sommeil, douleurs). Chaque point est traçable jusqu'à sa cause, historisé jour par jour, limites assumées. |
| 🔮 **Prédictions** | Modèle personnel de la VFC de demain (ridge, **validation walk-forward**, erreur affichée face à une référence naïve) avec simulateur « et si je dors 6 h ? ». Planificateur d'affûtage par projection de Banister. Temps de course (Riegel vs prédicteur Garmin). |
| 📊 **Cockpit** | Performance Manager (CTL/ATL/TSB), volume par discipline, 1RM estimé, distribution d'intensité (polarisé / pyramidal). |
| ⌚ **Garmin Connect** | Connexion (MFA), synchronisation de 14 à 90 jours d'historique (nuits, phases, horaires, VFC, FC repos, Body Battery, stress, activités) en un clic. **Lecture seule**, garantie par un test. |
| 🧠 **Coach IA** | Séance générée par Google Gemini à partir de tous ces indicateurs (le risque ≥ 50 impose une récupération), lecture de photos de WOD. |

## 🔬 Rigueur
- **Méthodes publiées** : Banister, Foster, Gabbett, Williams, Plews, Buchheit, Bosquet, Riegel. Sources dans l'onglet *Méthodologie & sources*.
- **Prédictions honnêtes** : évaluation walk-forward sans fuite d'information du futur, comparée à une référence naïve. Le gain est affiché, même s'il est nul.
- **Limites explicites** : l'indice de risque est une aide à la décision, pas un diagnostic. Le débat sur l'ACWR (Impellizzeri 2020) est cité dans l'application.

## 🧪 Démo publique sécurisée
Avec le secret `APP_PASSWORD`, l'URL peut être partagée publiquement :
- les visiteurs arrivent sur un **athlète simulé** (12 semaines au modèle physiologique cohérent, avec un stage de surcharge qui fait chuter la VFC et monter le risque) ;
- chaque visiteur a sa propre base **en mémoire**. Il peut même connecter **sa** montre : ses données restent dans sa session et ne sont écrites nulle part ;
- le propriétaire déverrouille ses vraies données (Google Sheets) avec le mot de passe.

## 🛠️ Installation
Python **3.12+** requis.

```bash
pip install -r requirements.txt
streamlit run app.py
```

### Configuration (optionnelle)
Copie `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` :

| Clé | Rôle |
|---|---|
| `APP_PASSWORD` | Active la démo publique ; mot de passe d'accès à tes données. |
| `GEMINI_API_KEY` (`GEMINI_MODEL`) | Coach IA, NLP, lecture des photos de WOD (clé gratuite sur aistudio.google.com). Sans clé : règles physiologiques. |
| `GARMIN_TOKENS` *ou* `GARMIN_EMAIL` / `GARMIN_PASSWORD` | Connexion Garmin automatique (mode propriétaire uniquement). |
| `[gcp_service_account]`, `SPREADSHEET_NAME` | Stockage Google Sheets (sinon CSV local). Les onglets et nouvelles colonnes sont créés automatiquement. |

## 🗂️ Architecture
```
app.py                  # navigation, accès (démo / propriétaire)
coach/
  readiness.py          # readiness vs baseline personnelle
  training_load.py      # TSS (sRPE), CTL/ATL/TSB, ACWR, zones FC
  hrv.py                # analyse VFC (ln rMSSD, plage normale, CV)
  sleep.py              # dette, régularité, architecture, effet sur la VFC
  risk.py               # indice de risque de blessure explicable
  forecast.py           # modèle VFC walk-forward, planificateur d'affûtage, Riegel
  garmin.py             # connexion, MFA, historique, parseurs (lecture seule)
  ai.py                 # Gemini + repli par règles
  storage.py            # Google Sheets / CSV / mémoire (démo)
  demo.py               # athlète simulé physiologiquement cohérent
  ui/                   # thème et pages Streamlit
tests/                  # modèles, parseurs, flux Garmin simulé, chaque page
```

## ✅ Qualité
```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q
```
Les tests couvrent les modèles scientifiques, les parseurs Garmin, la connexion et le MFA
simulés, la garantie de lecture seule, l'isolement du mode démo et l'affichage de chaque
page. Ils tournent en intégration continue via GitHub Actions.

## 📈 Pistes
- Enregistrement des blessures réelles pour entraîner un vrai modèle prédictif de blessure.
- Synchronisation Strava (OAuth2) et envoi des séances générées vers la montre.

---
Conçu et développé par **Ali HAMDAN** · [LinkedIn](https://www.linkedin.com/in/alihamdan2002/)
