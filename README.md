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

Quatre pages, en français ou en anglais (bouton FR / EN) :

| Page | Ce qu'on y trouve |
|---|---|
| 🏠 **Aujourd'hui** | La décision du jour en langage simple, 4 indicateurs (récupération, sommeil, risque de blessure, fraîcheur) avec un bouton « Pourquoi ? » pour chacun, la synchronisation Garmin et le ressenti du jour en un clic. |
| 🏃 **Entraînement** | Séance du jour (endurance, WOD avec lecture de photo par l'IA, musculation série par série), Coach IA (Gemini), programme. |
| 📈 **Analyses** | Forme & charge (Banister, ACWR, disciplines, 1RM, intensité) · Sommeil & VFC (méthode Plews/Buchheit) · Risque de blessure (indice explicable à 6 facteurs) · Prédictions (VFC de demain validée en walk-forward, planificateur d'affûtage, temps de course). Chaque onglet commence par un résumé « En bref ». |
| ⚙️ **Réglages** | Connexion Garmin (lecture seule, MFA, historique 14-90 jours), profil, accès aux données, méthodologie & sources. |

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
app.py                  # navigation (4 pages), langue FR / EN
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
  ui/                   # thème, traductions (i18n.py), pages Streamlit
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
