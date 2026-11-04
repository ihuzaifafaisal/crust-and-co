from __future__ import annotations

from datetime import UTC, datetime

from .json_store import JsonDataStore


class ComplaintRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    async def create(
        self, customer_id: int, message: str, order_id: int | None = None
    ) -> dict:
        cleaned_message = message.strip()
        if not cleaned_message:
            raise ValueError("complaint details are required")
        data = self.store.read()
        if not any(item["id"] == customer_id for item in data.get("customers", [])):
            raise ValueError("customer was not found")
        if order_id is not None and not any(
            item["id"] == order_id and item["customer_id"] == customer_id
            for item in data.get("orders", [])
        ):
            raise ValueError("order was not found for this customer")
        existing = next(
            (
                item
                for item in reversed(data.get("complaints", []))
                if item["customer_id"] == customer_id
                and item.get("order_id") == order_id
                and item["message"] == cleaned_message
                and item["status"] == "open"
            ),
            None,
        )
        if existing:
            return {
                "complaint_id": existing["id"],
                "status": existing["status"],
                "order_id": existing.get("order_id"),
                "message": existing["message"],
                "duplicate": True,
            }
        complaint = {
            "id": max((item["id"] for item in data.get("complaints", [])), default=0)
            + 1,
            "customer_id": customer_id,
            "order_id": order_id,
            "message": cleaned_message,
            "status": "open",
            "created_at": datetime.now(UTC).isoformat(),
        }
        data.setdefault("complaints", []).append(complaint)
        self.store.write(data)
        return {
            "complaint_id": complaint["id"],
            "status": complaint["status"],
            "order_id": order_id,
            "message": cleaned_message,
            "duplicate": False,
        }
