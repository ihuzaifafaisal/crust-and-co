from __future__ import annotations

from .json_store import JsonDataStore


class MenuRepository:
    def __init__(self, store: JsonDataStore | None = None) -> None:
        self.store = store or JsonDataStore()

    async def list_menu(self) -> list[dict]:
        items = [
            item
            for item in self.store.read().get("menu_items", [])
            if item["is_available"]
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
        # Re-read the menu so cart prices and modifiers always come from the seed data.
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
