import pytest
from datetime import datetime
from src.common.db import init_db, get_session
from src.common.models import OrderModel, ShipmentModel
from src.validation.engine import ValidationEngine

TEST_RULES_YAML = "configs/validation_rules.yaml"


@pytest.fixture
def db_session():
    test_db_url = "sqlite:///:memory:"
    init_db(test_db_url)
    session = get_session(test_db_url)
    yield session
    session.close()


def test_referential_integrity_check(db_session):
    # Add an order referencing an unknown supplier
    order = OrderModel(
        order_id="ORD-9999",
        supplier_id="SUPP-NONEXISTENT",
        order_date=datetime.utcnow(),
        total_amount=100.0,
        items_count=2,
        status="PENDING",
        updated_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.commit()

    engine = ValidationEngine(TEST_RULES_YAML)
    violations = engine.run_all_checks(db_session)

    ri_violations = [v for v in violations if v.category == "referential_integrity" and v.rule_id == "RULE-RI-001"]
    assert len(ri_violations) == 1
    assert "ORD-9999" in ri_violations[0].affected_ids


def test_cross_system_reconciliation(db_session):
    # Order cancelled, but shipment marked DELIVERED
    order = OrderModel(
        order_id="ORD-0005",
        supplier_id="SUPP-001",
        order_date=datetime.utcnow(),
        total_amount=50.0,
        items_count=5,
        status="CANCELLED",
        updated_at=datetime.utcnow(),
    )
    shipment = ShipmentModel(
        shipment_id="SHIP-0005",
        order_id="ORD-0005",
        shipped_at=datetime.utcnow(),
        quantity=5,
        carrier="DHL",
        status="DELIVERED",
        updated_at=datetime.utcnow(),
    )
    db_session.add(order)
    db_session.add(shipment)
    db_session.commit()

    engine = ValidationEngine(TEST_RULES_YAML)
    violations = engine.run_all_checks(db_session)

    recon_violations = [v for v in violations if v.rule_id == "RULE-RECON-002"]
    assert len(recon_violations) == 1
    assert "SHIP-0005" in recon_violations[0].affected_ids


def test_schema_and_null_checks(db_session):
    # Order with negative amount
    bad_order = OrderModel(
        order_id="ORD-NEG",
        supplier_id="SUPP-001",
        order_date=datetime.utcnow(),
        total_amount=-500.0,
        items_count=1,
        status="CONFIRMED",
        updated_at=datetime.utcnow(),
    )
    db_session.add(bad_order)
    db_session.commit()

    engine = ValidationEngine(TEST_RULES_YAML)
    violations = engine.run_all_checks(db_session)

    schema_violations = [v for v in violations if v.rule_id == "RULE-SCHEMA-001"]
    assert len(schema_violations) == 1
    assert "ORD-NEG" in schema_violations[0].affected_ids
