"""Tests de fumée de l'interface : chaque page doit s'afficher sans exception,
avec une base vide puis avec les données de démonstration."""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

PAGES = ["home", "readiness", "session", "insights", "sleep_page", "risk_page", "predictions", "coach_ia", "garmin_page", "method"]


def _page_script(module: str, demo_mode: bool = False) -> None:  # exécuté par AppTest comme un script autonome
    import importlib

    import streamlit as st

    keys = ["home", "readiness", "session", "insights", "sleep", "risk", "predict", "coach", "garmin", "method"]
    pages = {k: st.Page(lambda: None, title=k, url_path=k) for k in keys}
    st.navigation(list(pages.values()), position="hidden")
    st.session_state["_pages"] = pages
    if demo_mode:
        st.session_state["demo_mode"] = True
    importlib.import_module(f"coach.ui.pages.{module}").render()


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCAL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GEMINI_API_KEY", "")
    monkeypatch.delenv("APP_PASSWORD", raising=False)
    from coach.ui import state

    state._owner_storage.clear()
    state.clear_cache()
    return tmp_path


def _run(module: str, demo_mode: bool = False) -> AppTest:
    at = AppTest.from_function(_page_script, kwargs={"module": module, "demo_mode": demo_mode}, default_timeout=60)
    at.run()
    return at


@pytest.mark.parametrize("module", PAGES)
def test_pages_empty_db(data_dir, module):
    at = _run(module)
    assert not at.exception, [e.value for e in at.exception]


@pytest.mark.parametrize("module", PAGES)
def test_pages_with_demo_data(data_dir, module):
    from coach import demo
    from coach.storage import LocalStorage

    demo.seed(LocalStorage(data_dir))
    at = _run(module)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]


@pytest.mark.parametrize("module", PAGES)
def test_pages_in_public_demo_mode(data_dir, module):
    at = _run(module, demo_mode=True)
    assert not at.exception, [e.value for e in at.exception]
    assert not at.error, [e.value for e in at.error]
    # le mode démo n'écrit jamais dans la base réelle
    assert not any(data_dir.iterdir())


def test_full_app_boots(data_dir):
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    assert not at.exception


def test_checkin_saves_row(data_dir):
    at = _run("readiness")
    at.button[-1].click().run()
    assert not at.exception
    from coach import schema
    from coach.storage import LocalStorage

    assert len(LocalStorage(data_dir).read(schema.CHECKIN)) == 1


def test_rule_based_session_generation(data_dir):
    from coach import demo
    from coach.storage import LocalStorage

    demo.seed(LocalStorage(data_dir))
    at = _run("coach_ia")
    gen = next(b for b in at.button if "Générer" in b.label)
    gen.click().run()
    assert not at.exception
    assert at.session_state["seance_ia"]["exercices"]


def test_garmin_page_imports_activities_once(data_dir, monkeypatch):
    import garminconnect
    from test_garmin import FakeGarmin, _FakeClient

    from coach import schema
    from coach.garmin import GarminSession
    from coach.storage import LocalStorage

    monkeypatch.setattr(garminconnect, "Garmin", FakeGarmin)
    session = GarminSession()
    session.login_with_tokens(_FakeClient().dumps())

    at = AppTest.from_function(_page_script, kwargs={"module": "garmin_page"}, default_timeout=60)
    at.session_state["garmin"] = session
    at.run()
    assert not at.exception
    next(b for b in at.button if "Charger" in b.label).click().run()
    imp = next(b for b in at.button if b.label.startswith("📥 Importer"))
    assert "2 activité" in imp.label
    imp.click().run()
    assert not at.exception, [e.value for e in at.exception]
    realise = LocalStorage(data_dir).read(schema.REALISE)
    assert sorted(realise["Activity_ID"]) == ["123456789", "2"]
    # Une seconde fois : tout est déjà importé
    imp = next(b for b in at.button if b.label.startswith("📥 Importer"))
    assert "0 activité" in imp.label and imp.disabled


def test_garmin_history_sync_in_demo_replaces_simulated_athlete(data_dir, monkeypatch):
    import garminconnect
    from test_garmin import FakeGarmin, _FakeClient

    from coach import schema

    monkeypatch.setattr(garminconnect, "Garmin", FakeGarmin)
    from coach.garmin import GarminSession

    session = GarminSession()
    session.login_with_tokens(_FakeClient().dumps())
    at = AppTest.from_function(_page_script, kwargs={"module": "garmin_page", "demo_mode": True}, default_timeout=60)
    at.session_state["garmin"] = session
    at.run()
    next(b for b in at.button if "Synchroniser" in b.label).click().run()
    assert not at.exception, [e.value for e in at.exception]
    mem = at.session_state["demo_storage"]
    checkins = mem.read(schema.CHECKIN)
    assert len(checkins) == 60 and set(checkins["Source"]) == {"Garmin"}
    assert checkins["Deep_Min"].notna().all()
    assert sorted(mem.read(schema.REALISE)["Activity_ID"]) == ["123456789", "2"]
    assert not any(data_dir.iterdir())  # rien d'écrit hors de la session


def test_password_protects_owner_data(data_dir, monkeypatch):
    monkeypatch.setenv("APP_PASSWORD", "s3cret")
    at = AppTest.from_file("../app.py", default_timeout=60)
    at.run()
    assert not at.exception
    pwd = next(t for t in at.text_input if t.placeholder == "Mot de passe")
    pwd.set_value("wrong")
    next(b for b in at.button if "Déverrouiller" in b.label).click().run()
    assert any("incorrect" in e.value for e in at.error)
    assert not at.session_state["owner_unlocked"] if "owner_unlocked" in at.session_state else True
    pwd = next(t for t in at.text_input if t.placeholder == "Mot de passe")
    pwd.set_value("s3cret")
    next(b for b in at.button if "Déverrouiller" in b.label).click().run()
    assert at.session_state["owner_unlocked"] is True
