import random
import copy
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel


class FaultConfig(BaseModel):
    fault_type: str
    target_service: str  # orders, suppliers, shipments
    probability: float = 1.0
    seed: Optional[int] = 42
    params: Dict[str, Any] = {}


class FaultEvent(BaseModel):
    fault_id: str
    scenario_id: str
    target_service: str
    fault_type: str
    affected_ids: List[str]
    details: Dict[str, Any]
    injected_at: str


class FaultInjectionEngine:
    """Manages seeded fault injections and ground truth ledger for mock services."""

    def __init__(self, seed: int = 42):
        self.seed = seed
        self.rng = random.Random(seed)
        self.active_faults: List[FaultConfig] = []
        self.ground_truth_ledger: List[FaultEvent] = []

    def set_seed(self, seed: int) -> None:
        self.seed = seed
        self.rng = random.Random(seed)

    def register_fault(self, fault: FaultConfig) -> None:
        self.active_faults.append(fault)

    def clear_faults(self) -> None:
        self.active_faults = []

    def clear_ledger(self) -> None:
        self.ground_truth_ledger = []

    def get_ledger(self) -> List[FaultEvent]:
        return self.ground_truth_ledger

    def apply_service_faults(
        self,
        service_name: str,
        records: List[Dict[str, Any]],
        scenario_id: str = "adhoc",
    ) -> List[Dict[str, Any]]:
        """Transforms a batch of service records according to active fault rules."""
        records = copy.deepcopy(records)
        matching_faults = [f for f in self.active_faults if f.target_service == service_name]

        for fault in matching_faults:
            if fault.seed is not None:
                self.rng = random.Random(fault.seed)

            # Check probability
            if self.rng.random() > fault.probability:
                continue

            records = self._execute_fault(fault, service_name, records, scenario_id)

        return records

    def _execute_fault(
        self,
        fault: FaultConfig,
        service_name: str,
        records: List[Dict[str, Any]],
        scenario_id: str,
    ) -> List[Dict[str, Any]]:
        fault_type = fault.fault_type
        affected_ids = []
        details = {}

        if fault_type == "schema_drift":
            # Renames an expected key or alters structure
            drift_field = fault.params.get("field", "status")
            new_field = fault.params.get("new_field", f"{drift_field}_v2")
            for r in records[:3]:
                if drift_field in r:
                    key_id = r.get("order_id") or r.get("supplier_id") or r.get("shipment_id")
                    if key_id:
                        affected_ids.append(str(key_id))
                    r[new_field] = r.pop(drift_field)
            details = {"drift_field": drift_field, "new_field": new_field}

        elif fault_type == "null_spike":
            # Injects nulls into mandatory columns
            null_field = fault.params.get("field", "order_id" if service_name == "orders" else "name")
            for r in records[:4]:
                key_id = r.get("order_id") or r.get("supplier_id") or r.get("shipment_id")
                if key_id:
                    affected_ids.append(str(key_id))
                r[null_field] = None
            details = {"null_field": null_field, "count": len(affected_ids)}

        elif fault_type == "duplicates":
            # Injects duplicate records with identical primary keys
            if records:
                dup_count = min(3, len(records))
                dups = copy.deepcopy(records[:dup_count])
                for d in dups:
                    key_id = d.get("order_id") or d.get("supplier_id") or d.get("shipment_id")
                    if key_id:
                        affected_ids.append(str(key_id))
                records = dups + records
            details = {"duplicated_records": affected_ids}

        elif fault_type == "late_data":
            # Emits stale timestamps far in the past (e.g. 180 days ago)
            stale_days = fault.params.get("days_ago", 180)
            date_field = fault.params.get("date_field", "updated_at")
            for r in records[:5]:
                key_id = r.get("order_id") or r.get("supplier_id") or r.get("shipment_id")
                if key_id:
                    affected_ids.append(str(key_id))
                r[date_field] = (datetime.utcnow() - timedelta(days=stale_days)).isoformat()
            details = {"stale_days": stale_days, "date_field": date_field}

        elif fault_type == "mismatched_ids":
            # Injects orphan references (e.g., supplier_id that does not exist in suppliers)
            if service_name == "orders":
                ref_field = "supplier_id"
                dummy_val = "SUPP-GHOST-999"
            elif service_name == "shipments":
                ref_field = "order_id"
                dummy_val = "ORD-GHOST-9999"
            else:
                ref_field = "parent_id"
                dummy_val = "ORPHAN-000"

            for r in records[:4]:
                key_id = r.get("order_id") or r.get("supplier_id") or r.get("shipment_id")
                if key_id:
                    affected_ids.append(str(key_id))
                r[ref_field] = dummy_val
            details = {"reference_field": ref_field, "injected_orphan_id": dummy_val}

        elif fault_type == "silent_corruption":
            # Inconsistent or corrupt values: negative quantities or mismatched order counts
            corrupt_type = fault.params.get("corruption_type", "negative_value")
            if corrupt_type == "negative_value":
                field = "total_amount" if service_name == "orders" else "quantity"
                for r in records[:3]:
                    key_id = r.get("order_id") or r.get("supplier_id") or r.get("shipment_id")
                    if key_id:
                        affected_ids.append(str(key_id))
                    r[field] = -abs(r.get(field, 10))
                details = {"field": field, "corruption_type": "negative_value"}
            elif corrupt_type == "quantity_mismatch":
                # shipments quantity vastly exceeds order items_count
                for r in records[:3]:
                    key_id = r.get("shipment_id")
                    if key_id:
                        affected_ids.append(str(key_id))
                    r["quantity"] = 99999  # absurd quantity guaranteed to mismatch order
                details = {"field": "quantity", "corruption_type": "quantity_mismatch"}
            elif corrupt_type == "status_mismatch":
                for r in records[:3]:
                    key_id = r.get("shipment_id")
                    if key_id:
                        affected_ids.append(str(key_id))
                    r["status"] = "DELIVERED"
                details = {"field": "status", "corruption_type": "status_mismatch_with_cancelled_order"}

        elif fault_type == "volume_drop":
            # Ingest volume drops severely (e.g. only 1 record returned)
            original_len = len(records)
            records = records[:1]
            affected_ids = [str(r.get("order_id") or r.get("supplier_id") or r.get("shipment_id")) for r in records]
            details = {"original_count": original_len, "reduced_count": len(records)}

        if affected_ids:
            event = FaultEvent(
                fault_id=f"FAULT-{len(self.ground_truth_ledger)+1:04d}",
                scenario_id=scenario_id,
                target_service=service_name,
                fault_type=fault_type,
                affected_ids=affected_ids,
                details=details,
                injected_at=datetime.utcnow().isoformat(),
            )
            self.ground_truth_ledger.append(event)

        return records

    def check_http_fault(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Returns error specification if an HTTP fault (500 or timeout) should trigger."""
        for fault in self.active_faults:
            if fault.target_service == service_name and fault.fault_type in ("http_500", "http_timeout"):
                if fault.seed is not None:
                    self.rng = random.Random(fault.seed)
                if self.rng.random() <= fault.probability:
                    event = FaultEvent(
                        fault_id=f"FAULT-{len(self.ground_truth_ledger)+1:04d}",
                        scenario_id=fault.params.get("scenario_id", "adhoc"),
                        target_service=service_name,
                        fault_type=fault.fault_type,
                        affected_ids=["HTTP_REQUEST"],
                        details=fault.params,
                        injected_at=datetime.utcnow().isoformat(),
                    )
                    self.ground_truth_ledger.append(event)
                    return {"type": fault.fault_type, "params": fault.params}
        return None


# Global singleton engine for mock services in local/compose processes
global_fault_engine = FaultInjectionEngine(seed=42)
