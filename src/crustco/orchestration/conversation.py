from __future__ import annotations

from .state import Language, RestaurantSessionState

LANGUAGE_CLARIFICATION = "Please choose English or Urdu."

VOICE_OUTPUT_RULES = (
    "This is a voice conversation. Speak naturally and never read or mention "
    "markdown or formatting symbols, including asterisks, hash signs, brackets, "
    "underscores, backticks, bullet markers, or JSON. Never read URLs, web "
    "addresses, email addresses, code, database fields, internal IDs, or tool "
    "output aloud. Convert prices into natural spoken rupees, and "
    "describe items in conversational language. Keep replies concise."
)


def select_language(text: str) -> Language | None:
    """Return a clear language choice without guessing from unrelated speech."""
    # Roman Urdu phrases are accepted without treating general Urdu speech as a choice.
    normalized = text.casefold()
    if (
        normalized in {"urdu", "urdu please"}
        or any(
            phrase in normalized
            for phrase in ("speak urdu", "in urdu", "switch to urdu", "urdu mein")
        )
        or "اردو" in text
    ):
        return Language.URDU
    if (
        normalized in {"english", "english please"}
        or any(
            phrase in normalized
            for phrase in ("speak english", "in english", "switch to english")
        )
        or "انگریزی" in text
    ):
        return Language.ENGLISH
    return None


def update_language(state: RestaurantSessionState, text: str) -> str:
    language = select_language(text)
    if language is None:
        return LANGUAGE_CLARIFICATION
    state.language = language
    return (
        "Theek hai, hum Urdu mein baat karte hain."
        if language is Language.URDU
        else "Great, we will continue in English."
    )
