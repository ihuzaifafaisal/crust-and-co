from __future__ import annotations

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt

from .json_store import JsonDataStore


class OrderRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    @staticmethod
    def _distance(address: dict, branch: dict) -> float:
        # Haversine distance is sufficient for choosing among nearby Lahore branches.
        latitude_delta = radians(branch["latitude"] - address["latitude"])
        longitude_delta = radians(branch["longitude"] - address["longitude"])
        value = (
            sin(latitude_delta / 2) ** 2
            + cos(radians(address["latitude"]))
            * cos(radians(branch["latitude"]))
            * sin(longitude_delta / 2) ** 2
        )
        return 6371 * 2 * asin(sqrt(value))

    async def get_status(
        self, customer_id: int, order_id: int | None = None
    ) -> dict | None:
        data = self.store.read()
        orders = [
            order
            for order in data.get("orders", [])
            if order["customer_id"] == customer_id
            and (order_id is None or order["id"] == order_id)
        ]
        if not orders:
            return None
        order = max(orders, key=lambda item: item.get("created_at", ""))
        branch = next(
            (
                item["name"]
                for item in data.get("branches", [])
                if item["id"] == order["branch_id"]
            ),
            "Unknown",
        )
        return {
            "order_id": order["id"],
            "status": order["status"],
            "fulfillment_type": order["fulfillment_type"],
            "total_rupees": order["total_rupees"],
            "branch": branch,
            "status_history": [
                event
                for event in data.get("order_status_history", [])
                if event["order_id"] == order["id"]
            ],
        }

    async def place_order(
        self,
        customer_id: int,
        address_id: int | None,
        fulfillment_type: str,
        cart: list[dict],
    ) -> dict:
        if fulfillment_type not in {"delivery", "takeaway"}:
            raise ValueError("fulfillment type must be delivery or takeaway")
        if not cart:
            raise ValueError("cart is empty")
        data = self.store.read()
        if not any(item["id"] == customer_id for item in data.get("customers", [])):
            raise ValueError("customer was not found")
        if fulfillment_type == "delivery" and address_id is None:
            raise ValueError("a delivery address is required")
        if address_id is not None and not any(
            item["id"] == address_id and item["customer_id"] == customer_id
            for item in data.get("customer_addresses", [])
        ):
            raise ValueError("delivery address was not found")
        address = next(
            (
                item
                for item in data.get("customer_addresses", [])
                if item["id"] == address_id and item["customer_id"] == customer_id
            ),
            None,
        )
        if fulfillment_type == "delivery" and (
            address is None
            or address.get("latitude") is None
            or address.get("longitude") is None
        ):
            raise ValueError("delivery address location is unavailable")
        items = []
        for raw in cart:
            item = next(
                (
                    item
                    for item in data.get("menu_items", [])
                    if item["id"] == raw.get("variant_id") and item["is_available"]
                ),
                None,
            )
            quantity = raw.get("quantity", 0)
            if item is None or not isinstance(quantity, int) or quantity < 1:
                raise ValueError("cart contains an unavailable item")
            allowed = {modifier["name"]: modifier for modifier in item["modifiers"]}
            modifiers = raw.get("modifiers", [])
            if any(modifier["name"] not in allowed for modifier in modifiers):
                raise ValueError("cart contains an unavailable modifier")
            items.append((item, quantity, modifiers))
        branches = [item for item in data.get("branches", []) if item["is_active"]]
        # Takeaway orders use the first active branch; deliveries use the nearest one.
        branch = (
            min(branches, key=lambda item: self._distance(address, item))
            if fulfillment_type == "delivery" and address
            else (branches[0] if branches else None)
        )
        if branch is None:
            raise ValueError("no branch serves this order")
        fee = 150 if fulfillment_type == "delivery" else 0
        total = (
            sum(
                (
                    item["price_rupees"]
                    + sum(modifier["price_delta_rupees"] for modifier in modifiers)
                )
                * quantity
                for item, quantity, modifiers in items
            )
            + fee
        )
        order_id = max((item["id"] for item in data.get("orders", [])), default=0) + 1
        now = datetime.now(UTC).isoformat()
        data.setdefault("orders", []).append(
            {
                "id": order_id,
                "customer_id": customer_id,
                "branch_id": branch["id"],
                "status": "pending",
                "fulfillment_type": fulfillment_type,
                "total_rupees": total,
                "created_at": now,
            }
        )
        data.setdefault("order_status_history", []).append(
            {"order_id": order_id, "status": "pending", "changed_at": now, "note": None}
        )
        self.store.write(data)
        return {
            "order_id": order_id,
            "status": "pending",
            "branch": branch["name"],
            "fulfillment_type": fulfillment_type,
            "total_rupees": total,
        }
