# ⚡ Dynamic Hybrid Coach

Application de coaching **hybride** (endurance + préparation physique) pilotée par la donnée :
readiness matinale, modélisation de la charge (Banister / ACWR), coach IA (**Claude**, Anthropic) et
**synchronisation Garmin Connect**.

[![CI](https://github.com/alihamdannn02-lab/dynamic-hybrid-coach/actions/workflows/ci.yml/badge.svg)](https://github.com/alihamdannn02-lab/dynamic-hybrid-coach/actions/workflows/ci.yml)

## 🎯 Problématique
Les athlètes d'endurance croulent sous les données mais manquent d'outils simples pour relier
leur **charge d'entraînement** à leur **état de forme physiologique**, et décider chaque matin :
*je pousse, je maintiens ou je récupère ?*

## 🚀 Fonctionnalités

| Page | Ce qu'elle fait |
|---|---|
| ⚡ **Morning Readiness** | Check-in en 1 clic depuis **Garmin** (sommeil, VFC, FC repos, Body Battery, Training Readiness), par phrase libre (NLP) ou manuel. Score de readiness comparé à **ta baseline personnelle** (30 j). |
| 🏃 **Ma Séance du Jour** | Saisie endurance (zones FC en bpm calculées sur ta FC max), WOD (lecture de la **photo du tableau** par l'IA), PPG série par série avec suggestion de surcharge progressive. |
| 📊 **Cockpit Performance** | Performance Manager (CTL / ATL / TSB), **ACWR** et monotonie de Foster, volume par discipline, 1RM estimé (Epley + RIR), distribution d'intensité (polarisé / pyramidal), tendances VFC & FC repos. |
| 🧠 **Coach IA & Programme** | Génération de séance par **Claude** tenant compte du sommeil, des douleurs, de la readiness, du TSB, de l'ACWR et des données Garmin. Planificateur avec duplication de la semaine précédente. |
| ⌚ **Garmin Connect** | Connexion (MFA supporté), récupération du matin, **import des activités** (distance, durée, D+, allure/puissance, temps par zone, RPE) sans doublon. |

## ⌚ Intégration Garmin

Garmin réserve son API officielle aux entreprises partenaires. L'application utilise donc la
bibliothèque open-source [`garminconnect`](https://github.com/cyberjunky/python-garminconnect),
qui emploie le même protocole que l'app mobile Garmin Connect.

1. Ouvre la page **⌚ Garmin Connect** et connecte-toi (code MFA demandé si activé).
2. **Morning Readiness → « Importer ma nuit »** pré-remplit ton check-in.
3. **Garmin Connect → Activités** : coche les séances à importer ; elles alimentent aussitôt
   le Cockpit (charge, zones, volume). Chaque activité n'est importée qu'une fois (`Activity_ID`).

**Sécurité** : le mot de passe n'est jamais stocké. Seul un jeton de session est conservé en
mémoire, propre à ton navigateur. Pour éviter de te reconnecter (et les blocages de Garmin en
cas de connexions répétées), copie le jeton affiché dans *Session & déploiement* vers le secret
`GARMIN_TOKENS`. Ce jeton donne accès à ton compte : ne le commite jamais.

> Limite : bibliothèque non officielle — si Garmin modifie son protocole, une mise à jour de
> `garminconnect` peut être nécessaire (`pip install -U garminconnect`).

## 🧠 Coach IA (Claude)

L'IA s'appuie sur l'API Claude d'Anthropic (SDK `anthropic`, modèle `claude-opus-5-5` par défaut) :
- **sorties structurées** (JSON Schema) pour l'extraction du check-in et la génération de séance :
  la réponse est garantie conforme, sans parsing fragile ;
- **vision** pour transcrire la photo du tableau de WOD ;
- niveau d'effort adapté à chaque tâche (`low` pour l'extraction, `medium` pour la séance) ;
- repli automatique côté serveur si une requête est refusée (`fallbacks: "default"`).

Crée une clé sur [console.anthropic.com](https://console.anthropic.com/settings/keys) et ajoute-la
au secret `ANTHROPIC_API_KEY`. La facturation de l'API est indépendante de l'abonnement claude.ai.

## 🧬 Modèles physiologiques

- **Readiness** : sommeil (25 %), énergie (20 %), FC repos (25 %), VFC (30 %). VFC et FCR sont
  évaluées par rapport à la baseline personnelle dès 5 check-ins (normes de référence sinon).
- **Charge** : TSS estimé par la méthode sRPE de Foster, ramené à l'échelle TSS
  (`h × IF² × 100`, `IF ≈ 0,45 + 0,055 × RPE`).
- **Banister / Coggan** : CTL (τ = 42 j) et ATL (τ = 7 j) calculées **jour par jour** à partir
  de zéro, TSB = CTL − ATL de la veille.
- **ACWR** (Gabbett) : charge moyenne 7 j / 28 j, zone optimale 0,8 – 1,3, danger > 1,5.
- **Zones FC** : FC max de Tanaka (`208 − 0,7 × âge`) ou valeur saisie dans le profil.

## 🛠️ Installation

Python **3.12+** requis.

```bash
pip install -r requirements.txt
streamlit run app.py
```

Sans aucun secret, l'application démarre en **mode local** (CSV dans `./data`) : charge
8 semaines de données réalistes via *Mode démo* dans la barre latérale.

### Configuration (optionnelle)
Copie `.streamlit/secrets.toml.example` en `.streamlit/secrets.toml` :

| Clé | Rôle |
|---|---|
| `ANTHROPIC_API_KEY` (`CLAUDE_MODEL`, défaut `claude-opus-5-5`) | Coach IA, NLP, lecture des photos de WOD. Clé à créer sur console.anthropic.com. Sans clé : moteur de règles physiologiques. |
| `GARMIN_TOKENS` *ou* `GARMIN_EMAIL` / `GARMIN_PASSWORD` | Connexion Garmin automatique au démarrage. |
| `[gcp_service_account]`, `SPREADSHEET_NAME` | Stockage Google Sheets (onglets `Programme_Theorique`, `Historique_Realise`, `Historique_Checkin`, créés si absents). |

Les feuilles existantes restent compatibles : les colonnes sont lues par position et les
nouvelles colonnes (`Activity_ID`, `Body_Battery`, `Score_Sommeil`, `Source`) sont ajoutées
automatiquement à l'en-tête.

## 🧪 Qualité

```bash
pip install -r requirements-dev.txt
ruff check . && pytest -q
```

47 tests : modèles physiologiques, parseurs Garmin (sur des réponses API types), flux de
connexion Garmin + MFA simulé, extraction NLP, stockage, et tests de fumée de chaque page
Streamlit (base vide et données de démo). Exécutés en CI via GitHub Actions.

## 🗂️ Architecture

```
app.py                  # point d'entrée : navigation, barre latérale
coach/
  storage.py            # Google Sheets ↔ CSV local (même interface)
  schema.py             # schéma canonique des onglets
  readiness.py          # score de readiness + baseline personnelle
  training_load.py      # TSS, CTL/ATL/TSB, ACWR, zones FC
  ai.py                 # Claude (SDK anthropic, sorties structurées) + repli par règles
  garmin.py             # connexion, MFA, jetons, parseurs Garmin
  demo.py               # jeu de données de démonstration
  ui/                   # thème, état partagé, pages Streamlit
tests/
```

## 📈 Pistes V5
- Synchronisation Strava (OAuth2) et export des séances générées vers la montre (workouts Garmin).
- Modèle prédictif de blessure entraîné sur l'historique VFC / ACWR.

---
POC développé par **Ali HAMDAN** — [LinkedIn](https://www.linkedin.com/in/alihamdan2002/)
