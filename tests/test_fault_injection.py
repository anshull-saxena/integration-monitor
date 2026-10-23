from src.mock_services.fault_injection import (
    FaultInjectionEngine,
    FaultConfig,
)
from src.mock_services.seed_data import DEFAULT_ORDERS, DEFAULT_SHIPMENTS


def test_seeded_reproducibility():
    f1 = FaultInjectionEngine(seed=123)
    f2 = FaultInjectionEngine(seed=123)

    cfg = FaultConfig(
        fault_type="silent_corruption",
        target_service="orders",
        probability=1.0,
        seed=123,
        params={"corruption_type": "negative_value"},
    )
    f1.register_fault(cfg)
    f2.register_fault(cfg)

    res1 = f1.apply_service_faults("orders", DEFAULT_ORDERS, scenario_id="test_repro")
    res2 = f2.apply_service_faults("orders", DEFAULT_ORDERS, scenario_id="test_repro")

    assert res1 == res2
    ledger1 = f1.get_ledger()
    ledger2 = f2.get_ledger()
    assert len(ledger1) == len(ledger2)
    assert ledger1[0].affected_ids == ledger2[0].affected_ids


def test_ground_truth_ledger_records_all_faults():
    engine = FaultInjectionEngine(seed=999)

    engine.register_fault(
        FaultConfig(
            fault_type="schema_drift",
            target_service="orders",
            probability=1.0,
            params={"field": "status", "new_field": "order_status_v2"},
        )
    )
    engine.register_fault(
        FaultConfig(
            fault_type="mismatched_ids",
            target_service="shipments",
            probability=1.0,
        )
    )

    _out_orders = engine.apply_service_faults("orders", DEFAULT_ORDERS, scenario_id="scen_1")
    _out_shipments = engine.apply_service_faults("shipments", DEFAULT_SHIPMENTS, scenario_id="scen_1")

    ledger = engine.get_ledger()
    assert len(ledger) == 2

    fault_types = [item.fault_type for item in ledger]
    assert "schema_drift" in fault_types
    assert "mismatched_ids" in fault_types
    assert all(len(item.affected_ids) > 0 for item in ledger)
