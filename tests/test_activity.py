from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import AsyncMock, patch

from ruzclient.errors import RuzHttpError

from ruzbot import activity


class TestTouchUserActivity(IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        activity._user_locks.clear()

    @staticmethod
    def _client_context(client):
        @asynccontextmanager
        async def context():
            yield client

        return context

    async def test_skips_touch_when_less_than_five_minutes_passed(self) -> None:
        users = SimpleNamespace(
            get_by_id=AsyncMock(
                return_value={
                    "last_used_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=4)
                    ).isoformat()
                }
            ),
            touch=AsyncMock(),
        )
        client = SimpleNamespace(users=users)

        with (
            patch.object(activity, "ruz_client", self._client_context(client)),
            patch.object(
                activity.cache, "invalidate_profile", new_callable=AsyncMock
            ) as invalidate_profile,
        ):
            updated = await activity.touch_user_activity(123)

        self.assertFalse(updated)
        users.touch.assert_not_awaited()
        invalidate_profile.assert_not_awaited()

    async def test_touches_when_five_minutes_passed(self) -> None:
        users = SimpleNamespace(
            get_by_id=AsyncMock(
                return_value={
                    "last_used_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=5, seconds=1)
                    ).isoformat()
                }
            ),
            touch=AsyncMock(return_value=True),
        )
        client = SimpleNamespace(users=users)

        with (
            patch.object(activity, "ruz_client", self._client_context(client)),
            patch.object(
                activity.cache, "invalidate_profile", new_callable=AsyncMock
            ) as invalidate_profile,
        ):
            updated = await activity.touch_user_activity(123)

        self.assertTrue(updated)
        users.touch.assert_awaited_once_with(user_id=123)
        invalidate_profile.assert_awaited_once_with(123)

    async def test_missing_user_does_not_break_action(self) -> None:
        users = SimpleNamespace(
            get_by_id=AsyncMock(
                side_effect=RuzHttpError(status_code=404, message="not found")
            ),
            touch=AsyncMock(),
        )
        client = SimpleNamespace(users=users)

        with patch.object(activity, "ruz_client", self._client_context(client)):
            updated = await activity.touch_user_activity(123)

        self.assertFalse(updated)
        users.touch.assert_not_awaited()
