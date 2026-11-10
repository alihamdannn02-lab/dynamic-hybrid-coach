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


def test_gemini_client_targets_v1beta(monkeypatch):
    """Le mode JSON n'existe que sur v1beta : sans cela, chaque appel échoue (400)
    et l'app retombe silencieusement sur les règles."""
    from google import genai

    captured = {}

    class FakeClient:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(genai, "Client", FakeClient)
    Coach(api_key="test")._get_client()
    assert captured["http_options"] == {"api_version": "v1beta"}
