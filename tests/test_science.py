"""Tests des modèles scientifiques : VFC, sommeil, risque de blessure, prédictions."""

import numpy as np
import pandas as pd
import pytest

from coach import demo, forecast, hrv, risk, schema, sleep
from coach import training_load as tl
from coach.storage import MemoryStorage


def _checkins(vfc, sleep_h=7.5, rhr=48, pains=None, start="2026-01-01", bed="23:00", wake="07:00"):
    n = len(vfc)
    rows = []
    for i in range(n):
        s = sleep_h[i] if isinstance(sleep_h, list | np.ndarray) else sleep_h
        r = rhr[i] if isinstance(rhr, list | np.ndarray) else rhr
        p = pains[i] if pains else "Aucun"
        d = (pd.Timestamp(start) + pd.Timedelta(days=i)).strftime("%Y-%m-%d")
        b = bed[i] if isinstance(bed, list) else bed
        rows.append([d, s, vfc[i], r, 7, p, 30, "", "", "Test", 80, 250, 100, 20, b, wake])
    return schema.normalize(schema.CHECKIN, rows)


# --- VFC -----------------------------------------------------------------------
def test_hrv_status_detects_suppression_against_personal_range():
    rng = np.random.default_rng(0)
    vfc = list(np.exp(rng.normal(np.log(65), 0.05, 50))) + [45] * 7
    status = hrv.hrv_status(hrv.hrv_trend(_checkins([round(v) for v in vfc])))
    assert status.status == "basse" and status.vfc7 < status.lower


def test_hrv_status_stable_and_needs_baseline():
    rng = np.random.default_rng(1)
    vfc = [round(v) for v in np.exp(rng.normal(np.log(65), 0.05, 40))]
    assert hrv.hrv_status(hrv.hrv_trend(_checkins(vfc))).status == "stable"
    assert hrv.hrv_status(hrv.hrv_trend(_checkins(vfc[:5]))).status == "insuffisant"


# --- Sommeil -------------------------------------------------------------------
def test_sleep_debt_regularity_and_midnight_bedtimes():
    hours = [6.0] * 7
    beds = ["23:30", "00:30", "23:45", "00:15", "23:30", "00:30", "00:00"]
    s = sleep.summarize(sleep.sleep_frame(_checkins([60] * 7, sleep_h=hours, bed=beds)), need_h=8)
    assert s.debt_h == pytest.approx(14.0)
    assert s.bedtime == "00:00"  # une moyenne naïve des heures donnerait ~12:00
    assert s.bed_sd < 30 and s.regularity == "Excellente"
    assert any(level == "error" for level, _ in s.insights)  # < 7 h et dette ≥ 5 h signalées


def test_sleep_hrv_effect_finds_positive_link():
    rng = np.random.default_rng(2)
    hours = rng.uniform(5.5, 9, 40)
    vfc = np.round(np.exp(np.log(60) + 0.06 * (hours - 7.5) + rng.normal(0, 0.02, 40)))
    eff = sleep.sleep_hrv_effect(_checkins(list(vfc), sleep_h=list(hours)))
    assert eff.r > 0.8 and eff.short_ms < eff.long_ms


# --- Risque de blessure ------------------------------------------------------------
def _flat_load(days=60, value=50.0, start="2026-01-01"):
    return pd.Series(value, index=pd.date_range(start, periods=days, freq="D"))


def test_risk_flags_load_spike_with_traceable_points():
    load = _flat_load(60)
    load.iloc[-7:] = 160.0
    ck = _checkins([60] * 60)
    rep = risk.compute_risk(load[load.index <= load.index[-1]], ck[ck["Date"] <= load.index[-1]])
    acwr = next(f for f in rep.timeline.loc[[load.index[-1]]].iterrows())[1]["acwr"]
    assert acwr == 30  # ACWR > 1.5
    assert rep.timeline.loc[load.index[-1], "score"] >= 30


def test_risk_persistent_pain_and_short_sleep():
    n = 30
    pains = ["Aucun"] * (n - 4) + ["Mollets"] * 4
    ck = _checkins([60] * n, sleep_h=[6.0] * n, pains=pains, start=str(pd.Timestamp.today().normalize() - pd.Timedelta(days=n - 1))[:10])
    rep = risk.compute_risk(_flat_load(n, start=str(ck["Date"].min())[:10]), ck)
    by = {f.key: f for f in rep.factors}
    assert by["douleur"].points == 20 and "Mollets" in by["douleur"].value
    assert by["sommeil"].points == 15
    assert rep.score == sum(f.points for f in rep.factors)
    assert rep.drivers[0].key == "douleur"


def test_risk_level_thresholds():
    assert risk.level_of(10)[0] == "Faible" and risk.level_of(30)[0] == "Modéré" and risk.level_of(60)[0] == "Élevé"


# --- Prédictions --------------------------------------------------------------------
def _demo_frames():
    mem = MemoryStorage()
    demo.seed(mem)
    re, ck = mem.read(schema.REALISE), mem.read(schema.CHECKIN)
    return tl.daily_load(tl.sessions_from_history(re)), ck, re


def test_hrv_model_beats_naive_forecast_in_walk_forward():
    daily, ck, _ = _demo_frames()
    m = forecast.train_hrv_model(daily, ck)
    assert m.ready and len(m.backtest) == 30
    assert m.mae_model < m.mae_naive
    # effets dans le bon sens physiologique
    assert m.effect_pct("charge_j") < 0 and m.effect_pct("sommeil") > 0


def test_hrv_model_requires_history():
    daily, ck, _ = _demo_frames()
    assert not forecast.train_hrv_model(daily.tail(10), ck.tail(10)).ready


def test_taper_scenario_freshens_athlete():
    daily, _, _ = _demo_frames()
    pmc = tl.performance_manager(daily)
    sc = forecast.race_scenarios(pmc, pd.Timestamp.today() + pd.Timedelta(days=21))
    assert sc["Affûtage 10 j"]["TSB"].iloc[-1] > sc["Maintien"]["TSB"].iloc[-1] > sc["Progression +8 %/sem."]["TSB"].iloc[-1]
    assert forecast.best_scenario(sc) == "Affûtage 10 j"


def test_project_pmc_matches_recursive_definition():
    out = forecast.project_pmc(50.0, 60.0, np.array([100.0]), pd.Timestamp("2026-01-01"))
    assert out["TSB"].iloc[0] == pytest.approx(-10.0)
    assert out["CTL"].iloc[0] == pytest.approx(50 + 50 / 42)


def test_riegel_and_race_predictions():
    assert forecast.riegel(45, 10, 10) == 45
    assert forecast.fmt_time(forecast.riegel(20, 5, 10)) == "41'42"
    _, _, re = _demo_frames()
    rp = forecast.race_predictions(re)
    assert rp is not None and rp["source"]["Type_Seance"] == "Test 10 km"
    assert rp["predictions"]["5 km"] < rp["predictions"]["10 km"] < rp["predictions"]["Marathon"]


def test_demo_tells_an_overreaching_story():
    daily, ck, _ = _demo_frames()
    rep = risk.compute_risk(daily, ck)
    assert rep.timeline["score"].max() >= 50  # le stage de surcharge déclenche un risque élevé
