"""Jeu de données de démonstration : 12 semaines d'un athlète hybride simulé.

Les données ne sont pas aléatoires « à plat » : elles suivent un modèle
physiologique simple pour que chaque analyse ait quelque chose de réel à montrer.

* la charge suit une périodisation (progression, décharge toutes les 4 semaines)
  avec un **stage de surcharge en semaine 7** et une reprise de charge en cours ;
* la VFC (ln rMSSD) réagit à la charge de la veille, à la fatigue accumulée
  (TSB) et à la durée de la nuit, avec un bruit autocorrélé ; la FC de repos
  évolue en miroir ;
* le sommeil a des horaires (couchers plus tardifs le week-end), des phases
  (profond, paradoxal, léger, éveils) et se dégrade sous forte charge ;
* les douleurs apparaissent plus souvent quand l'ACWR s'envole ;
* deux tests de 10 km alimentent le prédicteur de temps de course.
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from . import schema
from .training_load import estimate_tss

PLAN = {
    "Lundi": ("Renforcement PPG A", [("Squat goblet", 4, "8", 24), ("Soulevé de terre roumain", 3, "8", 50), ("Mollets sur step", 3, "15", 0)]),
    "Mardi": ("Course Fractionné VMA", [("10 x 400 m VMA (r=1 min)", 1, "50 min", 0)]),
    "Mercredi": ("Vélo Endurance Z2", [("Vélo continu Z2", 1, "80 min", 0)]),
    "Jeudi": ("Renforcement PPG B", [("Fentes bulgares", 3, "10", 12), ("Hip thrust", 4, "10", 60), ("Gainage dynamique", 3, "45 s", 0)]),
    "Vendredi": ("Repos", [("Mobilité", 1, "20 min", 0)]),
    "Samedi": ("Sortie Longue Endurance", [("Course Z2", 1, "100 min", 0)]),
    "Dimanche": ("Hyrox WOD", [("EMOM 30 : SkiErg / Wall balls / Burpees", 1, "50 min", 0)]),
}
# Multiplicateur de volume par semaine : progression, décharges (S4, S8), surcharge (S7).
VOLUME = [0.85, 0.95, 1.0, 0.65, 1.0, 1.05, 2.0, 0.6, 1.0, 1.08, 1.2, 1.3, 1.4]
TEST_WEEKS = {5: 46.5, 10: 45.2}  # semaine → temps (min) au test de 10 km
BASE_LN = 4.15  # ≈ 63 ms


def _hhmm(minutes: float) -> str:
    m = int(round(minutes)) % 1440
    return f"{m // 60:02d}:{m % 60:02d}"


def build(weeks: int = 12, age: int = 28, seed: int = 7, today: date | None = None) -> dict[str, list[list]]:
    rng = np.random.default_rng(seed)
    today = today or date.today()
    start = today - timedelta(days=weeks * 7 - 1)
    start -= timedelta(days=start.weekday())  # démarre un lundi

    programme = []
    for w in range(1, weeks + 1):
        progression = 1 + 0.025 * (w - 1)
        for jour, (seance, exos) in PLAN.items():
            for nom, series, reps, poids in exos:
                programme.append([w, jour, seance, nom, series, reps, round(poids * progression, 1), "", "Démo"])

    realise, checkin = [], []
    ctl = atl = 35.0
    acute = chronic = 50.0
    prev_tss, noise = 50.0, 0.0
    d, week = start, 1
    while d <= today:
        if d.weekday() == 0 and d != start:
            week += 1
        vol = VOLUME[(week - 1) % len(VOLUME)]
        overreach = vol >= 1.5
        jour = schema.JOURS[d.weekday()]
        weekend = d.weekday() >= 5

        # --- Nuit précédant ce matin -------------------------------------
        sleep = rng.normal(7.3, 0.55) + (0.5 if weekend else 0) + (0.3 if prev_tss > 90 else 0) - (0.8 if overreach else 0)
        sleep = float(np.clip(sleep, 5.0, 9.6))
        tsb = ctl - atl
        noise = 0.55 * noise + rng.normal(0, 0.045)
        ln = BASE_LN + 0.05 * (sleep - 7.3) - 0.0016 * (prev_tss - 55) + 0.0045 * tsb + noise
        hrv = float(np.exp(ln))
        rhr = 47 - 22 * (ln - BASE_LN) + rng.normal(0, 1.0)
        energie = int(np.clip(round(7 + 10 * (ln - BASE_LN) + rng.normal(0, 0.8)), 1, 10))
        bed = (23 * 60 + 5 if not weekend else 24 * 60 + 10) + rng.normal(0, 25 if not weekend else 30)
        awake = float(np.clip(rng.normal(24, 9), 5, 60))
        asleep = sleep * 60
        deep = asleep * np.clip(rng.normal(0.18 - (0.03 if overreach else 0), 0.025), 0.08, 0.3)
        rem = asleep * np.clip(rng.normal(0.22, 0.03), 0.12, 0.32)
        acwr = acute / chronic if chronic else 1.0
        p_pain = 0.03 + 0.6 * max(0.0, acwr - 1.15)
        pain = ("Mollets" if rng.random() < 0.75 else "Genoux") if rng.random() < p_pain else "Aucun"
        checkin.append(
            [
                d.isoformat(),
                round(sleep, 2),
                int(round(hrv)),
                int(round(rhr)),
                energie,
                pain,
                age,
                int(np.clip(68 + 160 * (ln - BASE_LN) + rng.normal(0, 6), 5, 100)),
                int(np.clip(55 + 7 * (sleep - 6) + 60 * (deep / asleep - 0.15) + rng.normal(0, 4), 30, 98)),
                "Démo",
                int(deep),
                int(asleep - deep - rem),
                int(rem),
                int(awake),
                _hhmm(bed),
                _hhmm(bed + asleep + awake),
                int(np.clip(28 - 90 * (ln - BASE_LN) + rng.normal(0, 4), 8, 80)),
            ]
        )

        # --- Séance du jour ---------------------------------------------
        seance, exos = PLAN[jour]
        dstr = d.isoformat()
        tss = 0.0
        if seance == "Repos" and overreach:  # stage : pas de jour de repos
            duree = 70
            realise.append([dstr, week, jour, "Footing stage", "Bilan Endurance", 0, 0, 0, 0, 6, round(duree / 60 * 10.4, 1), duree, 5, 55, 10, 0, 0, "Course à pied", 120, "5:46 min/km", ""])
            tss = estimate_tss(duree, 6)
        elif seance == "Repos":
            realise.append([dstr, week, jour, seance, "Repos", 0, 0, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, "Repos", 0, ""])
        elif seance.startswith("Renforcement"):
            duree = int(50 * vol)
            for nom, series, reps, poids in exos:
                for s in range(1, series + 1):
                    rir = int(rng.integers(1, 4))
                    charge = round(poids * (1 + 0.025 * (week - 1)), 1)
                    realise.append([dstr, week, jour, seance, f"{nom} (Série {s})", charge, int(reps) if reps.isdigit() else 0, rir, 10 - rir, 7, 0, duree, 0, 0, 0, 0, 0, "Renforcement / PPG", 0, ""])
            tss = estimate_tss(duree, 7)
        else:
            base_min = int(exos[0][2].split()[0])
            duree = int(base_min * vol)
            if seance.startswith("Sortie Longue") and week in TEST_WEEKS:
                t10 = TEST_WEEKS[week]
                sport, zones, dist, dplus, rpe, duree = "Course à pied", [0.05, 0.15, 0.2, 0.4, 0.2], 10.0, 35, 9, int(round(t10))
                allure = f"{int(t10 / 10)}:{int((t10 / 10) % 1 * 60):02d} min/km"
                seance_nom = "Test 10 km"
            elif "Vélo" in seance:
                sport, zones, dist, dplus, allure, rpe, seance_nom = "Cyclisme", [0.1, 0.8, 0.1, 0, 0], duree / 60 * 29, 300, "205 W", 5, seance
            elif "Hyrox" in seance:
                sport, zones, dist, dplus, allure, rpe, seance_nom = "Cross-Training", [0.05, 0.2, 0.35, 0.3, 0.1], 0, 0, "", 8, seance
            elif "VMA" in seance:
                sport, zones, dist, dplus, allure, rpe, seance_nom = "Course à pied", [0.25, 0.25, 0.1, 0.2, 0.2], duree / 60 * 11, 40, "5:27 min/km", 8, seance
            else:
                sport, zones, dist, dplus, allure, rpe, seance_nom = "Course à pied", [0.1, 0.75, 0.15, 0, 0], duree / 60 * 10.6, 150, "5:40 min/km", 6, seance
            zmin = [int(round(z * duree)) for z in zones]
            realise.append([dstr, week, jour, seance_nom, "Bilan Endurance", 0, 0, 0, 0, rpe, round(dist, 1), duree, *zmin, sport, int(dplus), allure, ""])
            tss = estimate_tss(duree, rpe)

        ctl += (tss - ctl) / 42
        atl += (tss - atl) / 7
        acute += (tss - acute) * 2 / 8
        chronic += (tss - chronic) * 2 / 29
        prev_tss = tss
        d += timedelta(days=1)

    return {schema.PROGRAMME: programme, schema.REALISE: realise, schema.CHECKIN: checkin}


def seed(storage, **kwargs) -> None:
    data = build(**kwargs)
    if hasattr(storage, "reset"):
        storage.reset()
    for sheet, rows in data.items():
        storage.append(sheet, rows)
