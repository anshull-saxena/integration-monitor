import pytest
from fastapi.testclient import TestClient
from src.common.db import init_db, get_session
from src.api.main import app, get_db

TEST_DB = "sqlite:///:memory:"

def override_get_db():
    session = get_session(TEST_DB)
    try:
        yield session
    finally:
        session.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)


@pytest.fixture(autouse=True)
def setup_db():
    init_db(TEST_DB)


def test_api_health():
    res = client.get("/health")
    assert res.status_code == 200
    assert res.json()["service"] == "integration-monitor-api"


def test_eval_endpoint():
    res = client.get("/eval")
    assert res.status_code == 200
    data = res.json()
    assert data["total_scenarios_run"] >= 8
    assert "metrics_by_fault_type" in data
    assert "diagnostic_evaluations" in data


def test_list_incidents_empty():
    res = client.get("/incidents")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


def test_list_dlq_records_empty():
    res = client.get("/dead-letter-records")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
