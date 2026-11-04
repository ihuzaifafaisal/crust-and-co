from __future__ import annotations

import os

from livekit.agents import AgentSession, TurnHandlingOptions, inference, room_io
from livekit.plugins import noise_cancellation

from ..config import Model, Voice
from .state import RestaurantSessionState


def build_session(state: RestaurantSessionState) -> AgentSession:
    return AgentSession(
        stt=inference.STT(model=os.getenv("CRUSTCO_STT_MODEL", Model.STT)),
        llm=inference.LLM(model=os.getenv("CRUSTCO_LLM_MODEL", Model.LLM)),
        tts=inference.TTS(
            model=os.getenv("CRUSTCO_TTS_MODEL", Model.TTS),
            voice=os.getenv("CRUSTCO_TTS_VOICE", Voice.DEFAULT),
        ),
        turn_handling=TurnHandlingOptions(
            turn_detection=inference.TurnDetector(),
        ),
        userdata=state,
    )


def build_room_options() -> room_io.RoomOptions:
    """Configure enhanced cancellation for the caller's incoming audio."""
    return room_io.RoomOptions(
        audio_input=room_io.AudioInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )
