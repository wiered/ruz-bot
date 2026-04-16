from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def _ensure_module(name: str) -> ModuleType:
    module = sys.modules.get(name)
    if module is None:
        module = ModuleType(name)
        sys.modules[name] = module
    return module


telebot = _ensure_module("telebot")
telebot_types = _ensure_module("telebot.types")
telebot_util = _ensure_module("telebot.util")


class _DummyMarkup:
    def __init__(self, *args, **kwargs) -> None:
        self.keyboard = []

    def row(self, *buttons) -> None:
        self.keyboard.append(list(buttons))


class _DummyButton:
    def __init__(self, *args, **kwargs) -> None:
        self.text = kwargs.get("text", args[0] if args else "")
        self.callback_data = kwargs.get("callback_data")
        self.url = kwargs.get("url")


telebot_types.InlineKeyboardMarkup = _DummyMarkup
telebot_types.InlineKeyboardButton = _DummyButton
telebot.types = telebot_types
telebot_util.quick_markup = lambda *args, **kwargs: {}
telebot.util = telebot_util

dotenv = _ensure_module("dotenv")
dotenv.load_dotenv = lambda *args, **kwargs: None

redis_pkg = _ensure_module("redis")
redis_pkg.__path__ = []
redis_asyncio = _ensure_module("redis.asyncio")
redis_asyncio.from_url = lambda *args, **kwargs: None
redis_pkg.asyncio = redis_asyncio

ruzbot_bot = _ensure_module("ruzbot.bot")
ruzbot_bot.__version__ = "test"

ruzbot_utils = _ensure_module("ruzbot.utils")


class _DummyAsyncContextManager:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False


def _dummy_ruz_client():
    return _DummyAsyncContextManager()


ruzbot_utils.ruz_client = _dummy_ruz_client
ruzbot_utils.remove_position = lambda value: value

ruzclient = _ensure_module("ruzclient")
ruzclient.UNSET = object()


class _Payload:
    def __init__(self, **kwargs) -> None:
        self.__dict__.update(kwargs)


ruzclient.UserCreate = _Payload
ruzclient.UserScheduleLesson = dict
ruzclient.UserUpdate = _Payload
ruzclient_errors = _ensure_module("ruzclient.errors")


class RuzHttpError(Exception):
    def __init__(self, status_code: int = 0) -> None:
        super().__init__(status_code)
        self.status_code = status_code


ruzclient_errors.RuzHttpError = RuzHttpError
ruzclient.errors = ruzclient_errors


from ruzbot import cache, commands  # noqa: E402


def _redis_prefix() -> str:
    return (cache.settings.redis_key_prefix or "ruzbot").strip(":")


class FakeRedisClient:
    def __init__(self, keys: list[str]) -> None:
        self._keys = keys
        self.deleted: list[str] = []

    async def delete(self, *keys: str) -> None:
        self.deleted.extend(keys)

    async def scan_iter(self, match: str):
        prefix = match[:-1] if match.endswith("*") else match
        for key in self._keys:
            if key.startswith(prefix):
                yield key


class FakeScheduleClient:
    def __init__(self, lessons) -> None:
        self.get_group_week = AsyncMock(return_value=lessons)


class FakeClient:
    def __init__(self, lessons) -> None:
        self.schedule = FakeScheduleClient(lessons)


class FakeGroupClient:
    def __init__(self, side_effect) -> None:
        self.groups = type(
            "Groups",
            (),
            {"get_group": AsyncMock(side_effect=side_effect)},
        )()


class GroupScheduleCacheTests(IsolatedAsyncioTestCase):
    def test_group_week_key_uses_group_prefix(self) -> None:
        key = cache.group_week_key(17, date(2026, 3, 26))
        self.assertEqual(
            key,
            f"{_redis_prefix()}:group:17:schedule:week:2026-03-23",
        )

    async def test_invalidate_user_keeps_group_schedule(self) -> None:
        prefix = _redis_prefix()
        profile_key = f"{prefix}:user:42:profile"
        screen_key = f"{prefix}:user:42:screen:start"
        old_user_week_key = f"{prefix}:user:42:schedule:week:2026-03-23"
        old_user_day_key = f"{prefix}:user:42:schedule:day:2026-03-26"
        group_week_key = f"{prefix}:group:55:schedule:week:2026-03-23"
        fake = FakeRedisClient(
            [
                profile_key,
                screen_key,
                old_user_week_key,
                old_user_day_key,
                group_week_key,
            ]
        )

        with patch.object(cache, "get_redis_client", AsyncMock(return_value=fake)):
            await cache.invalidate_user(42)

        self.assertIn(profile_key, fake.deleted)
        self.assertIn(screen_key, fake.deleted)
        self.assertIn(old_user_week_key, fake.deleted)
        self.assertIn(old_user_day_key, fake.deleted)
        self.assertNotIn(group_week_key, fake.deleted)

    async def test_get_user_week_lessons_filters_by_subgroup(self) -> None:
        cases = [
            (
                0,
                [
                    {"sub_group": 0, "lesson_id": 1},
                    {"sub_group": 1, "lesson_id": 2},
                ],
                [1, 2],
            ),
            (
                1,
                [
                    {"sub_group": 0, "lesson_id": 3},
                    {"sub_group": 1, "lesson_id": 4},
                ],
                [3, 4],
            ),
            (
                "2",
                [
                    {"sub_group": 0, "lesson_id": 5},
                    {"sub_group": "2", "lesson_id": 6},
                    {"sub_group": 1, "lesson_id": 7},
                ],
                [5, 6],
            ),
        ]

        for subgroup, lessons, expected_ids in cases:
            fake_client = FakeClient(lessons)

            async def fake_fetch_user(client, user_id):
                return {"group_oid": 55, "subgroup": subgroup}

            async def fake_get_or_load_group_week_lessons(
                group_id, anchor_date, loader
            ):
                self.assertEqual(group_id, 55)
                return await loader(cache.week_anchor_date(anchor_date))

            async def fake_get_or_load_user_week_lessons(user_id, anchor_date, loader):
                self.assertEqual(user_id, 100)
                return await loader(cache.week_anchor_date(anchor_date))

            with (
                patch.object(commands, "_fetch_user", side_effect=fake_fetch_user),
                patch.object(
                    commands.cache,
                    "get_or_load_group_week_lessons",
                    side_effect=fake_get_or_load_group_week_lessons,
                ),
                patch.object(
                    commands.cache,
                    "get_or_load_week_lessons",
                    side_effect=fake_get_or_load_user_week_lessons,
                ),
            ):
                _, filtered = await commands.get_user_week_lessons(
                    fake_client, 100, date(2026, 3, 26)
                )

            self.assertEqual([lesson["lesson_id"] for lesson in filtered], expected_ids)
            fake_client.schedule.get_group_week.assert_awaited_once_with(
                55, date(2026, 3, 23)
            )

    async def test_fetch_group_returns_none_for_404(self) -> None:
        fake_client = FakeGroupClient(RuzHttpError(404))

        result = await commands._fetch_group(fake_client, 55)

        self.assertIsNone(result)

    async def test_fetch_group_reraises_non_404(self) -> None:
        fake_client = FakeGroupClient(RuzHttpError(500))

        with self.assertRaises(RuzHttpError):
            await commands._fetch_group(fake_client, 55)

    async def test_set_group_uses_server_metadata_for_existing_user(self) -> None:
        fake_client = SimpleNamespace(
            users=SimpleNamespace(
                update_user=AsyncMock(),
                create_user=AsyncMock(),
            )
        )
        fake_bot = SimpleNamespace(reply_to=AsyncMock())
        fake_callback = SimpleNamespace(
            from_user=SimpleNamespace(id=42, username="alice"),
            message=SimpleNamespace(),
        )

        with (
            patch.object(
                commands,
                "_fetch_group",
                AsyncMock(return_value={"guid": "guid-55", "name": "Group 55"}),
            ),
            patch.object(commands, "_fetch_user", AsyncMock(return_value={"id": 42})),
            patch.object(
                commands, "ruz_client", return_value=_DummyAsyncContextManager()
            ),
            patch.object(
                _DummyAsyncContextManager,
                "__aenter__",
                AsyncMock(return_value=fake_client),
            ),
            patch.object(commands.cache, "invalidate_user", AsyncMock()),
        ):
            saved = await commands.setGroup(fake_bot, fake_callback, 55, "Group 55")

        self.assertTrue(saved)
        fake_client.users.create_user.assert_not_awaited()
        fake_client.users.update_user.assert_awaited_once()
        _, update_payload = fake_client.users.update_user.await_args.args
        self.assertEqual(update_payload.group_oid, 55)
        self.assertEqual(update_payload.group_guid, "guid-55")
        self.assertEqual(update_payload.group_name, "Group 55")
