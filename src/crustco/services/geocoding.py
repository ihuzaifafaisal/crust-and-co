from __future__ import annotations

import asyncio
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from pydantic import BaseModel


class Coordinates(BaseModel):
    latitude: float
    longitude: float


def _lookup(address: str) -> Coordinates:
    if not address.strip():
        raise ValueError("please provide a Lahore delivery address")
    query = urlencode(
        {
            "q": f"{address.strip()}, Lahore, Pakistan",
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "pk",
        }
    )
    request = Request(
        f"{os.getenv('CRUSTCO_GEOCODER_URL', 'https://nominatim.openstreetmap.org/search')}?{query}",
        headers={
            "User-Agent": os.getenv(
                "CRUSTCO_GEOCODER_USER_AGENT", "crust-and-co-demo/1.0"
            )
        },
    )
    try:
        with urlopen(request, timeout=8) as response:
            results = json.load(response)
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("address lookup is temporarily unavailable") from error
    if not isinstance(results, list) or not results:
        raise ValueError("please provide a valid Lahore delivery address")
    try:
        return Coordinates(
            latitude=float(results[0]["lat"]), longitude=float(results[0]["lon"])
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("the address lookup returned an invalid response") from error


async def geocode(address: str) -> Coordinates:
    return await asyncio.to_thread(_lookup, address)
