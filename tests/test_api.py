import pytest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

import database as db_module
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


@pytest.fixture(autouse=True)
def test_db(tmp_path):
    db_path = tmp_path / "api_test.db"
    test_url = f"sqlite:///{db_path}"
    engine = create_engine(test_url, connect_args={"check_same_thread": False})
    TestSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db_module.Base.metadata.create_all(engine)

    original_engine = db_module.engine
    original_session = db_module.SessionLocal
    db_module.engine = engine
    db_module.SessionLocal = TestSession

    yield

    db_module.engine = original_engine
    db_module.SessionLocal = original_session


@pytest.fixture
def client(test_db):
    db_module.init_db()
    from main import app
    from unittest.mock import patch, AsyncMock

    with patch("main.scrape", new_callable=AsyncMock, return_value=[]):
        with TestClient(app) as c:
            yield c


def seed_data():
    now = datetime.now(timezone.utc)
    records = []
    for i in range(5):
        ts = now - timedelta(hours=i)
        records.append({
            "club_name": "Test Club",
            "city": "Vilnius",
            "address": "Test St 1",
            "usage_percentage": 50 + i,
            "timestamp": ts,
        })
    records.append({
        "club_name": "Other Club",
        "city": "Kaunas",
        "address": "Other St 2",
        "usage_percentage": 30,
        "timestamp": now,
    })
    db_module.insert_usage(records)


class TestApiCurrent:
    def test_current_empty(self, client):
        resp = client.get("/api/current")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_current_returns_latest(self, client):
        seed_data()
        resp = client.get("/api/current")
        data = resp.json()
        assert len(data) == 2
        names = {d["club_name"] for d in data}
        assert "Test Club" in names
        assert "Other Club" in names

    def test_current_response_schema(self, client):
        seed_data()
        resp = client.get("/api/current")
        data = resp.json()
        for item in data:
            assert "club_name" in item
            assert "city" in item
            assert "address" in item
            assert "usage_percentage" in item
            assert "timestamp" in item


class TestApiHistorical:
    def test_historical_for_club(self, client):
        seed_data()
        resp = client.get("/api/historical/Test Club")
        data = resp.json()
        assert len(data) == 5
        assert all(d["club_name"] == "Test Club" for d in data)

    def test_historical_respects_days_param(self, client):
        now = datetime.now(timezone.utc)
        recent = now - timedelta(days=3)
        old = now - timedelta(days=10)
        db_module.insert_usage([
            {"club_name": "X", "city": "V", "address": "A", "usage_percentage": 10, "timestamp": recent},
            {"club_name": "X", "city": "V", "address": "A", "usage_percentage": 20, "timestamp": old},
        ])
        resp = client.get("/api/historical/X?days=7")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["usage_percentage"] == 10

    def test_historical_unknown_club(self, client):
        resp = client.get("/api/historical/ nonexistent")
        assert resp.json() == []


class TestApiAverage:
    def test_average_for_club(self, client):
        base = datetime(2025, 5, 28, 10, 0, tzinfo=timezone.utc)
        for i in range(3):
            ts = base + timedelta(weeks=i)
            db_module.insert_usage([{
                "club_name": "AvgClub", "city": "V", "address": "A",
                "usage_percentage": 20 + i * 10, "timestamp": ts,
            }])

        resp = client.get("/api/average/AvgClub")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["day_of_week"] == 3
        assert data[0]["hour"] == 10
        assert data[0]["avg_usage"] == 30.0

    def test_average_unknown_club(self, client):
        resp = client.get("/api/average/Unknown")
        assert resp.json() == []


class TestApiClubs:
    def test_clubs_list(self, client):
        seed_data()
        resp = client.get("/api/clubs")
        names = resp.json()
        assert isinstance(names, list)
        assert "Test Club" in names
        assert "Other Club" in names

    def test_clubs_empty(self, client):
        resp = client.get("/api/clubs")
        assert resp.json() == []


class TestIndexPage:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Lemon Gym" in resp.text