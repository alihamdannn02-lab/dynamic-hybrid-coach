from coach.ai import (
    Coach,
    SessionContext,
    extract_checkin_rules,
    must_recover,
    normalize_session,
    parse_json,
    rule_based_session,
)


def test_parse_json_variants():
    assert parse_json('{"a": 1}') == {"a": 1}
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Voici :\n{"a": {"b": 2}}\nBonne séance') == {"a": {"b": 2}}
    assert parse_json("pas de json") is None
    assert parse_json("[1, 2]") is None


def test_extract_checkin_rules():
    out = extract_checkin_rules("J'ai dormi 7h30, ma VFC est à 65, FC repos 44, je suis en forme mais j'ai mal aux mollets et au genou")
    assert out["sommeil"] == 7.5
    assert out["vfc"] == 65
    assert out["fcr"] == 44
    assert out["energie"] == 8
    assert out["douleurs"] == ["Genoux", "Mollets"]


def test_extract_checkin_rules_vfc_before_fc():
    out = extract_checkin_rules("VFC 58, FC 51, énergie 6/10, nuit de 6h")
    assert out["vfc"] == 58 and out["fcr"] == 51 and out["energie"] == 6 and out["sommeil"] == 6


def test_coach_without_key_falls_back_to_rules():
    coach = Coach(api_key="")
    assert not coach.enabled
    values, source = coach.extract_checkin("dormi 8h, fatigué", 30)
    assert source == "règles" and values["sommeil"] == 8 and values["energie"] == 4
    seance, source = coach.generate_session(SessionContext(sommeil=8, energie=8, douleurs="", objectif="Renforcement : Force maximale"))
    assert source == "règles" and seance["exercices"]


def test_recovery_is_forced_when_fatigued():
    ctx = SessionContext(sommeil=5, energie=8, douleurs="", objectif="Course : Fractionné / VMA")
    assert must_recover(ctx)
    assert "Récupération" in rule_based_session(ctx)["titre"]
    assert must_recover(SessionContext(sommeil=8, energie=8, douleurs="", objectif="x", acwr=1.6))
    assert not must_recover(SessionContext(sommeil=8, energie=8, douleurs="", objectif="x", tsb=-5, acwr=1.0))


def test_lower_limb_pain_switches_to_bike():
    ctx = SessionContext(sommeil=8, energie=8, douleurs="Mollets", objectif="Course : Fractionné / VMA")
    assert rule_based_session(ctx)["titre"].startswith("Vélo")


def test_normalize_session_is_tolerant():
    s = normalize_session({"exercices": [{"nom": "Squat", "series": "4", "reps": 8, "poids": "40,5"}, {"nom": "X", "series": None}, "junk"]})
    assert s["titre"] == "Séance IA"
    assert s["exercices"][0] == {"Exercice": "Squat", "Séries": 4, "Reps": "8", "Poids (kg)": 40.5}
    assert s["exercices"][1]["Séries"] == 1
    assert len(s["exercices"]) == 2


# ---------------------------------------------------------------------------
# Intégration Claude (client simulé : aucune requête réseau, aucun coût)
# ---------------------------------------------------------------------------
import json  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from coach.ai import CHECKIN_SCHEMA, SESSION_SCHEMA  # noqa: E402


class FakeMessages:
    def __init__(self, text="", stop_reason="end_turn", exc=None):
        self.text, self.stop_reason, self.exc, self.calls = text, stop_reason, exc, []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return SimpleNamespace(stop_reason=self.stop_reason, content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=self.text)])


def _coach(messages: FakeMessages) -> Coach:
    coach = Coach(api_key="sk-test", model="claude-opus-5-5")
    coach._client = SimpleNamespace(beta=SimpleNamespace(messages=messages))
    return coach


def test_claude_checkin_uses_structured_output():
    fake = FakeMessages(json.dumps({"sommeil": 7.5, "fcr": 44, "vfc": 68, "energie": 8, "douleurs": ["Mollets"]}))
    values, source = _coach(fake).extract_checkin("J'ai dormi 7h30…", 30)
    assert source == "ia"
    assert values == {"sommeil": 7.5, "fcr": 44, "vfc": 68, "energie": 8, "douleurs": ["Mollets"]}
    call = fake.calls[0]
    assert call["model"] == "claude-opus-5-5"
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": CHECKIN_SCHEMA}
    assert call["output_config"]["effort"] == "low"
    assert call["fallbacks"] == "default"
    assert "temperature" not in call and "thinking" not in call


def test_claude_session_generation():
    payload = {"titre": "Seuil vélo", "message": "Go.", "exercices": [{"nom": "4x6 min Z4", "series": 4, "reps": "6 min", "poids": 0}]}
    fake = FakeMessages(json.dumps(payload))
    seance, source = _coach(fake).generate_session(SessionContext(sommeil=8, energie=8, douleurs="", objectif="Vélo : PMA / Seuil", tsb=-5.0, acwr=1.1))
    assert source == "ia" and seance["titre"] == "Seuil vélo"
    assert fake.calls[0]["output_config"]["format"]["schema"] == SESSION_SCHEMA
    assert "ACWR" in fake.calls[0]["messages"][0]["content"]


def test_claude_refusal_or_error_falls_back_to_rules():
    coach = _coach(FakeMessages(stop_reason="refusal"))
    seance, source = coach.generate_session(SessionContext(sommeil=8, energie=8, douleurs="", objectif="Natation : Technique & aérobie"))
    assert source == "règles" and seance["exercices"] and "refusée" in coach.last_error

    import anthropic

    coach = _coach(FakeMessages(exc=anthropic.APIConnectionError(request=None)))
    values, source = coach.extract_checkin("dormi 6h", 30)
    assert source == "règles" and values["sommeil"] == 6 and "réseau" in coach.last_error


def test_claude_reads_wod_photo():
    fake = FakeMessages("For Time\n1000 m Run\n50 Wall Balls 9 kg\n")
    text = _coach(fake).read_wod_image(b"\x89PNG...", "image/png")
    assert text == "For Time\n1000 m Run\n50 Wall Balls 9 kg"
    image_block = fake.calls[0]["messages"][0]["content"][0]
    assert image_block["type"] == "image" and image_block["source"]["media_type"] == "image/png"
