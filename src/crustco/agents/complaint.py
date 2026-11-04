from __future__ import annotations

import json

from livekit.agents import Agent, RunContext, function_tool

from ..orchestration.conversation import VOICE_OUTPUT_RULES
from ..orchestration.handoffs import transfer
from ..orchestration.state import RestaurantSessionState
from ..repositories import ComplaintRepository, CustomerRepository


class ComplaintAgent(Agent):
    def __init__(
        self,
        customers: CustomerRepository | None = None,
        complaints: ComplaintRepository | None = None,
    ) -> None:
        self.customers = customers or CustomerRepository()
        self.complaints = complaints or ComplaintRepository()
        super().__init__(
            instructions=(
                "You are the Crust & Co. complaint specialist. Listen empathetically. "
                "Identify the caller by Pakistani phone number, ask for the existing "
                "order number if they have one, and capture the complaint details. "
                "Read back a short summary and ask for confirmation before calling "
                "register_complaint. Never promise a refund or a resolution. Keep the "
                "caller's selected language. If the caller says goodbye or wants to "
                "end the call, say goodbye and call end_call instead of returning to "
                "the receptionist. " + VOICE_OUTPUT_RULES
            )
        )

    async def on_enter(self) -> None:
        await self.session.generate_reply(
            instructions=(
                "Briefly acknowledge the handoff empathetically and ask for the "
                "caller's phone number so the complaint can be attached to their "
                "customer record."
            )
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
    async def register_complaint(
        self,
        context: RunContext[RestaurantSessionState],
        message: str,
        order_reference: int | None = None,
    ) -> str:
        """Save a confirmed complaint for the identified caller."""
        if context.userdata.customer_id is None:
            return json.dumps({"ok": False, "error": "identify the customer first"})
        # The confirmation is handled by the model before this mutating tool runs.
        try:
            complaint = await self.complaints.create(
                context.userdata.customer_id,
                message,
                order_reference,
            )
        except ValueError as error:
            return json.dumps({"ok": False, "error": str(error)})
        context.userdata.order_id = order_reference
        return json.dumps({"ok": True, "complaint": complaint})

    @function_tool
    async def return_to_receptionist(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Return after registering the complaint or finishing complaint support."""
        from .receptionist import ReceptionistAgent

        return transfer(
            context,
            ReceptionistAgent(),
            "receptionist",
            "complaint workflow completed",
        )

    @function_tool
    async def end_call(self, context: RunContext[RestaurantSessionState]) -> str:
        """Gracefully disconnect when the caller says goodbye."""
        # Specialists hang up directly instead of routing a goodbye through reception.
        context.session.shutdown(drain=True)
        return "Goodbye. Thank you for calling Crust & Co."
