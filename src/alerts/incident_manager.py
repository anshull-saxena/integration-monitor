import uuid
import logging
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.common.models import IncidentModel, AuditLogModel
from src.validation.rules import ValidationViolation
from src.alerts.notifiers import PluggableNotifierManager

logger = logging.getLogger(__name__)


class IncidentManager:
    """Handles incident lifecycle, deduplication, persistence, and alert dispatching."""

    def __init__(self, notifier_manager: Optional[PluggableNotifierManager] = None):
        self.notifiers = notifier_manager or PluggableNotifierManager()

    def process_violations(
        self, session: Session, violations: List[ValidationViolation]
    ) -> List[IncidentModel]:
        """Converts validation violations into incidents, avoids duplicate open incidents, and triggers alerts."""
        created_incidents: List[IncidentModel] = []

        for v in violations:
            # Check if an open incident already exists for this check_name
            existing = session.execute(
                select(IncidentModel).filter_by(check_name=v.rule_name, status="OPEN")
            ).scalar_one_or_none()

            if existing:
                # Update existing incident with latest count and sample
                existing.details = {
                    "rule_id": v.rule_id,
                    "description": v.description,
                    "violation_count": v.violation_count,
                    "sample_records": v.sample_records,
                    "last_detected_at": datetime.utcnow().isoformat(),
                }
                existing.affected_record_ids = v.affected_ids
                session.flush()
                logger.info(f"Updated existing open incident {existing.incident_id} for rule {v.rule_name}")
                continue

            incident_id = f"INC-{uuid.uuid4().hex[:8].upper()}"
            incident = IncidentModel(
                incident_id=incident_id,
                check_name=v.rule_name,
                rule_category=v.category,
                severity=v.severity,
                status="OPEN",
                details={
                    "rule_id": v.rule_id,
                    "description": v.description,
                    "violation_count": v.violation_count,
                    "sample_records": v.sample_records,
                },
                affected_record_ids=v.affected_ids,
                created_at=datetime.utcnow(),
            )
            session.add(incident)
            session.flush()

            # Record audit log
            audit_entry = AuditLogModel(
                event_type="INCIDENT_CREATED",
                component="IncidentManager",
                details={
                    "incident_id": incident_id,
                    "check_name": v.rule_name,
                    "category": v.category,
                    "severity": v.severity,
                    "count": v.violation_count,
                },
            )
            session.add(audit_entry)
            session.commit()

            # Dispatch notification
            incident_dict = {
                "incident_id": incident.incident_id,
                "check_name": incident.check_name,
                "rule_category": incident.rule_category,
                "severity": incident.severity,
                "status": incident.status,
                "details": incident.details,
                "affected_record_ids": incident.affected_record_ids,
            }
            self.notifiers.dispatch(incident_dict)
            created_incidents.append(incident)

        return created_incidents

    def resolve_incident(self, session: Session, incident_id: str) -> bool:
        """Marks an open incident as resolved."""
        incident = session.execute(
            select(IncidentModel).filter_by(incident_id=incident_id)
        ).scalar_one_or_none()
        if not incident:
            return False

        incident.status = "RESOLVED"
        incident.resolved_at = datetime.utcnow()
        session.add(
            AuditLogModel(
                event_type="INCIDENT_RESOLVED",
                component="IncidentManager",
                details={"incident_id": incident_id},
            )
        )
        session.commit()
        return True
