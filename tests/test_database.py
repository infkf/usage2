from datetime import datetime, timezone, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import database as db_module


@pytest.fixture
def tmp_db(tmp_path):
    db_path = tmp_path / "test_gym.db"
    test_url = f"sqlite:///{db_path}"
    engine = create_engine(test_url, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    db_module.Base.metadata.create_all(engine)

    original_engine = db_module.engine
    original_session = db_module.SessionLocal
    db_module.engine = engine
    db_module.SessionLocal = TestSession

    yield db_path

    db_module.engine = original_engine
    db_module.SessionLocal = original_session


def _make_record(club_name="Test Club", city="Vilnius", address="Test St 1", pct=50, ts=None):
    return {
        "club_name": club_name,
        "city": city,
        "address": address,
        "usage_percentage": pct,
        "timestamp": ts or datetime.now(timezone.utc),
    }


class TestDatabaseInit:
    def test_init_db_creates_table(self, tmp_db):
        db_module.init_db()
        assert tmp_db.exists()


class TestInsertAndQuery:
    def test_insert_and_retrieve(self, tmp_db):
        records = [
            _make_record("Club A", "Vilnius", "St 1", 30),
            _make_record("Club B", "Kaunas", "St 2", 70),
        ]
        db_module.insert_usage(records)

        latest = db_module.get_latest_usage()
        assert len(latest) == 2
        names = {r["club_name"] for r in latest}
        assert "Club A" in names
        assert "Club B" in names

    def test_latest_returns_newest_per_club(self, tmp_db):
        now = datetime.now(timezone.utc)
        old_ts = now - timedelta(hours=2)
        new_ts = now - timedelta(hours=1)

        db_module.insert_usage([_make_record("Club X", "Vilnius", "St", 20, old_ts)])
        db_module.insert_usage([_make_record("Club X", "Vilnius", "St", 80, new_ts)])

        latest = db_module.get_latest_usage()
        assert len(latest) == 1
        assert latest[0]["usage_percentage"] == 80

    def test_historical_filters_by_club_and_days(self, tmp_db):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=3)
        old = now - timedelta(days=10)

        db_module.insert_usage([_make_record("Club A", "Vilnius", "St", 30, recent)])
        db_module.insert_usage([_make_record("Club A", "Vilnius", "St", 10, old)])
        db_module.insert_usage([_make_record("Club B", "Vilnius", "St", 50, recent)])

        hist = db_module.get_historical_usage("Club A", days=7)
        assert len(hist) == 1
        assert hist[0]["usage_percentage"] == 30

    def test_historical_default_7_days(self, tmp_db):
        now = datetime.now(timezone.utc)
        ts = now - timedelta(days=5)

        db_module.insert_usage([_make_record("Club Z", "Vilnius", "St", 44, ts)])

        hist = db_module.get_historical_usage("Club Z")
        assert len(hist) == 1

    def test_average_usage_aggregation(self, tmp_db):
        base = datetime(2025, 5, 28, 10, 0, tzinfo=timezone.utc)

        for i in range(3):
            ts = base + timedelta(weeks=i)
            db_module.insert_usage([_make_record("Club A", "Vilnius", "St", 30 + i * 10, ts)])

        avg = db_module.get_average_usage("Club A")
        assert len(avg) == 1
        assert avg[0]["day_of_week"] == 3
        assert avg[0]["hour"] == 10
        assert avg[0]["avg_usage"] == 40.0

    def test_club_names(self, tmp_db):
        db_module.insert_usage([
            _make_record("Alpha", "Vilnius", "St", 10),
            _make_record("Beta", "Kaunas", "St", 20),
            _make_record("Alpha", "Vilnius", "St", 15),
        ])
        names = db_module.get_club_names()
        assert set(names) == {"Alpha", "Beta"}

    def test_insert_empty_records(self, tmp_db):
        db_module.insert_usage([])
        latest = db_module.get_latest_usage()
        assert latest == []

    def test_as_dict_serialization(self, tmp_db):
        ts = datetime(2025, 6, 1, 12, 0, tzinfo=timezone.utc)
        db_module.insert_usage([_make_record("DictClub", "Vilnius", "Addr 1", 55, ts)])

        latest = db_module.get_latest_usage()
        assert latest[0]["club_name"] == "DictClub"
        assert latest[0]["city"] == "Vilnius"
        assert latest[0]["usage_percentage"] == 55
        assert "2025-06-01" in latest[0]["timestamp"]

    def test_prune_old_records(self, tmp_db):
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=800)
        recent = now - timedelta(days=10)

        db_module.insert_usage([
            _make_record("OldClub", "Vilnius", "St", 10, old),
            _make_record("RecentClub", "Kaunas", "St", 20, recent),
            _make_record("OldClub2", "Vilnius", "St", 30, old),
        ])

        deleted = db_module.prune_old_records()
        assert deleted == 2

        all_names = db_module.get_club_names()
        assert all_names == ["RecentClub"]

    def test_prune_keeps_exactly_two_years(self, tmp_db):
        now = datetime.now(timezone.utc)
        exactly_729 = now - timedelta(days=729)
        exactly_731 = now - timedelta(days=731)

        db_module.insert_usage([
            _make_record("Keep", "V", "S", 10, exactly_729),
            _make_record("Prune", "V", "S", 20, exactly_731),
        ])

        deleted = db_module.prune_old_records()
        assert deleted == 1
        names = db_module.get_club_names()
        assert names == ["Keep"]