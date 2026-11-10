import pandas as pd
import pytest

from coach import readiness as rd
from coach import training_load as tl


def test_readiness_bounds_and_ordering():
    good = rd.compute_readiness(8, 70, 45, 9).score
    bad = rd.compute_readiness(4.5, 35, 62, 2).score
    assert 0 <= bad < 50 < 75 <= good <= 100


def test_personal_baseline_changes_interpretation():
    hist = pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=10), "VFC": [40] * 10, "FC_Repos": [58] * 10})
    base = rd.compute_baseline(hist)
    assert base.personal and base.vfc == 40 and base.fcr == 58
    # 40 ms est "bas" dans l'absolu mais normal pour cet athlète
    assert rd.compute_readiness(8, 40, 58, 8, base).score > rd.compute_readiness(8, 40, 58, 8).score


def test_baseline_needs_minimum_history():
    hist = pd.DataFrame({"Date": pd.date_range("2026-01-01", periods=3), "VFC": [40] * 3, "FC_Repos": [58] * 3})
    assert not rd.compute_baseline(hist).personal


def test_estimate_tss_reference_points():
    assert tl.estimate_tss(60, 10) == pytest.approx(100)
    assert 40 < tl.estimate_tss(60, 4) < 50
    assert tl.estimate_tss(0, 8) == 0
    assert tl.estimate_tss(60, 0) == 0


def test_performance_manager_uses_daily_series():
    sessions = pd.DataFrame({"Date": pd.to_datetime(["2026-01-01", "2026-01-10"]), "TSS": [100.0, 100.0]})
    daily = tl.daily_load(sessions, until=pd.Timestamp("2026-01-10"))
    assert len(daily) == 10 and daily.sum() == 200
    pmc = tl.performance_manager(daily)
    # La fatigue doit avoir décru pendant les jours de repos
    assert pmc.ATL.iloc[8] < pmc.ATL.iloc[0]
    assert pmc.CTL.iloc[-1] < pmc.ATL.iloc[-1]


def test_acwr_flags_spike():
    calm = pd.Series([50.0] * 21 + [150.0] * 7, index=pd.date_range("2026-01-01", periods=28))
    status = tl.acwr_status(calm)
    assert status.acwr > 1.5 and status.label == "Zone de danger"
    steady = pd.Series([50.0] * 28, index=pd.date_range("2026-01-01", periods=28))
    assert tl.acwr_status(steady).label == "Zone optimale"
    assert tl.acwr_status(steady.tail(5)).acwr is None


def test_hr_zones_and_rpe_from_zones():
    assert tl.fc_max_tanaka(30) == 187
    zones = tl.hr_zones(200)
    assert zones[0]["min"] == 100 and zones[-1]["max"] == 200
    assert tl.rpe_from_zones([0, 60, 0, 0, 0]) == 4.0
    assert tl.rpe_from_zones([0, 0, 0, 0, 0]) is None


def test_sessions_group_strength_sets_into_one_session():
    from coach import schema

    rows = [["2026-01-05", 1, "Lundi", "PPG A", f"Squat (Série {i})", 60, 8, 2, 8, 7, 0, 50, 0, 0, 0, 0, 0, "Renforcement / PPG", 0, ""] for i in range(1, 4)] + [
        ["2026-01-06", 1, "Mardi", "Repos", "Repos", 0, 0, 0, 0, 3, 0, 0, 0, 0, 0, 0, 0, "Repos", 0, ""]
    ]
    df = schema.normalize(schema.REALISE, rows)
    sessions = tl.sessions_from_history(df)
    assert len(sessions) == 2
    assert sessions.iloc[0]["TSS"] == tl.estimate_tss(50, 7)
    assert sessions.iloc[1]["TSS"] == 0  # le repos n'ajoute pas de charge
