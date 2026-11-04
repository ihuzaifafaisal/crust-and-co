from __future__ import annotations

from livekit.agents import Agent, RunContext, function_tool

from ..orchestration.conversation import (
    VOICE_OUTPUT_RULES,
    select_language,
    update_language,
)
from ..orchestration.handoffs import transfer
from ..orchestration.state import RestaurantSessionState
from .complaint import ComplaintAgent
from .order import OrderAgent
from .order_status import OrderStatusAgent

INITIAL_GREETING = (
    "Assalam-o-alaikum! Thank you for calling Crust & Co. Welcome! "
    "I can assist you in English or Urdu. Which language would you prefer?"
)


class ReceptionistAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions=(
                "You are the receptionist for Crust & Co., a fictional pizza "
                "restaurant in Lahore, Pakistan. Be warm, concise, professional, "
                "and ask one question at a time. Speak only English or Urdu. The "
                "first turn must ask the caller to choose English or Urdu. Preserve "
                "the selected language through every handoff. Identify whether the "
                "caller wants a new order, existing-order status, or complaint. "
                "Use the matching transfer tool when intent is clear. Ask for "
                "clarification when it is unclear. When the caller says goodbye "
                "or clearly wants to end the call, say a brief goodbye and call "
                "end_call. Never perform specialist work. " + VOICE_OUTPUT_RULES
            )
        )

    async def on_enter(self) -> None:
        state = self.session.userdata
        if state.language is None:
            await self.session.generate_reply(instructions=INITIAL_GREETING)
        else:
            await self.session.generate_reply(
                instructions=(
                    f"The caller already selected {state.language}. "
                    "Do not repeat the greeting or ask for language selection. "
                    "Ask whether there is anything else you can help with, or whether "
                    "they would like to end the call. If they want more help, continue "
                    "with the main service menu. If they want to leave, say goodbye."
                )
            )

    async def on_user_turn_completed(self, chat_ctx, new_message) -> None:
        transcript = new_message.text_content or ""
        if (
            select_language(transcript) is not None
            or self.session.userdata.language is None
        ):
            update_language(self.session.userdata, transcript)

    @function_tool
    async def transfer_to_order(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Transfer a caller with a clear request to place a new order."""
        return transfer(context, OrderAgent(), "order", "caller requested a new order")

    @function_tool
    async def transfer_to_status(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Transfer a caller asking about an existing order's status."""
        return transfer(
            context,
            OrderStatusAgent(),
            "order_status",
            "caller requested existing order status",
        )

    @function_tool
    async def transfer_to_complaint(
        self, context: RunContext[RestaurantSessionState]
    ) -> str:
        """Transfer a caller reporting a problem or registering a complaint."""
        return transfer(
            context,
            ComplaintAgent(),
            "complaint",
            "caller requested complaint handling",
        )

    @function_tool
    async def end_call(self, context: RunContext[RestaurantSessionState]) -> str:
        """Gracefully disconnect after the goodbye response has been spoken."""
        context.session.shutdown(drain=True)
        return "Goodbye. Thank you for calling Crust & Co."
