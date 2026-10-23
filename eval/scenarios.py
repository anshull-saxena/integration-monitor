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


def generate_scenario_matrix(num_runs_per_type: int = 5) -> List[EvaluationScenario]:
    """Generates an extensive, randomized test matrix with multiple seeds, varying noise levels,

    subtle edge-cases, and clean baseline runs.
    """
    scenarios: List[EvaluationScenario] = []

    # 1. Clean Baseline Runs (Normal operations)
    for i in range(1, 11):
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-CLEAN-{i:02d}",
                name=f"Clean Production Run #{i}",
                description="Clean upstream data across orders, suppliers, and shipments",
                expected_fault_type="none",
                faults=[],
                cycles_to_run=1,
            )
        )

    # 2. Schema Drift variations (some subtle drift in optional vs mandatory fields)
    for i in range(1, 6):
        field = "status" if i % 2 == 0 else "contact_email"
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-SCHEMA-{i:02d}",
                name=f"Schema Drift #{i} on {field}",
                description=f"Altered field name for {field}",
                expected_fault_type="schema_drift" if field == "status" else "none",  # optional field drift shouldn't fail required checks
                faults=[
                    FaultConfig(
                        fault_type="schema_drift",
                        target_service="orders" if field == "status" else "suppliers",
                        probability=1.0 if i < 5 else 0.4,
                        seed=100 + i,
                        params={"field": field, "new_field": f"{field}_v2"},
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 3. Null Spikes (various columns, some high rate, some borderline low rate)
    for i in range(1, 6):
        field = "order_id" if i % 2 == 1 else "supplier_id"
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-NULL-{i:02d}",
                name=f"Null Spike #{i} on {field}",
                description=f"Injected nulls in {field}",
                expected_fault_type="null_spike",
                faults=[
                    FaultConfig(
                        fault_type="null_spike",
                        target_service="orders",
                        probability=0.3 + (i * 0.14),
                        seed=200 + i,
                        params={"field": field},
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 4. Duplicates (varying duplicate rate)
    for i in range(1, 6):
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-DUP-{i:02d}",
                name=f"Duplicate Keys #{i}",
                description="Emitted duplicate shipment primary keys",
                expected_fault_type="duplicates",
                faults=[
                    FaultConfig(
                        fault_type="duplicates",
                        target_service="shipments",
                        probability=0.5 if i == 1 else 1.0,
                        seed=300 + i,
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 5. Late Data / Freshness Breaches (varying staleness from 15 days to 200 days)
    for i in range(1, 6):
        days = 15 if i == 1 else (30 * i)  # 15 days is below 30d threshold -> shouldn't trigger
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-LATE-{i:02d}",
                name=f"Late Data #{i} ({days} days old)",
                description=f"Updated_at timestamps {days} days ago",
                expected_fault_type="late_data" if days > 30 else "none",
                faults=[
                    FaultConfig(
                        fault_type="late_data",
                        target_service="orders",
                        probability=1.0,
                        seed=400 + i,
                        params={"days_ago": days, "date_field": "updated_at"},
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 6. HTTP 500 / Network Failures
    for i in range(1, 6):
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-HTTP-{i:02d}",
                name=f"HTTP 500 Server Outage #{i}",
                description="Upstream 500 error triggered on orders service",
                expected_fault_type="http_500",
                faults=[
                    FaultConfig(
                        fault_type="http_500",
                        target_service="orders",
                        probability=1.0 if i > 1 else 0.5,
                        seed=500 + i,
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 7. Mismatched IDs / Orphan Foreign Keys
    for i in range(1, 6):
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-MISMATCH-{i:02d}",
                name=f"Orphan Foreign Key #{i}",
                description="Orders referencing nonexistent supplier",
                expected_fault_type="mismatched_ids",
                faults=[
                    FaultConfig(
                        fault_type="mismatched_ids",
                        target_service="orders",
                        probability=1.0 if i > 1 else 0.6,
                        seed=600 + i,
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 8. Silent Corruption (Negative values vs Quantity mismatches)
    for i in range(1, 6):
        c_type = "negative_value" if i % 2 == 1 else "quantity_mismatch"
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-CORRUPT-{i:02d}",
                name=f"Silent Corruption #{i} ({c_type})",
                description=f"Corrupted fields with {c_type}",
                expected_fault_type="silent_corruption",
                faults=[
                    FaultConfig(
                        fault_type="silent_corruption",
                        target_service="orders" if c_type == "negative_value" else "shipments",
                        probability=1.0 if i > 1 else 0.5,
                        seed=700 + i,
                        params={"corruption_type": c_type},
                    )
                ],
                cycles_to_run=1,
            )
        )

    # 9. Volume Drops (moderate drop vs severe drop)
    for i in range(1, 6):
        scenarios.append(
            EvaluationScenario(
                scenario_id=f"SCEN-VOL-{i:02d}",
                name=f"Volume Drop #{i}",
                description="Orders service returns truncated batch",
                expected_fault_type="volume_drop",
                faults=[
                    FaultConfig(
                        fault_type="volume_drop",
                        target_service="orders",
                        probability=1.0 if i > 1 else 0.5,
                        seed=800 + i,
                    )
                ],
                cycles_to_run=1,
            )
        )

    return scenarios


EVALUATION_SCENARIOS: List[EvaluationScenario] = generate_scenario_matrix()
