from __future__ import annotations

import json

from livekit.agents import Agent, RunContext, function_tool

from ..orchestration.conversation import VOICE_OUTPUT_RULES
from ..orchestration.handoffs import transfer
from ..orchestration.state import CartItem, RestaurantSessionState
from ..repositories import CustomerRepository, MenuRepository, OrderRepository


class OrderAgent(Agent):
    def __init__(
        self,
        menu: MenuRepository | None = None,
        customers: CustomerRepository | None = None,
        orders: OrderRepository | None = None,
    ) -> None:
        self.menu = menu or MenuRepository()
        self.customers = customers or CustomerRepository()
        self.orders = orders or OrderRepository()
        super().__init__(
            instructions=(
                "You are the Crust & Co. order specialist. Help the caller plan a new "
                "order using the menu tools. Keep the caller's selected language. "
                "Do not claim an order was placed: this milestone only builds an "
                "in-memory cart. Before placing an order, collect the customer phone, "
                "assuming Pakistan unless the caller clearly says otherwise; do not "
                "ask for a country code. "
                "delivery address for delivery orders, and fulfillment type. Call "
                "place_order only after the caller clearly confirms the cart. Once "
                "the caller is done planning, return to the receptionist so they can "
                "choose the main menu or end the call. A newly completed order is not "
                "an existing-order status request. If the caller says goodbye or "
                "wants to end the call, say goodbye and call end_call instead of "
                "returning to the receptionist. "
                "Transfer to the status specialist "
                "only when the caller explicitly asks about an existing order's status. "
                "Transfer complaints to the complaint specialist. " + VOICE_OUTPUT_RULES
            )
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Briefly acknowledge the handoff and ask what the caller would like "
                "to order. Do not repeat the opening greeting or language question."
            )
        )

    @function_tool
    async def show_menu(self, context: RunContext[RestaurantSessionState]) -> str:
        """Return menu facts for a natural spoken response, never read the JSON aloud."""
        return json.dumps(await self.menu.list_menu())

    @function_tool
    async def add_item_to_cart(
        self,
        context: RunContext[RestaurantSessionState],
        variant_id: int,
        quantity: int = 1,
        modifier_names: list[str] | None = None,
    ) -> str:
        """Add a menu item with optional modifier names to the in-memory cart."""
        try:
            item = await self.menu.add_to_cart(
                variant_id, quantity, modifier_names or []
            )
        except ValueError as error:
            return json.dumps({"ok": False, "error": str(error)})
        context.userdata.cart.append(CartItem.model_validate(item))
        return json.dumps({"ok": True, "cart_item": item})

    @function_tool
    async def view_cart(self, context: RunContext[RestaurantSessionState]) -> str:
        """Return cart facts for a natural spoken summary; it is not an order receipt."""
        return json.dumps(
            {
                "items": [item.model_dump() for item in context.userdata.cart],
                "total_rupees": sum(
                    (
                        item.unit_price_rupees
                        + sum(
                            modifier["price_delta_rupees"]
                            for modifier in item.modifiers
                        )
                    )
                    * item.quantity
                    for item in context.userdata.cart
                ),
            }
        )

    @function_tool
    async def identify_customer(
        self,
        context: RunContext[RestaurantSessionState],
        phone: str,
        name: str | None = None,
    ) -> str:
        """Find or create the caller using a Pakistani phone number."""
        try:
            customer = await self.customers.get_or_create(phone, name)
        except ValueError as error:
            return json.dumps({"ok": False, "error": str(error)})
        context.userdata.customer_id = customer["id"]
        context.userdata.customer_phone = customer["phone"]
        context.userdata.customer_name = customer["name"]
        return json.dumps({"ok": True, "customer": customer})

    @function_tool
    async def save_customer_address(
        self,
        context: RunContext[RestaurantSessionState],
        label: str,
        address: str,
        is_default: bool = False,
    ) -> str:
        """Save an address for the identified caller."""
        if context.userdata.customer_id is None:
            return json.dumps({"ok": False, "error": "identify the customer first"})
        try:
            saved = await self.customers.add_address(
                context.userdata.customer_id,
                label,
                address,
                is_default,
            )
        except ValueError as error:
            return json.dumps({"ok": False, "error": str(error)})
        context.userdata.customer_address_id = saved["id"]
        return json.dumps({"ok": True, "address": saved})

    @function_tool
    async def place_order(
        self,
        context: RunContext[RestaurantSessionState],
        fulfillment_type: str,
        address_id: int | None = None,
    ) -> str:
        """Commit the validated cart after customer and branch checks succeed."""
        state = context.userdata
        if state.customer_id is None:
            return json.dumps({"ok": False, "error": "identify the customer first"})
        try:
            order = await self.orders.place_order(
                state.customer_id,
                address_id or state.customer_address_id,
                fulfillment_type.casefold(),
                [item.model_dump() for item in state.cart],
            )
        except ValueError as error:
            return json.dumps({"ok": False, "error": str(error)})
        state.fulfillment_type = order["fulfillment_type"]
        state.order_id = order["order_id"]
        state.order_completed = True
        state.cart.clear()
        return json.dumps({"ok": True, "order": order})

    @function_tool
    async def transfer_to_status(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Transfer when the caller asks about an existing order's status."""
        from .order_status import OrderStatusAgent

        return transfer(
            context,
            OrderStatusAgent(),
            "order_status",
            "caller changed intent to existing order status",
        )

    @function_tool
    async def transfer_to_complaint(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Transfer when the caller reports a problem or wants to complain."""
        from .complaint import ComplaintAgent

        return transfer(
            context,
            ComplaintAgent(),
            "complaint",
            "caller changed intent to complaint",
        )

    @function_tool
    async def return_to_receptionist(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Return after the caller is done ordering."""
        from .receptionist import ReceptionistAgent

        context.userdata.order_completed = True
        return transfer(
            context,
            ReceptionistAgent(),
            "receptionist",
            "order workflow completed; caller can choose main menu or end call",
        )

    @function_tool
    async def end_call(self, context: RunContext[RestaurantSessionState]) -> str:
        """Gracefully disconnect when the caller says goodbye."""
        context.session.shutdown(drain=True)
        return "Goodbye. Thank you for calling Crust & Co."
