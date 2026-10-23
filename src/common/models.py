from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    JSON,
    Index,
)
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class SupplierModel(Base):
    """Supplier master data warehouse table."""
    __tablename__ = "suppliers"

    supplier_id = Column(String(64), primary_key=True)
    name = Column(String(255), nullable=False)
    country = Column(String(64), nullable=False)
    contact_email = Column(String(255), nullable=True)
    status = Column(String(32), nullable=False, default="ACTIVE")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class OrderModel(Base):
    """Purchase orders warehouse table."""
    __tablename__ = "orders"

    order_id = Column(String(64), primary_key=True)
    supplier_id = Column(String(64), nullable=False)
    order_date = Column(DateTime, nullable=False)
    total_amount = Column(Float, nullable=False)
    items_count = Column(Integer, nullable=False)
    status = Column(String(32), nullable=False, default="PENDING")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_orders_supplier_id", "supplier_id"),
        Index("idx_orders_updated_at", "updated_at"),
    )


class ShipmentModel(Base):
    """Shipment events warehouse table."""
    __tablename__ = "shipments"

    shipment_id = Column(String(64), primary_key=True)
    order_id = Column(String(64), nullable=False)
    shipped_at = Column(DateTime, nullable=False)
    quantity = Column(Integer, nullable=False)
    carrier = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, default="IN_TRANSIT")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("idx_shipments_order_id", "order_id"),
        Index("idx_shipments_updated_at", "updated_at"),
    )


class DeadLetterModel(Base):
    """Dead-letter store for unparsable or malformed payloads."""
    __tablename__ = "dead_letter_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    source_service = Column(String(64), nullable=False)
    endpoint = Column(String(255), nullable=False)
    raw_payload = Column(Text, nullable=False)
    error_message = Column(Text, nullable=False)
    error_type = Column(String(64), nullable=False)
    retry_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class IngestionWatermarkModel(Base):
    """Watermarks tracking last incremental sync cursor."""
    __tablename__ = "ingestion_watermarks"

    service_name = Column(String(64), primary_key=True)
    last_cursor = Column(String(255), nullable=True)
    last_synced_at = Column(DateTime, default=datetime.utcnow)
    records_synced = Column(Integer, default=0)


class IncidentModel(Base):
    """Incident registry recording data quality and integration failures."""
    __tablename__ = "incidents"

    incident_id = Column(String(64), primary_key=True)
    check_name = Column(String(128), nullable=False)
    rule_category = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)  # CRITICAL, HIGH, MEDIUM, LOW
    status = Column(String(32), nullable=False, default="OPEN")  # OPEN, RESOLVED, SUPPRESSED
    details = Column(JSON, nullable=False)
    affected_record_ids = Column(JSON, nullable=True)
    root_cause_summary = Column(Text, nullable=True)
    suggested_fix = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)


class AuditLogModel(Base):
    """System-wide audit log for traceability."""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_type = Column(String(64), nullable=False)  # INGEST_START, INGEST_SUCCESS, VALIDATION_RUN, ALERT_SENT, FAULT_INJECTED
    component = Column(String(64), nullable=False)
    details = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class GroundTruthFaultModel(Base):
    """Ground truth log for faults injected during testing/evaluations."""
    __tablename__ = "ground_truth_faults"

    fault_id = Column(String(64), primary_key=True)
    scenario_id = Column(String(64), nullable=False)
    target_service = Column(String(64), nullable=False)
    fault_type = Column(String(64), nullable=False)
    affected_ids = Column(JSON, nullable=False)
    details = Column(JSON, nullable=False)
    injected_at = Column(DateTime, default=datetime.utcnow)
