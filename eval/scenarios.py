from typing import List
from pydantic import BaseModel
from src.mock_services.fault_injection import FaultConfig


class EvaluationScenario(BaseModel):
    scenario_id: str
    name: str
    description: str
    expected_fault_type: str
    faults: List[FaultConfig]
    cycles_to_run: int = 1


EVALUATION_SCENARIOS: List[EvaluationScenario] = [
    EvaluationScenario(
        scenario_id="SCEN-00-CLEAN",
        name="Clean Baseline Run",
        description="Normal operation without any injected faults; tests false-positive rate",
        expected_fault_type="none",
        faults=[],
        cycles_to_run=2,
    ),
    EvaluationScenario(
        scenario_id="SCEN-01-SCHEMA-DRIFT",
        name="Schema Drift in Status Field",
        description="Orders service renames 'status' to 'status_v2' causing parse/schema anomaly",
        expected_fault_type="schema_drift",
        faults=[
            FaultConfig(
                fault_type="schema_drift",
                target_service="orders",
                probability=1.0,
                seed=101,
                params={"field": "status", "new_field": "status_v2"},
            )
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-02-NULL-SPIKE",
        name="Null Spike in Mandatory Order Key",
        description="Orders service emits null order_id keys violating nullability constraints",
        expected_fault_type="null_spike",
        faults=[
            FaultConfig(
                fault_type="null_spike",
                target_service="orders",
                probability=1.0,
                seed=102,
                params={"field": "order_id"},
            )
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-03-DUPLICATES",
        name="Duplicate Primary Keys in Batch",
        description="Shipments service emits duplicate shipment_id records",
        expected_fault_type="duplicates",
        faults=[
            FaultConfig(
                fault_type="duplicates",
                target_service="shipments",
                probability=1.0,
                seed=103,
            )
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-04-LATE-DATA",
        name="Stale Timestamps (Late Data)",
        description="Orders service emits records with updated_at timestamps 180 days in the past",
        expected_fault_type="late_data",
        faults=[
            FaultConfig(
                fault_type="late_data",
                target_service="orders",
                probability=1.0,
                seed=104,
                params={"days_ago": 180, "date_field": "updated_at"},
            )
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-05-HTTP-500",
        name="Upstream 500 Server Errors",
        description="Orders service intermittently fails with 500 error; triggers tenacity retries and DLQ routing",
        expected_fault_type="http_500",
        faults=[
            FaultConfig(
                fault_type="http_500",
                target_service="orders",
                probability=1.0,
                seed=105,
            )
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-06-MISMATCHED-IDS",
        name="Orphan Foreign Key References",
        description="Orders service emits purchase orders referencing non-existent supplier IDs",
        expected_fault_type="mismatched_ids",
        faults=[
            FaultConfig(
                fault_type="mismatched_ids",
                target_service="orders",
                probability=1.0,
                seed=106,
            )
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-07-SILENT-CORRUPTION",
        name="Quantity Mismatch and Negative Amounts",
        description="Shipments emit quantities exceeding order items; orders emit negative total_amount",
        expected_fault_type="silent_corruption",
        faults=[
            FaultConfig(
                fault_type="silent_corruption",
                target_service="orders",
                probability=1.0,
                seed=107,
                params={"corruption_type": "negative_value"},
            ),
            FaultConfig(
                fault_type="silent_corruption",
                target_service="shipments",
                probability=1.0,
                seed=108,
                params={"corruption_type": "quantity_mismatch"},
            ),
        ],
        cycles_to_run=1,
    ),
    EvaluationScenario(
        scenario_id="SCEN-08-VOLUME-DROP",
        name="Sudden Upstream Volume Drop",
        description="Orders service returns a truncated payload below baseline threshold",
        expected_fault_type="volume_drop",
        faults=[
            FaultConfig(
                fault_type="volume_drop",
                target_service="orders",
                probability=1.0,
                seed=109,
            )
        ],
        cycles_to_run=1,
    ),
]
