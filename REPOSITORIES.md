# Repository Code

This file contains the current code from `src/crustco/repositories/`.

## `__init__.py`

```python
from .complaints import ComplaintRepository
from .customers import CustomerRepository
from .json_store import JsonDataStore
from .menu import MenuRepository
from .orders import OrderRepository

__all__ = [
    "ComplaintRepository",
    "CustomerRepository",
    "JsonDataStore",
    "MenuRepository",
    "OrderRepository",
]
```

## `json_store.py`

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "seed" / "mock_data.json"


def normalize_phone(phone: str) -> str:
    normalized = "".join(character for character in phone if character.isdigit())
    if normalized.startswith("00"):
        normalized = normalized[2:]
    if normalized.startswith("92"):
        return "+" + normalized
    if normalized.startswith("0"):
        normalized = normalized[1:]
    if len(normalized) < 10:
        raise ValueError("enter a valid phone number")
    return "+92" + normalized


class JsonDataStore:
    def __init__(self, path: str | Path = DATA_PATH) -> None:
        self.path = Path(path)

    def read(self) -> dict[str, list[dict[str, Any]]]:
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"unable to read mock data from {self.path}") from error
        if not isinstance(data, dict):
            raise RuntimeError("mock data must contain a JSON object")
        return data

    def write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        try:
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
                file.write("\n")
            temporary_path.replace(self.path)
        except OSError as error:
            raise RuntimeError(f"unable to write mock data to {self.path}") from error
```

## `menu.py`

```python
from __future__ import annotations

from .json_store import JsonDataStore


class MenuRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    async def list_menu(self) -> list[dict]:
        items = [
            item for item in self.store.read().get("menu_items", []) if item["is_available"]
        ]
        return [
            {
                "item_id": item["id"],
                "category": item["category"],
                "product": item["name"],
                "variant": item["size"],
                "description": item["description"],
                "price_rupees": item["price_rupees"],
                "modifiers": item["modifiers"],
            }
            for item in sorted(items, key=lambda item: (item["category"], item["id"]))
        ]

    async def add_to_cart(
        self, item_id: int, quantity: int, modifier_names: list[str]
    ) -> dict:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        item = next(
            (
                item
                for item in self.store.read().get("menu_items", [])
                if item["id"] == item_id and item["is_available"]
            ),
            None,
        )
        if item is None:
            raise ValueError("menu item was not found")
        available = {modifier["name"]: modifier for modifier in item["modifiers"]}
        if any(name not in available for name in modifier_names):
            raise ValueError("one or more modifiers are not available")
        return {
            "variant_id": item["id"],
            "product": item["name"],
            "variant": item["size"],
            "quantity": quantity,
            "unit_price_rupees": item["price_rupees"],
            "modifiers": [available[name] for name in modifier_names],
        }
```

## `customers.py`

```python
from __future__ import annotations

from ..services.geocoding import geocode
from .json_store import JsonDataStore, normalize_phone


class CustomerRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    @staticmethod
    def _result(customer: dict, data: dict) -> dict:
        return {
            "id": customer["id"],
            "phone": customer["phone"],
            "name": customer.get("name"),
            "addresses": [
                address
                for address in data.get("customer_addresses", [])
                if address["customer_id"] == customer["id"]
            ],
        }

    async def get_or_create(self, phone: str, name: str | None = None) -> dict:
        normalized_phone = normalize_phone(phone)
        data = self.store.read()
        customer = next(
            (item for item in data.get("customers", []) if item["phone"] == normalized_phone),
            None,
        )
        if customer is None:
            customer = {
                "id": max((item["id"] for item in data.get("customers", [])), default=0) + 1,
                "phone": normalized_phone,
                "name": name,
            }
            data.setdefault("customers", []).append(customer)
            self.store.write(data)
        elif name and customer.get("name") != name:
            customer["name"] = name
            self.store.write(data)
        return self._result(customer, data)

    async def find(self, phone: str) -> dict | None:
        normalized_phone = normalize_phone(phone)
        data = self.store.read()
        customer = next(
            (item for item in data.get("customers", []) if item["phone"] == normalized_phone),
            None,
        )
        return self._result(customer, data) if customer else None

    async def add_address(
        self,
        customer_id: int,
        label: str,
        address_text: str,
        is_default: bool = False,
    ) -> dict:
        if not label.strip() or not address_text.strip():
            raise ValueError("address label and address are required")
        data = self.store.read()
        if not any(item["id"] == customer_id for item in data.get("customers", [])):
            raise ValueError("customer was not found")
        coordinates = await geocode(address_text)
        addresses = data.setdefault("customer_addresses", [])
        if is_default:
            for saved in addresses:
                if saved["customer_id"] == customer_id:
                    saved["is_default"] = False
        address = {
            "id": max((item["id"] for item in addresses), default=0) + 1,
            "customer_id": customer_id,
            "label": label.strip(),
            "address": address_text.strip(),
            "latitude": coordinates.latitude,
            "longitude": coordinates.longitude,
            "is_default": is_default,
        }
        addresses.append(address)
        self.store.write(data)
        return {key: value for key, value in address.items() if key != "customer_id"}
```

## `orders.py`

```python
from __future__ import annotations

from datetime import UTC, datetime
from math import asin, cos, radians, sin, sqrt

from .json_store import JsonDataStore


class OrderRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    @staticmethod
    def _distance(address: dict, branch: dict) -> float:
        latitude_delta = radians(branch["latitude"] - address["latitude"])
        longitude_delta = radians(branch["longitude"] - address["longitude"])
        value = (
            sin(latitude_delta / 2) ** 2
            + cos(radians(address["latitude"]))
            * cos(radians(branch["latitude"]))
            * sin(longitude_delta / 2) ** 2
        )
        return 6371 * 2 * asin(sqrt(value))

    async def get_status(self, customer_id: int, order_id: int | None = None) -> dict | None:
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
            (item["name"] for item in data.get("branches", []) if item["id"] == order["branch_id"]),
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
        self, customer_id: int, address_id: int | None, fulfillment_type: str, cart: list[dict]
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
        branch = (
            min(branches, key=lambda item: self._distance(address, item))
            if fulfillment_type == "delivery" and address
            else (branches[0] if branches else None)
        )
        if branch is None:
            raise ValueError("no branch serves this order")
        fee = 150 if fulfillment_type == "delivery" else 0
        total = sum(
            (item["price_rupees"] + sum(modifier["price_delta_rupees"] for modifier in modifiers))
            * quantity
            for item, quantity, modifiers in items
        ) + fee
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
```

## `complaints.py`

```python
from __future__ import annotations

from datetime import UTC, datetime

from .json_store import JsonDataStore


class ComplaintRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    async def create(self, customer_id: int, message: str, order_id: int | None = None) -> dict:
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
            "id": max((item["id"] for item in data.get("complaints", [])), default=0) + 1,
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
```
