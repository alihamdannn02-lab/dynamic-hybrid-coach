"""Coach IA (Google Gemini) avec repli déterministe hors-ligne.

* SDK officiel ``google-genai`` (l'ancien ``google-generativeai`` est déprécié).
* Sortie JSON forcée (``response_mime_type``) + parsing tolérant.
* Si aucune clé n'est configurée ou si l'appel échoue, des règles
  physiologiques simples prennent le relais : l'application reste utilisable.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from .config import DEFAULT_GEMINI_MODEL, get_secret

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------
class Coach:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else get_secret("GEMINI_API_KEY")
        self.model = model or get_secret("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
        self._client = None
        self.last_error: str | None = None

    @property
    def enabled(self) -> bool:
        return bool(self.api_key)

    def _get_client(self):
        if self._client is None:
            from google import genai

            # JSON mode n'est servi que par l'API v1beta (le SDK cible v1 par défaut).
            self._client = genai.Client(api_key=self.api_key, http_options={"api_version": "v1beta"})
        return self._client

    def generate_json(self, prompt: str, temperature: float = 0.4) -> dict | None:
        if not self.enabled:
            return None
        try:
            from google.genai import types

            resp = self._get_client().models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(response_mime_type="application/json", temperature=temperature),
            )
            self.last_error = None
            return parse_json(resp.text or "")
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            log.warning("Appel Gemini échoué : %s", exc)
            return None

    # --- Cas d'usage --------------------------------------------------------
    def extract_checkin(self, text: str, age: int) -> tuple[dict, str]:
        """Extrait sommeil / FCR / VFC / énergie d'une phrase libre. → (valeurs, source)."""
        prompt = f"""Tu es un assistant d'extraction de données physiologiques.
Texte de l'athlète (âge {age} ans) : \"\"\"{text}\"\"\"
Extrais uniquement les valeurs explicitement mentionnées et réponds en JSON :
{{"sommeil": float|null (heures), "fcr": int|null (bpm), "vfc": int|null (ms), "energie": int|null (1-10), "douleurs": [liste de zones parmi {MUSCLES}]}}
Convertis "7h30" en 7.5. Si l'athlète dit "en forme" sans chiffre, estime l'énergie (forme=8, fatigué=4, épuisé=2)."""
        data = self.generate_json(prompt, temperature=0.0)
        if isinstance(data, dict):
            return _clean_checkin(data), "ia"
        return extract_checkin_rules(text), "règles"

    def read_wod_image(self, image: bytes, mime_type: str) -> str | None:
        """Lit le tableau blanc d'une box (photo) et retourne le WOD en texte."""
        if not self.enabled:
            return None
        try:
            from google.genai import types

            resp = self._get_client().models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image, mime_type=mime_type),
                    "Transcris le WOD écrit sur ce tableau : un mouvement par ligne avec reps/distances/charges, précédé du format (AMRAP, EMOM, For Time…). Texte brut uniquement, sans commentaire.",
                ],
            )
            self.last_error = None
            return (resp.text or "").strip() or None
        except Exception as exc:  # noqa: BLE001
            self.last_error = str(exc)
            return None

    def generate_session(self, ctx: SessionContext) -> tuple[dict, str]:
        data = self.generate_json(build_session_prompt(ctx), temperature=0.6)
        if isinstance(data, dict) and isinstance(data.get("exercices"), list) and data["exercices"]:
            return normalize_session(data), "ia"
        return rule_based_session(ctx), "règles"


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------
def parse_json(text: str) -> dict | None:
    """Parse une réponse JSON, éventuellement entourée de balises Markdown."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return None
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return data if isinstance(data, dict) else None


MUSCLES = [
    "Épaules",
    "Pectoraux",
    "Biceps",
    "Triceps",
    "Abdominaux",
    "Haut du dos",
    "Bas du dos (Lombaires)",
    "Fessiers",
    "Quadriceps",
    "Ischios",
    "Genoux",
    "Mollets",
]

_MUSCLE_KEYWORDS = {
    "épaule": "Épaules",
    "epaule": "Épaules",
    "pec": "Pectoraux",
    "biceps": "Biceps",
    "triceps": "Triceps",
    "abdo": "Abdominaux",
    "haut du dos": "Haut du dos",
    "trapèze": "Haut du dos",
    "lombaire": "Bas du dos (Lombaires)",
    "bas du dos": "Bas du dos (Lombaires)",
    "fessier": "Fessiers",
    "quadri": "Quadriceps",
    "cuisse": "Quadriceps",
    "ischio": "Ischios",
    "genou": "Genoux",
    "mollet": "Mollets",
}


def _clean_checkin(data: dict) -> dict:
    def num(key, cast, lo, hi):
        try:
            v = cast(float(str(data.get(key)).replace(",", ".")))
        except (TypeError, ValueError):
            return None
        return v if lo <= v <= hi else None

    douleurs = [m for m in (data.get("douleurs") or []) if m in MUSCLES]
    return {
        "sommeil": num("sommeil", float, 0, 14),
        "fcr": num("fcr", int, 25, 120),
        "vfc": num("vfc", int, 5, 250),
        "energie": num("energie", int, 1, 10),
        "douleurs": douleurs,
    }


def extract_checkin_rules(text: str) -> dict:
    """Extraction par expressions régulières (repli sans IA)."""
    t = text.lower().replace(",", ".")
    out: dict = {"sommeil": None, "fcr": None, "vfc": None, "energie": None, "douleurs": []}

    m = re.search(r"(\d{1,2})\s*h\s*(\d{2})?", t)
    if m:
        h = int(m.group(1)) + (int(m.group(2)) / 60 if m.group(2) else 0)
        if 0 < h <= 14:
            out["sommeil"] = round(h, 2)
    m = re.search(r"(?:vfc|hrv)\D{0,12}(\d{2,3})", t)
    if m:
        out["vfc"] = int(m.group(1))
    m = re.search(r"(?<![a-z])(?:fc\s*(?:de\s*)?repos|fcr|fc|rhr|pouls)(?!\s*max)\D{0,12}(\d{2,3})", t)
    if m:
        out["fcr"] = int(m.group(1))
    m = re.search(r"(?:énergie|energie|forme)\D{0,12}(\d{1,2})\s*(?:/\s*10)?", t)
    if m and 1 <= int(m.group(1)) <= 10:
        out["energie"] = int(m.group(1))
    elif any(w in t for w in ("épuisé", "epuise", "crevé", "creve", "lessivé")):
        out["energie"] = 2
    elif any(w in t for w in ("fatigué", "fatigue", "bof")):
        out["energie"] = 4
    elif any(w in t for w in ("pleine forme", "en forme", "au top", "frais")):
        out["energie"] = 8
    out["douleurs"] = sorted({m for k, m in _MUSCLE_KEYWORDS.items() if k in t}, key=MUSCLES.index)
    return out


# ---------------------------------------------------------------------------
# Génération de séance
# ---------------------------------------------------------------------------
@dataclass
class SessionContext:
    sommeil: float
    energie: int
    douleurs: str
    objectif: str
    readiness: int | None = None
    tsb: float | None = None
    acwr: float | None = None
    vfc_status: str | None = None
    body_battery: int | None = None
    risk: int | None = None
    risk_drivers: str = ""
    sleep_debt: float | None = None
    recent: str = ""


def build_session_prompt(ctx: SessionContext) -> str:
    extras = []
    if ctx.readiness is not None:
        extras.append(f"Readiness score : {ctx.readiness}/100")
    if ctx.tsb is not None:
        extras.append(f"Forme (TSB Banister) : {ctx.tsb:.0f}")
    if ctx.acwr is not None:
        extras.append(f"ACWR (charge aiguë/chronique) : {ctx.acwr:.2f}")
    if ctx.vfc_status:
        extras.append(f"Statut VFC Garmin : {ctx.vfc_status}")
    if ctx.body_battery is not None:
        extras.append(f"Body Battery Garmin : {ctx.body_battery}/100")
    if ctx.risk is not None:
        extras.append(f"Indice de risque de blessure : {ctx.risk}/100" + (f" (facteurs : {ctx.risk_drivers})" if ctx.risk_drivers else ""))
    if ctx.sleep_debt is not None:
        extras.append(f"Dette de sommeil sur 7 jours : {ctx.sleep_debt:.1f} h")
    if ctx.recent:
        extras.append(f"Séances récentes : {ctx.recent}")
    contexte = "\n".join(f"- {e}" for e in extras) or "- (pas d'historique)"

    return f"""Tu es un coach expert en physiologie de l'endurance et en entraînement hybride (triathlon, trail, cyclisme, Hyrox).

État de l'athlète ce matin :
- Sommeil : {ctx.sommeil} h
- Énergie perçue : {ctx.energie}/10
- Douleurs localisées : {ctx.douleurs or "Aucune"}
- Objectif souhaité : {ctx.objectif}
Indicateurs de charge :
{contexte}

Règles strictes :
1. Énergie < 5, sommeil < 6 h, readiness < 50, TSB < -30, ACWR > 1.5 ou risque de blessure ≥ 50 → impose une récupération active ou du Z1/LISS, quel que soit l'objectif, et explique pourquoi.
2. Douleurs aux membres inférieurs (mollets, genoux, ischios) → privilégie le vélo ou la natation plutôt que la course à pied.
3. Objectif de renforcement → mouvements de PPG spécifiques à l'endurance (squat excentrique, soulevé de terre partiel, mollets sur step, gainage dynamique…).
4. Pour un bloc cardio, mets la durée en minutes dans "reps" (ex : "20 min Z2") et 1 dans "series".

Réponds STRICTEMENT en JSON :
{{"titre": "Nom de la séance", "message": "Analyse physiologique courte et encouragement (3 phrases max)", "exercices": [{{"nom": "…", "series": 3, "reps": "10", "poids": 0}}]}}"""


def normalize_session(data: dict) -> dict:
    exos = []
    for e in data.get("exercices") or []:
        if not isinstance(e, dict):
            continue
        try:
            series = max(1, int(float(e.get("series") or 1)))
        except (TypeError, ValueError):
            series = 1
        try:
            poids = float(str(e.get("poids") or 0).replace(",", "."))
        except (TypeError, ValueError):
            poids = 0.0
        exos.append({"Exercice": str(e.get("nom") or "Bloc"), "Séries": series, "Reps": str(e.get("reps") or ""), "Poids (kg)": poids})
    return {"titre": str(data.get("titre") or "Séance IA"), "message": str(data.get("message") or ""), "exercices": exos}


def must_recover(ctx: SessionContext) -> bool:
    return ctx.energie < 5 or ctx.sommeil < 6 or (ctx.readiness is not None and ctx.readiness < 50) or (ctx.tsb is not None and ctx.tsb < -30) or (ctx.acwr is not None and ctx.acwr > 1.5)


def rule_based_session(ctx: SessionContext) -> dict:
    """Bibliothèque de séances types, sélectionnées selon l'état de forme."""
    lower_pain = any(k in (ctx.douleurs or "").lower() for k in ("mollet", "genou", "ischio", "quadri"))
    obj = ctx.objectif.lower()

    if must_recover(ctx):
        cardio = "Vélo souple Z1 (cadence > 90 rpm)" if lower_pain or "course" not in obj else "Footing très lent Z1"
        return normalize_session(
            {
                "titre": "Récupération active (Z1 / LISS)",
                "message": "Tes indicateurs signalent une fatigue : on protège l'adaptation. Séance très facile, la qualité reviendra quand le corps sera prêt.",
                "exercices": [
                    {"nom": cardio, "series": 1, "reps": "30 min Z1", "poids": 0},
                    {"nom": "Mobilité hanches & chevilles", "series": 2, "reps": "8 min", "poids": 0},
                    {"nom": "Respiration diaphragmatique", "series": 1, "reps": "5 min", "poids": 0},
                ],
            }
        )
    if "renforcement" in obj or "ppg" in obj or "force" in obj:
        return normalize_session(
            {
                "titre": "Force sous-maximale PPG — prévention",
                "message": "Bonne disponibilité : on construit la robustesse articulaire et tendineuse, clé de la prévention des blessures en endurance.",
                "exercices": [
                    {"nom": "Squat goblet tempo 3-1-1", "series": 4, "reps": "8", "poids": 20},
                    {"nom": "Soulevé de terre roumain", "series": 3, "reps": "8", "poids": 40},
                    {"nom": "Fentes bulgares", "series": 3, "reps": "10/côté", "poids": 10},
                    {"nom": "Mollets excentriques sur step", "series": 3, "reps": "12", "poids": 0},
                    {"nom": "Gainage dynamique (dead bug)", "series": 3, "reps": "45 s", "poids": 0},
                ],
            }
        )
    if "hyrox" in obj or "cross" in obj:
        return normalize_session(
            {
                "titre": "Conditioning Hyrox — EMOM 30",
                "message": "Tu es prêt pour de l'intensité : travail mixte cardio/force, garde une allure régulière plutôt qu'un départ explosif.",
                "exercices": [
                    {"nom": "Échauffement rameur Z2", "series": 1, "reps": "10 min", "poids": 0},
                    {"nom": "EMOM : 250 m SkiErg / 12 Wall balls / 10 Burpees broad jump", "series": 10, "reps": "3 min", "poids": 6},
                    {"nom": "Retour au calme vélo Z1", "series": 1, "reps": "10 min", "poids": 0},
                ],
            }
        )
    if "fractionné" in obj or "vma" in obj or "pma" in obj or "seuil" in obj:
        support = "Vélo" if lower_pain or "vélo" in obj else "Course"
        return normalize_session(
            {
                "titre": f"{support} — Intervalles au seuil",
                "message": "Feu vert pour la qualité. Le travail au seuil repousse ta capacité à tenir des allures soutenues.",
                "exercices": [
                    {"nom": f"Échauffement {support.lower()} progressif Z1→Z2", "series": 1, "reps": "15 min", "poids": 0},
                    {"nom": f"{support} au seuil (Z4), récup 2 min Z1", "series": 4, "reps": "6 min Z4", "poids": 0},
                    {"nom": "Retour au calme Z1", "series": 1, "reps": "10 min", "poids": 0},
                ],
            }
        )
    if "natation" in obj:
        return normalize_session(
            {
                "titre": "Natation — Technique & aérobie",
                "message": "Séance à faible impact : idéale pour développer l'aérobie tout en soulageant les articulations.",
                "exercices": [
                    {"nom": "Échauffement crawl souple", "series": 1, "reps": "400 m", "poids": 0},
                    {"nom": "Éducatifs (rattrapé, 3 temps)", "series": 4, "reps": "50 m", "poids": 0},
                    {"nom": "Crawl aérobie Z2, récup 20 s", "series": 6, "reps": "200 m", "poids": 0},
                    {"nom": "Retour au calme dos", "series": 1, "reps": "200 m", "poids": 0},
                ],
            }
        )
    support = "Vélo" if lower_pain or "vélo" in obj else "Course"
    return normalize_session(
        {
            "titre": f"{support} — Endurance fondamentale Z2",
            "message": "Constantes correctes : on capitalise sur le volume aérobie, fondation de toute performance en endurance.",
            "exercices": [
                {"nom": f"{support} continu en Z2 (aisance respiratoire)", "series": 1, "reps": "60 min Z2", "poids": 0},
                {"nom": "Lignes droites / accélérations progressives", "series": 4, "reps": "20 s", "poids": 0},
            ],
        }
    )
