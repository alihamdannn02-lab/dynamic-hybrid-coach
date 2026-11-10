from datetime import datetime

from coach import schema
from coach.garmin import (
    Wellness,
    activity_to_row,
    format_pace,
    map_sport,
    parse_activity,
    parse_hrv,
    parse_rhr,
    parse_sleep,
    parse_training_readiness,
)

SLEEP = {
    "dailySleepDTO": {"sleepTimeSeconds": 27000, "sleepScores": {"overall": {"value": 84}}},
    "avgOvernightHrv": 61.0,
    "restingHeartRate": 46,
}
HRV = {"hrvSummary": {"lastNightAvg": 63, "weeklyAvg": 60, "status": "BALANCED"}}
RHR = {"allMetrics": {"metricsMap": {"WELLNESS_RESTING_HEART_RATE": [{"value": 47.0, "calendarDate": "2026-11-10"}]}}}
RUN = {
    "activityId": 123456789,
    "activityName": "Footing Z2",
    "startTimeLocal": "2026-11-09 07:15:00",
    "activityType": {"typeKey": "running"},
    "distance": 10234.5,
    "duration": 3600.0,
    "elevationGain": 85.0,
    "averageHR": 142.0,
    "averageSpeed": 2.84,
    "hrTimeInZone_1": 300.0,
    "hrTimeInZone_2": 2700.0,
    "hrTimeInZone_3": 600.0,
    "hrTimeInZone_4": 0.0,
    "hrTimeInZone_5": 0.0,
}


def test_parse_sleep():
    assert parse_sleep(SLEEP) == (7.5, 84, 61, 46)
    assert parse_sleep(None) == (None, None, None, None)
    assert parse_sleep({}) == (None, None, None, None)


def test_parse_hrv_and_rhr():
    assert parse_hrv(HRV) == (63, "BALANCED", 60)
    assert parse_hrv({"hrvSummary": None}) == (None, None, None)
    assert parse_rhr(RHR) == 47
    assert parse_rhr({"allMetrics": {}}) is None


def test_parse_training_readiness_list_or_dict():
    assert parse_training_readiness([{"score": 72, "level": "MODERATE"}]) == (72, "MODERATE")
    assert parse_training_readiness({"score": 40}) == (40, None)
    assert parse_training_readiness([]) == (None, None)


def test_wellness_energy_suggestion():
    assert Wellness(date="x", body_battery=85).energie_suggeree == 8
    assert Wellness(date="x", body_battery=2).energie_suggeree == 1
    assert Wellness(date="x").energie_suggeree is None
    assert not Wellness(date="x").has_data


def test_map_sport():
    assert map_sport("trail_running") == "Trail / Ski Alpinisme"
    assert map_sport("road_biking") == "Cyclisme"
    assert map_sport("lap_swimming") == "Natation"
    assert map_sport("some_new_running_mode") == "Course à pied"
    assert map_sport("") == "Autre"


def test_format_pace():
    assert format_pace("Course à pied", 2.84, None) == "5:52 min/km"
    assert format_pace("Cyclisme", 8.0, 215.4) == "215 W"
    assert format_pace("Cyclisme", 8.0, None) == "28.8 km/h"
    assert format_pace("Natation", 1.0, None) == "1:40 min/100m"
    assert format_pace("Course à pied", None, None) == ""


def test_parse_activity_with_inline_zones():
    a = parse_activity(RUN)
    assert a.activity_id == "123456789"
    assert a.start == datetime(2026, 11, 9, 7, 15)
    assert a.sport == "Course à pied"
    assert a.distance_km == 10.23
    assert a.duration_min == 60
    assert a.zones_min == [5, 45, 10, 0, 0]
    assert 3.5 < a.rpe < 4.5  # majoritairement en Z2


def test_parse_activity_zone_fallback_and_rpe():
    raw = {**{k: v for k, v in RUN.items() if not k.startswith("hrTimeInZone")}, "directWorkoutRpe": 70}
    zones = [{"zoneNumber": i, "secsInZone": 600.0} for i in range(1, 6)]
    a = parse_activity(raw, zones)
    assert a.zones_min == [10, 10, 10, 10, 10]
    assert a.rpe == 7.0


def test_activity_to_row_matches_schema():
    row = activity_to_row(parse_activity(RUN), semaine=3)
    assert len(row) == len(schema.REALISE_COLUMNS)
    rec = dict(zip(schema.REALISE_COLUMNS, row))
    assert rec["Date"] == "2026-11-09"
    assert rec["Jour"] == "Lundi"
    assert rec["Semaine"] == 3
    assert rec["Sport_Discipline"] == "Course à pied"
    assert rec["Activity_ID"] == "123456789"
    assert rec["Z2_Min"] == 45
    assert rec["Allure_Puissance"] == "5:52 min/km"


# ---------------------------------------------------------------------------
# Flux d'authentification (bibliothèque garminconnect simulée)
# ---------------------------------------------------------------------------
import garminconnect  # noqa: E402
import pytest  # noqa: E402

from coach.garmin import GarminError, GarminSession  # noqa: E402


class _FakeClient:
    def dumps(self):
        return '{"di_token": "t", "di_refresh_token": "r", "di_client_id": "c"}'


class FakeGarmin:
    needs_mfa = False
    instances: list = []

    def __init__(self, email=None, password=None, is_cn=False, return_on_mfa=False, **_):
        self.email, self.password, self.return_on_mfa = email, password, return_on_mfa
        self.client = _FakeClient()
        self.full_name = None
        FakeGarmin.instances.append(self)

    def login(self, tokenstore=None):
        if tokenstore:
            assert '"di_token"' in tokenstore
            self.full_name = "Athlète Test"
            return None, None
        if self.password == "wrong":
            raise garminconnect.GarminConnectAuthenticationError("401")
        if FakeGarmin.needs_mfa:
            return "needs_mfa", {"state": 1}
        return None, None

    def resume_login(self, state, code):
        if code != "123456":
            raise garminconnect.GarminConnectAuthenticationError("bad code")
        self.full_name = "Athlète MFA"
        return None, None

    def logout(self):
        pass

    def get_sleep_data(self, d):
        return SLEEP

    def get_hrv_data(self, d):
        return HRV

    def get_user_summary(self, d):
        return {"restingHeartRate": 45, "bodyBatteryMostRecentValue": 77, "averageStressLevel": -1}

    def get_rhr_day(self, d):
        return RHR

    def get_training_readiness(self, d):
        raise garminconnect.GarminConnectConnectionError("not supported on this device")

    def get_activities_by_date(self, start, end):
        return [RUN, {**RUN, "activityId": 2, "startTimeLocal": "2026-11-10 18:00:00", "activityType": {"typeKey": "road_biking"}}]

    def get_activity_hr_in_timezones(self, activity_id):
        return []


@pytest.fixture()
def fake_garmin(monkeypatch):
    FakeGarmin.needs_mfa = False
    FakeGarmin.instances = []
    monkeypatch.setattr(garminconnect, "Garmin", FakeGarmin)
    return FakeGarmin


def test_login_without_mfa_reopens_session_from_tokens(fake_garmin):
    s = GarminSession()
    assert s.login("a@b.c", "pwd") == "ok"
    assert s.connected and s.display_name == "Athlète Test"
    assert fake_garmin.instances[0].return_on_mfa is True
    assert "di_token" in s.tokens()


def test_login_with_mfa(fake_garmin):
    fake_garmin.needs_mfa = True
    s = GarminSession()
    assert s.login("a@b.c", "pwd") == "mfa"
    assert s.awaiting_mfa and not s.connected
    with pytest.raises(GarminError):
        s.submit_mfa("000000")
    s.submit_mfa(" 123456 ")
    assert s.connected and not s.awaiting_mfa and s.display_name == "Athlète MFA"


def test_bad_credentials_are_friendly(fake_garmin):
    with pytest.raises(GarminError, match="Identifiants"):
        GarminSession().login("a@b.c", "wrong")


def test_fetch_wellness_tolerates_missing_endpoints(fake_garmin):
    s = GarminSession()
    s.login_with_tokens(_FakeClient().dumps())
    w = s.fetch_wellness()
    assert (w.sommeil_h, w.vfc, w.fcr, w.body_battery, w.stress) == (7.5, 63, 45, 77, None)
    assert w.training_readiness is None and "Training Readiness" in w.errors


def test_fetch_activities_sorted_newest_first(fake_garmin):
    s = GarminSession()
    s.login_with_tokens(_FakeClient().dumps())
    acts = s.fetch_activities(datetime(2026, 11, 1).date(), datetime(2026, 11, 10).date())
    assert [a.sport for a in acts] == ["Cyclisme", "Course à pied"]
