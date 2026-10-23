import logging
from typing import Dict, Any, Optional
from fastapi import FastAPI, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select, desc
from src.common.db import get_session, init_db
from src.common.models import (
    IncidentModel,
    DeadLetterModel,
    AuditLogModel,
)
from src.common.config import settings
from src.ingestion.engine import IngestionEngine
from src.validation.engine import ValidationEngine
from src.alerts.incident_manager import IncidentManager
from src.llm.explainer import MockLLMClient, OpenAILLMClient
from src.llm.prompt import build_root_cause_prompt
from eval.runner import EvaluationRunner

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Integration Monitor API",
    description="Data quality monitoring, integration pipeline orchestration, and LLM root-cause summaries",
    version="1.0.0",
)


@app.on_event("startup")
def on_startup():
    try:
        init_db()
        logger.info("Warehouse database initialized successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database on startup: {e}")


def get_db():
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_llm():
    if settings.llm_provider == "openai" and settings.llm_api_key:
        return OpenAILLMClient(api_key=settings.llm_api_key, model=settings.llm_model)
    return MockLLMClient()


# Request / Response Schemas
class SyncResponse(BaseModel):
    service: str
    status: str
    total_records: int
    dlq_count: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "integration-monitor-api"}


@app.post("/pipeline/sync", response_model=Dict[str, Any])
def run_sync_pipeline(
    scenario_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    """Triggers an incremental ingestion run across all upstream services."""
    service_urls = {
        "suppliers": settings.supplier_service_url,
        "orders": settings.orders_service_url,
        "shipments": settings.shipments_service_url,
    }
    engine = IngestionEngine(service_urls=service_urls)
    results = {}

    for service_name in ["suppliers", "orders", "shipments"]:
        res = engine.sync_service(
            service_name=service_name,
            session=db,
            scenario_id=scenario_id,
        )
        results[service_name] = res

    return {"status": "sync_completed", "results": results}


@app.post("/pipeline/validate")
def run_validations(db: Session = Depends(get_db)):
    """Runs all YAML-configured data quality & referential integrity checks, creating incidents and LLM summaries."""
    validation_engine = ValidationEngine(settings.validation_config_path)
    incident_mgr = IncidentManager()
    llm_client = get_llm()

    violations = validation_engine.run_all_checks(db)
    created_incidents = incident_mgr.process_violations(db, violations)

    # Generate LLM root cause analysis for newly created incidents
    enriched_count = 0
    for inc in created_incidents:
        prompt = build_root_cause_prompt(
            check_name=inc.check_name,
            category=inc.rule_category,
            severity=inc.severity,
            details=inc.details,
            affected_ids=inc.affected_record_ids or [],
            pipeline_logs=[{"event": "VALIDATION_FAILED", "rule": inc.check_name}],
        )
        explanation = llm_client.generate_explanation(prompt)
        inc.root_cause_summary = explanation.root_cause_summary
        inc.suggested_fix = explanation.suggested_fix
        db.commit()
        enriched_count += 1

    return {
        "status": "validation_completed",
        "violations_detected": len(violations),
        "incidents_created": len(created_incidents),
        "incidents_enriched_with_llm": enriched_count,
    }


@app.get("/incidents")
def list_incidents(
    status_filter: Optional[str] = Query(None, alias="status"),
    severity: Optional[str] = None,
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """Returns stored incidents with LLM root cause summaries."""
    query = select(IncidentModel).order_by(desc(IncidentModel.created_at)).limit(limit)
    if status_filter:
        query = query.filter_by(status=status_filter.upper())
    if severity:
        query = query.filter_by(severity=severity.upper())

    incidents = db.execute(query).scalars().all()
    return [
        {
            "incident_id": inc.incident_id,
            "check_name": inc.check_name,
            "rule_category": inc.rule_category,
            "severity": inc.severity,
            "status": inc.status,
            "details": inc.details,
            "affected_record_ids": inc.affected_record_ids,
            "root_cause_summary": inc.root_cause_summary,
            "suggested_fix": inc.suggested_fix,
            "created_at": inc.created_at.isoformat() if inc.created_at else None,
            "resolved_at": inc.resolved_at.isoformat() if inc.resolved_at else None,
        }
        for inc in incidents
    ]


@app.post("/incidents/{incident_id}/resolve")
def resolve_incident(incident_id: str, db: Session = Depends(get_db)):
    mgr = IncidentManager()
    success = mgr.resolve_incident(db, incident_id)
    if not success:
        raise HTTPException(status_code=404, detail="Incident not found")
    return {"status": "resolved", "incident_id": incident_id}


@app.get("/dead-letter-records")
def list_dlq_records(limit: int = 50, db: Session = Depends(get_db)):
    """Returns records that failed parsing or database upserts."""
    query = select(DeadLetterModel).order_by(desc(DeadLetterModel.created_at)).limit(limit)
    records = db.execute(query).scalars().all()
    return [
        {
            "id": r.id,
            "source_service": r.source_service,
            "endpoint": r.endpoint,
            "raw_payload": r.raw_payload,
            "error_message": r.error_message,
            "error_type": r.error_type,
            "retry_count": r.retry_count,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in records
    ]


@app.get("/audit-logs")
def list_audit_logs(limit: int = 50, db: Session = Depends(get_db)):
    query = select(AuditLogModel).order_by(desc(AuditLogModel.created_at)).limit(limit)
    logs = db.execute(query).scalars().all()
    return [
        {
            "id": log_entry.id,
            "event_type": log_entry.event_type,
            "component": log_entry.component,
            "details": log_entry.details,
            "created_at": log_entry.created_at.isoformat() if log_entry.created_at else None,
        }
        for log_entry in logs
    ]


@app.get("/eval")
def run_evaluation_suite():
    """Triggers the evaluation runner across scripted scenarios and returns full metrics."""
    runner = EvaluationRunner()
    summary = runner.run_all()
    return summary.model_dump()
