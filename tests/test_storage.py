from coach import demo, schema
from coach.storage import LocalStorage


def test_local_roundtrip_and_padding(tmp_path):
    s = LocalStorage(tmp_path)
    s.append(schema.CHECKIN, [["2026-01-01", "7,5", 60, 48, 7, "Aucun", 30]])
    df = s.read(schema.CHECKIN)
    assert list(df.columns) == schema.CHECKIN_COLUMNS
    assert df.iloc[0]["Heures_Sommeil"] == 7.5  # virgule décimale FR gérée


def test_delete_last_session_removes_all_sets_of_that_day(tmp_path):
    s = LocalStorage(tmp_path)
    s.append(schema.REALISE, [["2026-01-01", 1, "Jeudi", "A", "x"], ["2026-01-02", 1, "Vendredi", "B", "y (Série 1)"], ["2026-01-02", 1, "Vendredi", "B", "y (Série 2)"]])
    ok, msg = s.delete_last_session()
    assert ok and "2 lignes" in msg
    assert len(s.read(schema.REALISE)) == 1
    s.delete_last_session()
    assert s.delete_last_session() == (False, "L'historique est déjà vide.")


def test_legacy_rows_without_new_columns(tmp_path):
    """Les anciennes lignes (20 colonnes, sans Activity_ID) restent lisibles."""
    s = LocalStorage(tmp_path)
    s.append(schema.REALISE, [["2026-01-01", 1, "Jeudi", "Run", "Bilan Endurance", 0, 0, 0, 0, 6, 10, 60, 0, 60, 0, 0, 0, "Course à pied", 50, "5:00"]])
    df = s.read(schema.REALISE)
    assert df.iloc[0]["Activity_ID"] == ""


def test_demo_seed_is_consistent(tmp_path):
    s = LocalStorage(tmp_path)
    demo.seed(s, weeks=4)
    assert not s.read(schema.PROGRAMME).empty
    realise = s.read(schema.REALISE)
    assert realise["Date"].notna().all()
    assert set(realise["Jour"]) <= set(schema.JOURS)
    assert len(s.read(schema.CHECKIN)) >= 21
