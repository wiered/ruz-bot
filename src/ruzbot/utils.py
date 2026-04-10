from __future__ import annotations

import random
from contextlib import asynccontextmanager

from ruzclient.client import ClientConfig, RuzClient
from ruzbot.settings import settings

RANDOM_GROUP_NAMES = [
    'ИС222',
    'ИС221',
    'МС221',
    'МС222',
    'МС223',
    'МС231',
    'МС232',
    'МС233',
    'МС241',
    'МС242',
    'МС243',
    'БИС221',
    'БИС222',
    'БИС231',
    'БИС231',
    'БАС221',
    'БАС231',
    'БАС232',
    'БАС241',
    'БАС242',
    'ЭВМ221',
    'ЭВМб211',
    'ЭВМб212',
    'УВД221',
    'УВД222',
    'УВД231',
    'УВД241',
    ]

def getRandomGroup() -> str:
    """
    Returns a random group name from the RANDOM_GROUP_NAMES list.

    Returns:
        str: A random group name.
    """
    return random.choice(RANDOM_GROUP_NAMES)


def remove_position(lecturer_short_name: str) -> str:
    parts = lecturer_short_name.split()
    return " ".join(parts[-2:]) if len(parts) >= 2 else lecturer_short_name

@asynccontextmanager
async def ruz_client():
    """Контекст с настроенным ``RuzClient`` (aiohttp)."""
    cfg = ClientConfig(
        base_url=settings.base_url,
        timeout_s=settings.timeout_s,
        api_key=settings.token,
        default_headers=settings.default_headers,
    )
    async with RuzClient(cfg) as client:
        yield client