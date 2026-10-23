import pytest
from sqlalchemy import select
from src.common.db import init_db, get_session
from src.common.models import IncidentModel, AuditLogModel
from src.validation.rules import ValidationViolation
from src.alerts.incident_manager import IncidentManager
from src.alerts.notifiers import PluggableNotifierManager, BaseNotifier


class MockCollectorNotifier(BaseNotifier):
    def __init__(self):
        self.alerts = []

    def send_alert(self, incident):
        self.alerts.append(incident)
        return True


@pytest.fixture
def db_session():
    test_db_url = "sqlite:///:memory:"
    init_db(test_db_url)
    session = get_session(test_db_url)
    yield session
    session.close()


def test_incident_creation_and_alert_dispatch(db_session):
    collector = MockCollectorNotifier()
    mgr = IncidentManager(PluggableNotifierManager([collector]))

    violation = ValidationViolation(
        rule_id="RULE-RI-001",
        rule_name="orders_supplier_fk",
        category="referential_integrity",
        severity="CRITICAL",
        description="Missing supplier reference",
        violation_count=2,
        affected_ids=["ORD-101", "ORD-102"],
        sample_records=[{"order_id": "ORD-101"}],
    )

    incidents = mgr.process_violations(db_session, [violation])
    assert len(incidents) == 1
    assert incidents[0].check_name == "orders_supplier_fk"
    assert len(collector.alerts) == 1

    # Audit log check
    audit_logs = db_session.execute(select(AuditLogModel)).scalars().all()
    assert len(audit_logs) >= 1
    assert any(log.event_type == "INCIDENT_CREATED" for log in audit_logs)

    # Idempotency / deduplication: process same violation again
    mgr.process_violations(db_session, [violation])
    all_incidents = db_session.execute(select(IncidentModel)).scalars().all()
    assert len(all_incidents) == 1  # Should not duplicate open incident


def test_incident_resolution(db_session):
    mgr = IncidentManager(PluggableNotifierManager([]))
    violation = ValidationViolation(
        rule_id="RULE-NULL-001",
        rule_name="orders_required_fields",
        category="null_and_required",
        severity="CRITICAL",
        description="Null fields",
        violation_count=1,
        affected_ids=["ORD-999"],
        sample_records=[],
    )
    incidents = mgr.process_violations(db_session, [violation])
    inc_id = incidents[0].incident_id

    success = mgr.resolve_incident(db_session, inc_id)
    assert success is True

    resolved_inc = db_session.execute(select(IncidentModel).filter_by(incident_id=inc_id)).scalar_one()
    assert resolved_inc.status == "RESOLVED"
    assert resolved_inc.resolved_at is not None
