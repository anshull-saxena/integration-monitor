from fastapi.testclient import TestClient
from src.mock_services.app import app

client = TestClient(app)


def setup_function():
    client.post("/faults/reset")


def test_clean_service_endpoints():
    res_s = client.get("/suppliers?page=1&page_size=5")
    assert res_s.status_code == 200
    data_s = res_s.json()
    assert len(data_s["items"]) == 5
    assert data_s["items"][0]["supplier_id"].startswith("SUPP-")

    res_o = client.get("/orders?page=1&page_size=5")
    assert res_o.status_code == 200
    data_o = res_o.json()
    assert len(data_o["items"]) == 5
    assert data_o["items"][0]["order_id"].startswith("ORD-")

    res_sh = client.get("/shipments?page=1&page_size=5")
    assert res_sh.status_code == 200
    data_sh = res_sh.json()
    assert len(data_sh["items"]) == 5
    assert data_sh["items"][0]["shipment_id"].startswith("SHIP-")


def test_fault_injection_null_spike():
    res = client.post(
        "/faults/inject",
        json={
            "fault_type": "null_spike",
            "target_service": "orders",
            "probability": 1.0,
            "params": {"field": "order_id"},
        },
    )
    assert res.status_code == 200

    fetch = client.get("/orders?page=1&page_size=10")
    items = fetch.json()["items"]
    # Check that nulls were injected
    null_count = sum(1 for item in items if item.get("order_id") is None)
    assert null_count > 0

    ledger_res = client.get("/faults/ledger")
    ledger = ledger_res.json()
    assert len(ledger) >= 1
    assert ledger[0]["fault_type"] == "null_spike"
    assert ledger[0]["target_service"] == "orders"


def test_fault_injection_http_500():
    res = client.post(
        "/faults/inject",
        json={
            "fault_type": "http_500",
            "target_service": "orders",
            "probability": 1.0,
        },
    )
    assert res.status_code == 200
    fetch = client.get("/orders?page=1&page_size=10")
    assert fetch.status_code == 500
