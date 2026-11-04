from enum import StrEnum


class Model(StrEnum):
    STT = "assemblyai/universal-3-6-pro"
    LLM = "google/gemma-4-31b-it"
    TTS = "fishaudio/s2.1-pro"


class Voice(StrEnum):
    DEFAULT = "fa4c9eb3dccc4806b382b40d61c6b10a"
