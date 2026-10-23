import pytest
from sqlalchemy import select
from src.common.db import init_db, get_session
from src.common.models import (
    OrderModel,
    DeadLetterModel,
)
from src.ingestion.engine import IngestionEngine
from src.ingestion.client import UpstreamClient


@pytest.fixture
def db_session():
    test_db_url = "sqlite:///:memory:"
    init_db(test_db_url)
    session = get_session(test_db_url)
    yield session
    session.close()


def test_idempotent_upsert(db_session):
    engine = IngestionEngine({})

    # 1. Insert order
    item_1 = {
        "order_id": "ORD-0001",
        "supplier_id": "SUPP-001",
        "order_date": "2026-01-01T12:00:00",
        "total_amount": 100.5,
        "items_count": 2,
        "status": "PENDING",
        "updated_at": "2026-01-01T12:00:00",
    }
    success = engine._upsert_order(db_session, item_1)
    db_session.commit()
    assert success is True

    record = db_session.execute(select(OrderModel).filter_by(order_id="ORD-0001")).scalar_one()
    assert record.total_amount == 100.5
    assert record.status == "PENDING"

    # 2. Update same order (Idempotency check)
    item_update = {
        "order_id": "ORD-0001",
        "supplier_id": "SUPP-001",
        "order_date": "2026-01-01T12:00:00",
        "total_amount": 150.0,
        "items_count": 3,
        "status": "CONFIRMED",
        "updated_at": "2026-01-01T13:00:00",
    }
    success_upd = engine._upsert_order(db_session, item_update)
    db_session.commit()
    assert success_upd is True

    # Count must remain 1
    orders = db_session.execute(select(OrderModel)).scalars().all()
    assert len(orders) == 1
    assert orders[0].total_amount == 150.0
    assert orders[0].status == "CONFIRMED"


def test_dead_letter_routing(db_session):
    engine = IngestionEngine({})

    # Malformed order missing required order_id
    bad_item = {
        "order_id": None,
        "supplier_id": "SUPP-001",
        "total_amount": "not-a-number",
    }
    success = engine._upsert_record(db_session, "orders", bad_item)
    db_session.commit()
    assert success is False

    dlq_records = db_session.execute(select(DeadLetterModel)).scalars().all()
    assert len(dlq_records) == 1
    assert dlq_records[0].source_service == "orders"
    assert dlq_records[0].error_type == "PARSE_OR_DB_UPSERT_ERROR"


def test_client_retry_and_backoff(monkeypatch):
    calls = 0

    class DummyResponse:
        status_code = 500
        text = "Internal Server Error"

    def mock_get(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls < 3:
            return DummyResponse()
        # On third attempt, return success
        class SuccessResponse:
            status_code = 200
            def json(self):
                return {"items": [], "has_next": False}
        return SuccessResponse()

    monkeypatch.setattr("requests.get", mock_get)

    client = UpstreamClient("http://mock-service", timeout=1.0, max_retries=3, backoff_factor=0.01)
    res = client.fetch_page("orders", page=1)
    assert calls == 3
    assert res == {"items": [], "has_next": False}
