"""Schéma canonique des onglets de la base (Google Sheets ou CSV local).

Les feuilles historiques de l'utilisateur peuvent avoir des en-têtes légèrement
différents : on normalise donc **par position**, ce qui reproduit le
comportement historique (accès par ``iloc``) tout en exposant des noms clairs.
"""

from __future__ import annotations

import pandas as pd

PROGRAMME = "Programme_Theorique"
REALISE = "Historique_Realise"
CHECKIN = "Historique_Checkin"

PROGRAMME_COLUMNS = [
    "Semaine",
    "Jour",
    "Type_Seance",
    "Exercice_WOD",
    "Series_Cible",
    "Reps_Cible",
    "Poids_Cible_Kg",
    "Notes",
    "Source",
]

REALISE_COLUMNS = [
    "Date",
    "Semaine",
    "Jour",
    "Type_Seance",
    "Exercice",
    "Poids_Reel_Kg",
    "Reps_Reelles",
    "RIR",
    "RPE_Serie",
    "Session_RPE",
    "Distance_Km",
    "Duree_Min",
    "Z1_Min",
    "Z2_Min",
    "Z3_Min",
    "Z4_Min",
    "Z5_Min",
    "Sport_Discipline",
    "Denivele_M",
    "Allure_Puissance",
    "Activity_ID",
]

CHECKIN_COLUMNS = [
    "Date",
    "Heures_Sommeil",
    "VFC",
    "FC_Repos",
    "Niveau_Energie",
    "Muscles_Douloureux",
    "Age",
    "Body_Battery",
    "Score_Sommeil",
    "Source",
]

COLUMNS = {
    PROGRAMME: PROGRAMME_COLUMNS,
    REALISE: REALISE_COLUMNS,
    CHECKIN: CHECKIN_COLUMNS,
}

NUMERIC = {
    PROGRAMME: ["Semaine", "Series_Cible", "Poids_Cible_Kg"],
    REALISE: [
        "Semaine",
        "Poids_Reel_Kg",
        "Reps_Reelles",
        "RIR",
        "RPE_Serie",
        "Session_RPE",
        "Distance_Km",
        "Duree_Min",
        "Z1_Min",
        "Z2_Min",
        "Z3_Min",
        "Z4_Min",
        "Z5_Min",
        "Denivele_M",
    ],
    CHECKIN: ["Heures_Sommeil", "VFC", "FC_Repos", "Niveau_Energie", "Age", "Body_Battery", "Score_Sommeil"],
}

JOURS = ["Lundi", "Mardi", "Mercredi", "Jeudi", "Vendredi", "Samedi", "Dimanche"]


def jour_fr(d) -> str:
    """Nom du jour en français, indépendant de la locale système."""
    return JOURS[pd.Timestamp(d).weekday()]


def _to_number(series: pd.Series) -> pd.Series:
    # Google Sheets en locale FR renvoie parfois "7,5".
    cleaned = series.astype(str).str.replace(",", ".", regex=False).str.strip()
    return pd.to_numeric(cleaned, errors="coerce")


def normalize(sheet: str, rows: list[list]) -> pd.DataFrame:
    """Construit un DataFrame canonique à partir des lignes brutes (sans en-tête)."""
    columns = COLUMNS[sheet]
    width = len(columns)
    padded = [(list(r) + [""] * width)[:width] for r in rows if any(str(c).strip() for c in r)]
    df = pd.DataFrame(padded, columns=columns)
    for col in NUMERIC[sheet]:
        df[col] = _to_number(df[col])
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.dropna(subset=["Date"])
    return df.reset_index(drop=True)


def pad_row(sheet: str, row: list) -> list:
    """Complète une ligne avec des cellules vides pour couvrir tout le schéma."""
    width = len(COLUMNS[sheet])
    return (list(row) + [""] * width)[:width]
