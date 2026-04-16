"""Точка входа: long polling для AsyncTeleBot."""

from __future__ import annotations

import asyncio
import logging
import sys

from ruzbot.settings import settings


def main() -> None:
    # import urllib.request
    # import json

    # Check Telegram API availability using getMe before proceeding
    # try:
    #     url = f"https://api.telegram.org/bot{settings.bot_token}/getMe"
    #     with urllib.request.urlopen(url, timeout=5) as response:
    #         resp_body = response.read().decode()
    #         if response.status == 200:
    #             data = json.loads(resp_body)
    #             if data.get("ok"):
    #                 print("getMe успешен, api.telegram.org доступен")
    #             else:
    #                 print("api.telegram.org ответил ошибкой: %r" % data, file=sys.stderr)
    #                 sys.exit(2)
    #         else:
    #             print("api.telegram.org недоступен (status=%s)" % response.status, file=sys.stderr)
    #             sys.exit(2)
    # except Exception as ex:
    #     print("Ошибка доступа к api.telegram.org (getMe): %s" % ex, file=sys.stderr)
    #     sys.exit(2)

    if not settings.bot_token:
        print("Задайте BOT_TOKEN в окружении или в .env.", file=sys.stderr)
        sys.exit(1)

    # Импорт после проверки токена: иначе AsyncTeleBot падает на пустом токене.
    from ruzbot.bot import bot
    from ruzbot.callbacks import register_handlers

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    async def _run() -> None:
        register_handlers(bot)
        await bot.infinity_polling()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
