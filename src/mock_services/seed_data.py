from datetime import datetime, timedelta
from typing import List, Dict, Any

def get_clean_suppliers() -> List[Dict[str, Any]]:
    now = datetime.utcnow()
    return [
        {
            "supplier_id": f"SUPP-{i:03d}",
            "name": f"Supplier Partner {chr(65 + (i % 26))} Ltd",
            "country": ["USA", "Germany", "Japan", "India", "UK"][i % 5],
            "contact_email": f"contact@supplier{i:03d}.com",
            "status": "ACTIVE" if i % 10 != 0 else "INACTIVE",
            "updated_at": (now - timedelta(minutes=i * 5)).isoformat(),
        }
        for i in range(1, 31)
    ]


def get_clean_orders() -> List[Dict[str, Any]]:
    now = datetime.utcnow()
    return [
        {
            "order_id": f"ORD-{i:04d}",
            "supplier_id": f"SUPP-{(i % 25) + 1:03d}",  # all reference valid suppliers
            "order_date": (now - timedelta(minutes=i * 5 + 10)).isoformat(),
            "total_amount": round(50.0 + (i * 17.5) % 1500, 2),
            "items_count": (i % 15) + 1,
            # In clean data, confirmed or pending orders only for items that will ship
            "status": "CONFIRMED" if i % 2 == 0 else "PENDING",
            "updated_at": (now - timedelta(minutes=i * 5)).isoformat(),
        }
        for i in range(1, 61)
    ]


def get_clean_shipments() -> List[Dict[str, Any]]:
    now = datetime.utcnow()
    return [
        {
            "shipment_id": f"SHIP-{i:04d}",
            "order_id": f"ORD-{i:04d}",
            "shipped_at": (now - timedelta(minutes=i * 5 + 5)).isoformat(),
            # Exactly matches order items_count
            "quantity": (i % 15) + 1,
            "carrier": ["FedEx", "DHL", "UPS", "Maersk"][i % 4],
            "status": "DELIVERED" if i % 2 == 0 else "IN_TRANSIT",
            "updated_at": (now - timedelta(minutes=i * 5)).isoformat(),
        }
        for i in range(1, 41)
    ]


DEFAULT_SUPPLIERS: List[Dict[str, Any]] = get_clean_suppliers()
DEFAULT_ORDERS: List[Dict[str, Any]] = get_clean_orders()
DEFAULT_SHIPMENTS: List[Dict[str, Any]] = get_clean_shipments()
