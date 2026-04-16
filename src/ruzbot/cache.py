from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any, Awaitable, Callable, Optional

from telebot import types

from ruzbot.settings import settings

try:
    import redis.asyncio as redis
except ImportError:  # pragma: no cover - dependency is optional during bootstrap
    redis = None

logger = logging.getLogger(__name__)

_redis_client = None
_redis_lock = asyncio.Lock()


@dataclass(slots=True)
class ScreenSnapshot:
    text: str
    parse_mode: Optional[str]
    reply_markup: Optional[list[list[dict[str, Any]]]]
    source: Optional[str] = None
    created_at: str = ""


def _key_prefix() -> str:
    return (settings.redis_key_prefix or "ruzbot").strip(":")


def user_prefix(user_id: int) -> str:
    return f"{_key_prefix()}:user:{user_id}"


def profile_key(user_id: int) -> str:
    return f"{user_prefix(user_id)}:profile"


def week_key(user_id: int, week_date: date | datetime) -> str:
    anchor = week_anchor_date(week_date)
    return f"{user_prefix(user_id)}:schedule:week:{anchor.isoformat()}"


def day_key(user_id: int, day_date: date | datetime) -> str:
    if isinstance(day_date, datetime):
        day_date = day_date.date()
    return f"{user_prefix(user_id)}:schedule:day:{day_date.isoformat()}"


def group_prefix(group_id: int) -> str:
    return f"{_key_prefix()}:group:{group_id}"


def group_week_key(group_id: int, week_date: date | datetime) -> str:
    anchor = week_anchor_date(week_date)
    return f"{group_prefix(group_id)}:schedule:week:{anchor.isoformat()}"


def screen_key(user_id: int, screen_name: str) -> str:
    return f"{user_prefix(user_id)}:screen:{normalize_screen_key(screen_name)}"


def normalize_screen_key(screen_name: str | None) -> str:
    if not screen_name:
        return ""
    return str(screen_name).strip().replace(" ", ":")


def week_anchor_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        value = value.date()
    return value - timedelta(days=value.weekday())


def _json_loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        logger.warning("Failed to decode Redis JSON payload")
        return None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _serialize_markup(markup: Any) -> Optional[list[list[dict[str, Any]]]]:
    if markup is None:
        return None

    keyboard = getattr(markup, "keyboard", None)
    if keyboard is None:
        keyboard = getattr(markup, "inline_keyboard", None)
    if keyboard is None:
        return None

    rows: list[list[dict[str, Any]]] = []
    for row in keyboard:
        serialized_row: list[dict[str, Any]] = []
        for button in row:
            item: dict[str, Any] = {"text": getattr(button, "text", "")}
            callback_data = getattr(button, "callback_data", None)
            url = getattr(button, "url", None)
            if callback_data is not None:
                item["callback_data"] = callback_data
            if url is not None:
                item["url"] = url
            serialized_row.append(item)
        rows.append(serialized_row)
    return rows


def _deserialize_markup(
    payload: Optional[list[list[dict[str, Any]]]],
) -> Optional[types.InlineKeyboardMarkup]:
    if not payload:
        return None

    markup = types.InlineKeyboardMarkup()
    for row in payload:
        buttons: list[types.InlineKeyboardButton] = []
        for item in row:
            text = item.get("text", "")
            callback_data = item.get("callback_data")
            url = item.get("url")
            buttons.append(
                types.InlineKeyboardButton(
                    text=text, callback_data=callback_data, url=url
                )
            )
        if buttons:
            markup.row(*buttons)
    return markup


async def get_redis_client():
    if redis is None or not settings.redis_url:
        return None

    global _redis_client
    if _redis_client is not None:
        return _redis_client

    async with _redis_lock:
        if _redis_client is None:
            _redis_client = redis.from_url(
                settings.redis_url,
                decode_responses=True,
                health_check_interval=30,
            )
    return _redis_client


async def _read_json_key(key: str) -> Any:
    client = await get_redis_client()
    if client is None:
        return None

    try:
        raw = await client.get(key)
    except Exception:
        logger.exception("Failed to read Redis key %s", key)
        return None
    return _json_loads(raw)


async def _store_json_key(key: str, value: Any, ttl_s: int) -> None:
    client = await get_redis_client()
    if client is None:
        return

    try:
        await client.set(key, _json_dumps(value), ex=ttl_s)
    except Exception:
        logger.exception("Failed to store Redis key %s", key)


async def get_or_load_profile(
    user_id: int, loader: Callable[[], Awaitable[Any]]
) -> Any:
    key = profile_key(user_id)
    cached = await _read_json_key(key)
    if cached is not None:
        return cached

    profile = await loader()
    if profile is None:
        return None

    await _store_json_key(key, profile, settings.redis_ttl_profile_s)
    return profile


async def get_or_load_week_lessons(
    user_id: int,
    anchor_date: date | datetime,
    loader: Callable[[date], Awaitable[Any]],
) -> Any:
    key = week_key(user_id, anchor_date)
    cached = await _read_json_key(key)
    if cached is not None:
        return cached

    anchor = week_anchor_date(anchor_date)
    lessons = await loader(anchor)
    if lessons is None:
        return None

    await _store_json_key(key, lessons, settings.redis_ttl_schedule_s)
    return lessons


async def get_or_load_day_lessons(
    user_id: int,
    day_date: date | datetime,
    loader: Callable[[date], Awaitable[Any]],
) -> Any:
    key = day_key(user_id, day_date)
    cached = await _read_json_key(key)
    if cached is not None:
        return cached

    if isinstance(day_date, datetime):
        day_date = day_date.date()

    lessons = await loader(day_date)
    if lessons is None:
        return None

    await _store_json_key(key, lessons, settings.redis_ttl_schedule_s)
    return lessons


async def get_or_load_group_week_lessons(
    group_id: int,
    anchor_date: date | datetime,
    loader: Callable[[date], Awaitable[Any]],
) -> Any:
    key = group_week_key(group_id, anchor_date)
    cached = await _read_json_key(key)
    if cached is not None:
        return cached

    anchor = week_anchor_date(anchor_date)
    lessons = await loader(anchor)
    if lessons is None:
        return None

    await _store_json_key(key, lessons, settings.redis_ttl_schedule_s)
    return lessons


async def store_screen_snapshot(
    user_id: int,
    screen_name: str,
    *,
    text: str,
    reply_markup: Any = None,
    parse_mode: Optional[str] = None,
    source: Optional[str] = None,
) -> None:
    payload = ScreenSnapshot(
        text=text,
        parse_mode=parse_mode,
        reply_markup=_serialize_markup(reply_markup),
        source=source,
        created_at=datetime.utcnow().isoformat(timespec="seconds"),
    )
    await _store_json_key(
        screen_key(user_id, screen_name), asdict(payload), settings.redis_ttl_message_s
    )


async def get_screen_snapshot(
    user_id: int, screen_name: str
) -> Optional[ScreenSnapshot]:
    payload = await _read_json_key(screen_key(user_id, screen_name))
    if payload is None:
        return None
    try:
        return ScreenSnapshot(**payload)
    except TypeError:
        logger.warning("Invalid screen snapshot payload for %s", screen_name)
        return None


async def replay_screen_snapshot(bot, message, user_id: int, screen_name: str) -> bool:
    snapshot = await get_screen_snapshot(user_id, screen_name)
    if snapshot is None:
        return False

    kwargs: dict[str, Any] = {}
    markup = _deserialize_markup(snapshot.reply_markup)
    if markup is not None:
        kwargs["reply_markup"] = markup
    if snapshot.parse_mode is not None:
        kwargs["parse_mode"] = snapshot.parse_mode

    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=message.message_id,
            text=snapshot.text,
            **kwargs,
        )
    except Exception:
        logger.exception("Failed to replay screen snapshot %s", screen_name)
        return False
    return True


async def invalidate_user(user_id: int) -> None:
    client = await get_redis_client()
    if client is None:
        return

    try:
        pattern = f"{user_prefix(user_id)}:*"
        keys = [key async for key in client.scan_iter(match=pattern)]
        if keys:
            await client.delete(*keys)
    except Exception:
        logger.exception("Failed to invalidate Redis keys for user %s", user_id)
