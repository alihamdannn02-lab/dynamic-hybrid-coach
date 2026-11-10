"""Jeu de données de démonstration réaliste (8 semaines de bloc hybride)."""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from . import schema

PLAN = {
    "Lundi": ("Renforcement PPG A", [("Squat goblet", 4, "8", 24), ("Soulevé de terre roumain", 3, "8", 50), ("Mollets sur step", 3, "15", 0)]),
    "Mardi": ("Course Fractionné VMA", [("10 x 400 m VMA (r=1 min)", 1, "45 min", 0)]),
    "Mercredi": ("Vélo Endurance Z2", [("Vélo continu Z2", 1, "75 min", 0)]),
    "Jeudi": ("Renforcement PPG B", [("Fentes bulgares", 3, "10", 12), ("Hip thrust", 4, "10", 60), ("Gainage dynamique", 3, "45 s", 0)]),
    "Vendredi": ("Repos", [("Mobilité", 1, "20 min", 0)]),
    "Samedi": ("Sortie Longue Endurance", [("Course Z2 vallonnée", 1, "100 min", 0)]),
    "Dimanche": ("Hyrox WOD", [("EMOM 30 : SkiErg / Wall balls / Burpees", 1, "45 min", 0)]),
}


def build(weeks: int = 8, age: int = 28, seed: int = 7, today: date | None = None) -> dict[str, list[list]]:
    rng = np.random.default_rng(seed)
    today = today or date.today()
    start = today - timedelta(days=weeks * 7 - 1)
    start -= timedelta(days=start.weekday())  # démarre un lundi

    programme, realise, checkin = [], [], []
    for w in range(1, weeks + 1):
        progression = 1 + 0.025 * (w - 1)
        for jour, (seance, exos) in PLAN.items():
            for nom, series, reps, poids in exos:
                programme.append([w, jour, seance, nom, series, reps, round(poids * progression, 1), "", "Démo"])

    d = start
    week = 1
    while d <= today:
        jour = schema.JOURS[d.weekday()]
        if d.weekday() == 0 and d != start:
            week += 1
        deload = week % 4 == 0
        hrv = rng.normal(64 if not deload else 70, 6)
        rhr = rng.normal(48 if not deload else 46, 2)
        sleep = float(np.clip(rng.normal(7.4, 0.7), 5.0, 9.5))
        energie = int(np.clip(round(rng.normal(7, 1.3)), 2, 10))
        checkin.append(
            [
                d.isoformat(),
                round(sleep, 1),
                int(hrv),
                int(rhr),
                energie,
                "Mollets" if rng.random() < 0.15 else "Aucun",
                age,
                int(np.clip(rng.normal(70, 12), 20, 100)),
                int(np.clip(rng.normal(78, 8), 40, 98)),
                "Démo",
            ]
        )

        seance, exos = PLAN[jour]
        dstr = d.isoformat()
        vol = 0.7 if deload else 1.0
        if seance == "Repos":
            realise.append([dstr, week, jour, seance, "Repos", 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, "Repos", 0, ""])
        elif seance.startswith("Renforcement"):
            for nom, series, reps, poids in exos:
                for s in range(1, series + 1):
                    rir = int(rng.integers(1, 4))
                    realise.append(
                        [
                            dstr,
                            week,
                            jour,
                            seance,
                            f"{nom} (Série {s})",
                            round(poids * (1 + 0.025 * (week - 1)), 1),
                            int(reps) if reps.isdigit() else 0,
                            rir,
                            10 - rir,
                            7,
                            0,
                            50,
                            0,
                            0,
                            0,
                            0,
                            0,
                            "Renforcement / PPG",
                            0,
                            "",
                        ]
                    )
        else:
            duree = int(int(exos[0][2].split()[0]) * vol)
            if "Vélo" in seance:
                sport, zones, dist, dplus, allure, rpe = "Cyclisme", [0.1, 0.8, 0.1, 0, 0], duree / 60 * 29, 300, "205 W", 5
            elif "Hyrox" in seance:
                sport, zones, dist, dplus, allure, rpe = "Cross-Training", [0.05, 0.2, 0.35, 0.3, 0.1], 0, 0, "", 8
            elif "VMA" in seance:
                sport, zones, dist, dplus, allure, rpe = "Course à pied", [0.25, 0.25, 0.1, 0.2, 0.2], duree / 60 * 11, 40, "4:45 min/km", 8
            else:
                sport, zones, dist, dplus, allure, rpe = "Trail / Ski Alpinisme", [0.1, 0.75, 0.15, 0, 0], duree / 60 * 10.5, 650, "5:40 min/km", 6
            zmin = [int(round(z * duree)) for z in zones]
            realise.append([dstr, week, jour, seance, "Bilan Endurance", 0, 0, 0, 0, rpe, round(dist, 1), duree, *zmin, sport, int(dplus * vol), allure, ""])
        d += timedelta(days=1)

    return {schema.PROGRAMME: programme, schema.REALISE: realise, schema.CHECKIN: checkin}


def seed(storage, **kwargs) -> None:
    data = build(**kwargs)
    if hasattr(storage, "reset"):
        storage.reset()
    for sheet, rows in data.items():
        storage.append(sheet, rows)
