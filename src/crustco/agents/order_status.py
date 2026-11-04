from __future__ import annotations

import json

from livekit.agents import Agent, RunContext, function_tool

from ..orchestration.conversation import VOICE_OUTPUT_RULES
from ..orchestration.handoffs import transfer
from ..orchestration.state import RestaurantSessionState
from ..repositories import CustomerRepository, OrderRepository


class OrderStatusAgent(Agent):
    def __init__(
        self,
        customers: CustomerRepository | None = None,
        orders: OrderRepository | None = None,
    ) -> None:
        self.customers = customers or CustomerRepository()
        self.orders = orders or OrderRepository()
        super().__init__(
            instructions=(
                "You are the Crust & Co. order-status specialist. Identify the caller "
                "by Pakistani phone number before looking up an order. Ask for the "
                "order reference if the caller has one. Do not ask for a country "
                "code. Do not invent an order, status, delivery time, or customer "
                "data. Keep the caller's selected language. If the caller says "
                "goodbye or wants to end the call, say goodbye and call end_call "
                "instead of returning to the receptionist. " + VOICE_OUTPUT_RULES
            )
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Briefly acknowledge the handoff and ask for the caller's phone "
                "number so you can check their saved order history."
            )
        )

    @function_tool
    async def identify_customer(
        self,
        context: RunContext[RestaurantSessionState],
        phone: str,
        name: str | None = None,
    ) -> str:
        """Find the caller using a Pakistani phone number."""
        try:
            customer = await self.customers.find(phone)
        except ValueError as error:
            return json.dumps({"ok": False, "error": str(error)})
        if customer is None:
            return json.dumps(
                {"ok": False, "error": "no customer was found for that phone number"}
            )
        context.userdata.customer_id = customer["id"]
        context.userdata.customer_phone = customer["phone"]
        context.userdata.customer_name = customer["name"]
        return json.dumps({"ok": True, "customer": customer})

    @function_tool
    async def get_order_status(
        self,
        context: RunContext[RestaurantSessionState],
        order_reference: int | None = None,
    ) -> str:
        """Look up the caller's latest order or a supplied order reference."""
        if context.userdata.customer_id is None:
            return json.dumps({"ok": False, "error": "identify the customer first"})
        order = await self.orders.get_status(
            context.userdata.customer_id, order_reference
        )
        if order is None:
            return json.dumps({"ok": False, "error": "no matching order was found"})
        # Keep the selected order available to the shared session for later handoffs.
        context.userdata.order_id = order["order_id"]
        return json.dumps({"ok": True, "order": order})

    @function_tool
    async def return_to_receptionist(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Return after completing an order-status lookup."""
        from .receptionist import ReceptionistAgent

        return transfer(
            context,
            ReceptionistAgent(),
            "receptionist",
            "order-status lookup completed",
        )

    @function_tool
    async def end_call(self, context: RunContext[RestaurantSessionState]) -> str:
        """Gracefully disconnect when the caller says goodbye."""
        # Specialists hang up directly instead of routing a goodbye through reception.
        context.session.shutdown(drain=True)
        return "Goodbye. Thank you for calling Crust & Co."
