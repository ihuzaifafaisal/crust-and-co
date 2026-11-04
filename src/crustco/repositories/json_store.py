from __future__ import annotations

import json
from pathlib import Path
from typing import Any

DATA_PATH = Path(__file__).resolve().parents[3] / "data" / "seed" / "mock_data.json"


def normalize_phone(phone: str) -> str:
    # Store Pakistani numbers in one canonical form for reliable lookups.
    normalized = "".join(character for character in phone if character.isdigit())
    normalized = normalized.removeprefix("00")
    if normalized.startswith("92"):
        return "+" + normalized
    normalized = normalized.removeprefix("0")
    if len(normalized) < 10:
        raise ValueError("enter a valid phone number")
    return "+92" + normalized


class JsonDataStore:
    def __init__(self, path: str | Path = DATA_PATH) -> None:
        self.path = Path(path)

    def read(self) -> dict[str, list[dict[str, Any]]]:
        try:
            with self.path.open(encoding="utf-8") as file:
                data = json.load(file)
        except (OSError, json.JSONDecodeError) as error:
            raise RuntimeError(f"unable to read mock data from {self.path}") from error
        if not isinstance(data, dict):
            raise TypeError("mock data must contain a JSON object")
        return data

    def write(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(".tmp")
        try:
            # Replace the seed atomically so an interrupted write cannot corrupt it.
            with temporary_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, indent=2)
                file.write("\n")
            temporary_path.replace(self.path)
        except OSError as error:
            raise RuntimeError(f"unable to write mock data to {self.path}") from error
