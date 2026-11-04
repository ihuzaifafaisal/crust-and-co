from __future__ import annotations

import logging
from time import perf_counter

from dotenv import load_dotenv
from livekit import agents
from livekit.agents import AgentServer

load_dotenv()

# Keep the server entrypoint thin; session construction lives in orchestration.
from .agents.receptionist import ReceptionistAgent
from .orchestration.session import build_session
from .orchestration.state import RestaurantSessionState

logger = logging.getLogger("crustco.main")
server = AgentServer()


@server.rtc_session(agent_name="crust-and-co")
async def entrypoint(ctx: agents.JobContext) -> None:
    state = RestaurantSessionState()
    session = build_session(state)
    started_at = perf_counter()
    await session.start(
        agent=ReceptionistAgent(),
        room=ctx.room,
    )
    logger.info(
        "latency event=session_started elapsed_ms=%.2f",
        (perf_counter() - started_at) * 1000,
    )


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    agents.cli.run_app(server)


if __name__ == "__main__":
    main()
