import logging
from datetime import datetime
from typing import Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import select
from src.common.models import (
    SupplierModel,
    OrderModel,
    ShipmentModel,
    IngestionWatermarkModel,
    AuditLogModel,
)
from src.ingestion.client import UpstreamClient, UpstreamServerException
from src.ingestion.dlq import DeadLetterQueue

logger = logging.getLogger(__name__)


class IngestionEngine:
    """Manages incremental ingestion, idempotent upserts, and DLQ routing."""

    def __init__(self, service_urls: Dict[str, str], timeout: float = 5.0):
        self.clients = {
            name: UpstreamClient(url, timeout=timeout)
            for name, url in service_urls.items()
        }

    def sync_service(
        self,
        service_name: str,
        session: Session,
        scenario_id: str = "default",
        batch_size: int = 50,
        max_pages: int = 10,
    ) -> Dict[str, Any]:
        """Pulls incremental pages from a target service and performs idempotent upserts."""
        if service_name not in self.clients:
            raise ValueError(f"Unknown service {service_name}")

        client = self.clients[service_name]
        endpoint = service_name  # e.g. suppliers, orders, shipments

        # Retrieve watermark
        watermark = session.execute(
            select(IngestionWatermarkModel).filter_by(service_name=service_name)
        ).scalar_one_or_none()

        start_page = int(watermark.last_cursor) if watermark and watermark.last_cursor else 1
        current_page = start_page
        total_ingested = 0
        dlq_records = 0

        # Log audit start
        session.add(
            AuditLogModel(
                event_type="INGEST_START",
                component="IngestionEngine",
                details={"service": service_name, "start_page": start_page, "scenario_id": scenario_id},
            )
        )
        session.flush()

        for _ in range(max_pages):
            try:
                response = client.fetch_page(
                    endpoint=endpoint,
                    page=current_page,
                    page_size=batch_size,
                    scenario_id=scenario_id,
                )
            except UpstreamServerException as e:
                # Fatal fetch error after retries exhausted -> record to DLQ and audit log
                DeadLetterQueue.record_failure(
                    session=session,
                    source_service=service_name,
                    endpoint=endpoint,
                    raw_payload={"page": current_page, "scenario_id": scenario_id},
                    error_message=str(e),
                    error_type="UPSTREAM_UNAVAILABLE_AFTER_RETRIES",
                )
                session.commit()
                return {
                    "service": service_name,
                    "pages_synced": current_page - start_page,
                    "total_records": total_ingested,
                    "dlq_count": dlq_records + 1,
                    "status": "partial_error",
                    "error": str(e),
                }

            items = response.get("items", [])
            if not items:
                break

            for raw_item in items:
                success = self._upsert_record(session, service_name, raw_item)
                if success:
                    total_ingested += 1
                else:
                    dlq_records += 1

            session.commit()

            if not response.get("has_next", False):
                break
            current_page += 1

        # Update watermark
        if not watermark:
            watermark = IngestionWatermarkModel(service_name=service_name)
            session.add(watermark)

        watermark.last_cursor = str(current_page)
        watermark.last_synced_at = datetime.utcnow()
        watermark.records_synced += total_ingested

        # Log audit finish
        session.add(
            AuditLogModel(
                event_type="INGEST_SUCCESS",
                component="IngestionEngine",
                details={
                    "service": service_name,
                    "records_ingested": total_ingested,
                    "dlq_count": dlq_records,
                    "last_cursor": watermark.last_cursor,
                },
            )
        )
        session.commit()

        return {
            "service": service_name,
            "pages_synced": (current_page - start_page) + 1,
            "total_records": total_ingested,
            "dlq_count": dlq_records,
            "status": "success",
        }

    def _upsert_record(self, session: Session, service_name: str, item: Dict[str, Any]) -> bool:
        """Parses and upserts an individual record into warehouse table; sends to DLQ if malformed."""
        try:
            if service_name == "suppliers":
                return self._upsert_supplier(session, item)
            elif service_name == "orders":
                return self._upsert_order(session, item)
            elif service_name == "shipments":
                return self._upsert_shipment(session, item)
            else:
                raise ValueError(f"Unknown service {service_name}")
        except Exception as e:
            session.rollback()
            DeadLetterQueue.record_failure(
                session=session,
                source_service=service_name,
                endpoint=service_name,
                raw_payload=item,
                error_message=str(e),
                error_type="PARSE_OR_DB_UPSERT_ERROR",
            )
            return False

    def _upsert_supplier(self, session: Session, item: Dict[str, Any]) -> bool:
        supplier_id = item.get("supplier_id")
        if not supplier_id or not isinstance(supplier_id, str):
            raise ValueError(f"Invalid primary key 'supplier_id': {supplier_id}")

        existing = session.execute(
            select(SupplierModel).filter_by(supplier_id=supplier_id)
        ).scalar_one_or_none()

        upd_at = datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else datetime.utcnow()

        if existing:
            existing.name = str(item.get("name", existing.name))
            existing.country = str(item.get("country", existing.country))
            existing.contact_email = item.get("contact_email")
            existing.status = str(item.get("status", existing.status))
            existing.updated_at = upd_at
        else:
            supplier = SupplierModel(
                supplier_id=supplier_id,
                name=str(item.get("name", "")),
                country=str(item.get("country", "")),
                contact_email=item.get("contact_email"),
                status=str(item.get("status", "ACTIVE")),
                updated_at=upd_at,
            )
            session.add(supplier)
        session.flush()
        return True

    def _upsert_order(self, session: Session, item: Dict[str, Any]) -> bool:
        order_id = item.get("order_id")
        if not order_id or not isinstance(order_id, str):
            raise ValueError(f"Invalid primary key 'order_id': {order_id}")

        existing = session.execute(
            select(OrderModel).filter_by(order_id=order_id)
        ).scalar_one_or_none()

        upd_at = datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else datetime.utcnow()
        ord_date = datetime.fromisoformat(item["order_date"]) if item.get("order_date") else datetime.utcnow()

        if existing:
            existing.supplier_id = str(item.get("supplier_id", existing.supplier_id))
            existing.order_date = ord_date
            existing.total_amount = float(item.get("total_amount", existing.total_amount))
            existing.items_count = int(item.get("items_count", existing.items_count))
            existing.status = str(item.get("status") or "")
            existing.updated_at = upd_at
        else:
            order = OrderModel(
                order_id=order_id,
                supplier_id=str(item.get("supplier_id", "")),
                order_date=ord_date,
                total_amount=float(item.get("total_amount", 0.0)),
                items_count=int(item.get("items_count", 0)),
                status=str(item.get("status") or ""),
                updated_at=upd_at,
            )
            session.add(order)
        session.flush()
        return True

    def _upsert_shipment(self, session: Session, item: Dict[str, Any]) -> bool:
        shipment_id = item.get("shipment_id")
        if not shipment_id or not isinstance(shipment_id, str):
            raise ValueError(f"Invalid primary key 'shipment_id': {shipment_id}")

        existing = session.execute(
            select(ShipmentModel).filter_by(shipment_id=shipment_id)
        ).scalar_one_or_none()

        upd_at = datetime.fromisoformat(item["updated_at"]) if item.get("updated_at") else datetime.utcnow()
        shipped_at = datetime.fromisoformat(item["shipped_at"]) if item.get("shipped_at") else datetime.utcnow()

        if existing:
            existing.order_id = str(item.get("order_id", existing.order_id))
            existing.shipped_at = shipped_at
            existing.quantity = int(item.get("quantity", existing.quantity))
            existing.carrier = str(item.get("carrier", existing.carrier))
            existing.status = str(item.get("status", existing.status))
            existing.updated_at = upd_at
        else:
            shipment = ShipmentModel(
                shipment_id=shipment_id,
                order_id=str(item.get("order_id", "")),
                shipped_at=shipped_at,
                quantity=int(item.get("quantity", 0)),
                carrier=str(item.get("carrier", "")),
                status=str(item.get("status", "IN_TRANSIT")),
                updated_at=upd_at,
            )
            session.add(shipment)
        session.flush()
        return True
