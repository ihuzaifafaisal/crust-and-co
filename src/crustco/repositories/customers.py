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
            (
                item
                for item in data.get("customers", [])
                if item["phone"] == normalized_phone
            ),
            None,
        )
        if customer is None:
            customer = {
                "id": max((item["id"] for item in data.get("customers", [])), default=0)
                + 1,
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
            (
                item
                for item in data.get("customers", [])
                if item["phone"] == normalized_phone
            ),
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
            # A customer can have only one default delivery address.
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
