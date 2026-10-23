import time
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query, status
from pydantic import BaseModel
from src.mock_services.seed_data import (
    DEFAULT_ORDERS,
    DEFAULT_SUPPLIERS,
    DEFAULT_SHIPMENTS,
    get_clean_suppliers,
    get_clean_orders,
    get_clean_shipments,
)
from src.mock_services.fault_injection import (
    global_fault_engine,
    FaultConfig,
    FaultEvent,
)

app = FastAPI(title="Mock Upstream Systems & Fault Injector", version="1.0.0")

# In-memory storage of upstream datasets
data_store: Dict[str, List[Dict[str, Any]]] = {
    "suppliers": [dict(s) for s in DEFAULT_SUPPLIERS],
    "orders": [dict(o) for o in DEFAULT_ORDERS],
    "shipments": [dict(sh) for sh in DEFAULT_SHIPMENTS],
}


class FaultInjectRequest(BaseModel):
    fault_type: str
    target_service: str  # orders, suppliers, shipments
    probability: float = 1.0
    seed: Optional[int] = 42
    params: Dict[str, Any] = {}
    scenario_id: Optional[str] = "adhoc"


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/faults/inject")
def inject_fault(req: FaultInjectRequest):
    cfg = FaultConfig(
        fault_type=req.fault_type,
        target_service=req.target_service,
        probability=req.probability,
        seed=req.seed,
        params=req.params,
    )
    global_fault_engine.register_fault(cfg)
    return {"status": "fault_registered", "config": cfg.model_dump()}


@app.post("/faults/reset")
def reset_faults():
    global_fault_engine.clear_faults()
    global_fault_engine.clear_ledger()
    # Reset datasets to clean seed state
    data_store["suppliers"] = get_clean_suppliers()
    data_store["orders"] = get_clean_orders()
    data_store["shipments"] = get_clean_shipments()
    return {"status": "reset_complete"}


@app.get("/faults/ledger", response_model=List[FaultEvent])
def get_fault_ledger():
    return global_fault_engine.get_ledger()


def paginate_and_inject(service_name: str, page: int, page_size: int, scenario_id: str):
    # Check for HTTP 500 or timeout faults
    http_fault = global_fault_engine.check_http_fault(service_name)
    if http_fault:
        if http_fault["type"] == "http_500":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Injected upstream 500 error in {service_name}",
            )
        elif http_fault["type"] == "http_timeout":
            sleep_duration = http_fault["params"].get("sleep_seconds", 6.0)
            time.sleep(sleep_duration)

    all_records = data_store[service_name]
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    sliced = all_records[start_idx:end_idx]

    # Apply data-level fault injections
    processed_records = global_fault_engine.apply_service_faults(
        service_name=service_name,
        records=sliced,
        scenario_id=scenario_id,
    )

    total_records = len(all_records)
    has_next = end_idx < total_records

    return {
        "service": service_name,
        "page": page,
        "page_size": page_size,
        "total": total_records,
        "has_next": has_next,
        "items": processed_records,
    }


@app.get("/suppliers")
def get_suppliers(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    scenario_id: str = Query("default"),
):
    return paginate_and_inject("suppliers", page, page_size, scenario_id)


@app.get("/orders")
def get_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    scenario_id: str = Query("default"),
):
    return paginate_and_inject("orders", page, page_size, scenario_id)


@app.get("/shipments")
def get_shipments(
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    scenario_id: str = Query("default"),
):
    return paginate_and_inject("shipments", page, page_size, scenario_id)
