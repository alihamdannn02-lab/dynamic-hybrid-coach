"""Traductions FR / EN de l'interface principale."""

from __future__ import annotations

import streamlit as st

LANGS = ("FR", "EN")

T: dict[str, tuple[str, str]] = {
    # --- Navigation & coque ---
    "nav.today": ("Aujourd'hui", "Today"),
    "nav.training": ("Entraînement", "Training"),
    "nav.analyses": ("Analyses", "Analytics"),
    "nav.settings": ("Réglages", "Settings"),
    "app.tagline": ("De la montre à la décision du jour.", "From your watch to today's decision."),
    "app.footer": ("Conçu et développé par", "Designed and built by"),
    "demo.banner": (
        "Tu explores un **athlète simulé**. Connecte ta montre dans **Réglages › Garmin** pour voir tes propres données (elles restent dans ta session).",
        "You're exploring a **simulated athlete**. Connect your watch in **Settings › Garmin** to see your own data (it stays in your session).",
    ),
    "detail.fr_only": ("", "Detailed analyses are shown in French."),
    # --- Décision du jour ---
    "dec.title": ("Ma décision du jour", "Today's call"),
    "dec.rest": ("Récupération aujourd'hui", "Recover today"),
    "dec.rest.why": (
        "Ton corps envoie des signaux de fatigue. Une séance très facile (marche, vélo souple, mobilité) te fera progresser davantage qu'une séance dure.",
        "Your body is showing signs of fatigue. An easy session (walk, easy spin, mobility) will help you progress more than a hard one.",
    ),
    "dec.go": ("Feu vert pour une séance intense", "Green light for a hard session"),
    "dec.go.why": (
        "Tu es bien récupéré et ton risque est faible : c'est le bon jour pour du fractionné ou une séance de force.",
        "You're well recovered and your risk is low: a good day for intervals or a strength session.",
    ),
    "dec.easy": ("Séance facile, sans intensité", "Easy session, no intensity"),
    "dec.easy.sleep": (
        "Il te manque beaucoup de sommeil cette semaine : reste sur de l'endurance facile et couche-toi plus tôt ce soir.",
        "You're short on sleep this week: keep it easy and go to bed earlier tonight.",
    ),
    "dec.easy.why": (
        "Récupération correcte mais pas optimale : privilégie l'endurance tranquille (tu peux parler en courant).",
        "Recovery is fine but not optimal: keep it easy (conversational pace).",
    ),
    "dec.nodata": (
        "Pas encore de données : synchronise ta montre ou fais ton check-in.",
        "No data yet: sync your watch or do your check-in.",
    ),
    # --- Cartes ---
    "card.recovery": ("Récupération", "Recovery"),
    "card.sleep": ("Sommeil", "Sleep"),
    "card.risk": ("Risque de blessure", "Injury risk"),
    "card.fresh": ("Fraîcheur", "Freshness"),
    "card.why": ("Pourquoi ?", "Why?"),
    "rec.good": ("Bien récupéré", "Well recovered"),
    "rec.mid": ("Récupération moyenne", "Partly recovered"),
    "rec.low": ("Fatigué", "Fatigued"),
    "sleep.sub": ("par nuit (7 j) · manque {debt} h", "per night (7 d) · {debt} h short"),
    "risk.low": ("Faible", "Low"),
    "risk.mid": ("Modéré", "Moderate"),
    "risk.high": ("Élevé", "High"),
    "fresh.fresh": ("Frais", "Fresh"),
    "fresh.ok": ("Équilibré", "Balanced"),
    "fresh.tired": ("Chargé", "Loaded"),
    "fresh.very": ("Épuisé", "Exhausted"),
    "fresh.sub": ("{tsb} · fatigue vs forme de fond", "{tsb} · fatigue vs baseline fitness"),
    # --- Explications « Pourquoi ? » ---
    "why.recovery": (
        "Calculée chaque matin à partir de ton sommeil, ton énergie, ta fréquence cardiaque au repos et ta VFC (variabilité cardiaque), **comparés à tes propres moyennes** des 30 derniers jours.",
        "Computed every morning from your sleep, energy, resting heart rate and HRV (heart rate variability), **compared with your own 30-day averages**.",
    ),
    "why.sleep": (
        "Moyenne de tes 7 dernières nuits et heures manquantes par rapport à ton besoin ({need} h). Régularité du coucher : {reg}.",
        "Average of your last 7 nights and hours missing versus your need ({need} h). Bedtime regularity: {reg}.",
    ),
    "why.risk": (
        "Score sur 100 qui combine 6 signaux connus pour précéder les blessures : hausse brutale de charge, entraînement monotone, VFC basse, pouls au repos élevé, manque de sommeil, douleurs.",
        "A 0-100 score combining 6 signals known to precede injuries: sudden load increase, monotonous training, low HRV, raised resting heart rate, lack of sleep, pain.",
    ),
    "why.risk.none": ("Aucun signal d'alerte en ce moment.", "No warning signal right now."),
    "why.fresh": (
        "Différence entre ta forme de fond (6 dernières semaines) et ta fatigue récente (7 derniers jours). Négatif = tu accumules de la fatigue, positif = tu es reposé. Modèle de Banister.",
        "Difference between your baseline fitness (last 6 weeks) and recent fatigue (last 7 days). Negative = accumulating fatigue, positive = rested. Banister model.",
    ),
    "why.more": ("Voir le détail dans **Analyses**.", "See details in **Analytics**."),
    # --- Actions ---
    "act.sync": ("Synchroniser ma montre", "Sync my watch"),
    "act.connect": ("Connecter ma montre Garmin", "Connect my Garmin watch"),
    "act.checkin": ("Mon ressenti du jour", "How I feel today"),
    "act.synced": ("{n} nuit(s) et {a} activité(s) ajoutées.", "{n} night(s) and {a} activity(ies) added."),
    "act.uptodate": ("Déjà à jour.", "Already up to date."),
    "ck.energy": ("Énergie (1 = vidé, 10 = au top)", "Energy (1 = drained, 10 = great)"),
    "ck.pain": ("Douleurs", "Pain"),
    "ck.none": ("Aucune", "None"),
    "ck.manual": ("Sans montre : saisir mes valeurs", "No watch: enter my values"),
    "ck.sleep": ("Heures de sommeil", "Hours of sleep"),
    "ck.rhr": ("Pouls au repos (bpm)", "Resting heart rate (bpm)"),
    "ck.hrv": ("VFC (ms)", "HRV (ms)"),
    "ck.save": ("Enregistrer", "Save"),
    "ck.saved": ("Enregistré !", "Saved!"),
    "chart.title": ("Les 8 dernières semaines", "Last 8 weeks"),
    "chart.load": ("Charge d'entraînement", "Training load"),
    "chart.hrv": ("VFC (récupération)", "HRV (recovery)"),
    "chart.risk": ("Risque de blessure", "Injury risk"),
    "chart.caption": (
        "Quand la charge s'emballe, la VFC chute et le risque monte : l'app le repère avant la blessure.",
        "When load spikes, HRV drops and risk rises: the app spots it before injury happens.",
    ),
    # --- Pages sections ---
    "tr.session": ("Séance du jour", "Today's session"),
    "tr.coach": ("Coach IA", "AI coach"),
    "tr.plan": ("Programme", "Plan"),
    "an.load": ("Forme & charge", "Fitness & load"),
    "an.sleep": ("Sommeil & VFC", "Sleep & HRV"),
    "an.risk": ("Risque de blessure", "Injury risk"),
    "an.predict": ("Prédictions", "Predictions"),
    "an.brief": ("En bref", "In short"),
    "set.garmin": ("Garmin", "Garmin"),
    "set.profile": ("Profil", "Profile"),
    "set.access": ("Accès & données", "Access & data"),
    "set.method": ("Méthode & sources", "Method & sources"),
    "set.age": ("Âge", "Age"),
    "set.fcmax": ("FC max (0 = estimation automatique)", "Max HR (0 = automatic estimate)"),
    "set.fcmax.used": ("FC max utilisée : **{v} bpm**", "Max HR used: **{v} bpm**"),
    "set.need": ("Besoin de sommeil (h / nuit)", "Sleep need (h / night)"),
    "acc.demo": ("Mode démo : tu vois un athlète simulé.", "Demo mode: you're viewing a simulated athlete."),
    "acc.owner": ("Tu vois tes propres données.", "You're viewing your own data."),
    "acc.pwd": ("Mot de passe", "Password"),
    "acc.unlock": ("Accéder à mes données", "Open my data"),
    "acc.lock": ("Repasser en mode démo", "Back to demo mode"),
    "acc.bad": ("Mot de passe incorrect.", "Wrong password."),
    "acc.toggle": ("Mode démo (athlète simulé)", "Demo mode (simulated athlete)"),
    "acc.reset": ("Réinitialiser la démo", "Reset the demo"),
    "acc.undo": ("Annuler ma dernière séance", "Undo my last session"),
    "acc.refresh": ("Rafraîchir les données", "Refresh data"),
}


def lang() -> str:
    return st.session_state.get("lang", "FR")


def t(key: str, **kwargs) -> str:
    fr, en = T[key]
    text = en if lang() == "EN" else fr
    return text.format(**kwargs) if kwargs else text
