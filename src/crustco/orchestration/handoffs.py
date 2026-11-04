from __future__ import annotations

import logging

from livekit.agents import Agent, RunContext

from .state import RestaurantSessionState

logger = logging.getLogger("crustco.handoffs")
MAX_HANDOFFS = 8


def transfer(
    context: RunContext[RestaurantSessionState],
    target: Agent,
    target_name: str,
    reason: str,
) -> str:
    state = context.userdata
    if state.handoff_count >= MAX_HANDOFFS:
        # Stop accidental transfer loops from keeping the conversation alive forever.
        return "handoff_rejected: maximum handoff count reached"

    state.handoff_count += 1
    state.active_agent = target_name
    state.last_handoff_reason = reason
    logger.info(
        "agent_handoff target=%s reason=%s count=%d",
        target_name,
        reason,
        state.handoff_count,
    )
    # AgentSession retains the same userdata and conversation context across handoffs.
    context.session.update_agent(target)
    return f"handoff_started: target={target_name}"
