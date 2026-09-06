from __future__ import annotations

import asyncio
import logging
import weakref
from datetime import datetime, timedelta, timezone
from typing import Any

from ruzclient.errors import RuzHttpError

from ruzbot import cache
from ruzbot.utils import ruz_client

logger = logging.getLogger(__name__)

TOUCH_INTERVAL = timedelta(minutes=5)

_user_locks: weakref.WeakValueDictionary[int, asyncio.Lock] = (
    weakref.WeakValueDictionary()
)


def _parse_last_used_at(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
    else:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


async def touch_user_activity(user_id: int) -> bool:
    """Обновляет last_used_at не чаще одного раза в пять минут.

    Возвращает True, только если серверное поле действительно обновлено.
    Отсутствующий пользователь и ошибки API не прерывают основное действие бота.
    """
    lock = _user_locks.setdefault(user_id, asyncio.Lock())
    async with lock:
        try:
            async with ruz_client() as client:
                user = await client.users.get_by_id(user_id)
                last_used_at = _parse_last_used_at(user.get("last_used_at"))
                now = datetime.now(timezone.utc)
                if last_used_at is not None and now - last_used_at < TOUCH_INTERVAL:
                    return False

                updated = await client.users.touch(user_id=user_id)  # type: ignore[attr-defined]
        except RuzHttpError as error:
            if error.status_code == 404:
                logger.debug("Activity touch skipped for unknown user %s", user_id)
            else:
                logger.exception("Failed to touch activity for user %s", user_id)
            return False
        except Exception:
            logger.exception("Failed to touch activity for user %s", user_id)
            return False

        if updated:
            await cache.invalidate_profile(user_id)
            return True
        return False
