from __future__ import annotations

from typing import Optional, Union

from telebot import types
from telebot.async_telebot import AsyncTeleBot
from telebot.asyncio_helper import ApiTelegramException
from telebot.formatting import mlink
from telebot.util import quick_markup

from ruzbot import markups
from ruzbot.utils import ruz_client

from ruzclient.errors import RuzHttpError
from ruzbot.settings import settings

__version__ = "28.03.26"

# https://core.telegram.org/bots/api#sendmessage (тот же лимит у editMessageText)
TELEGRAM_MAX_MESSAGE_CHARS = 4096
_MESSAGE_TOO_LONG_MARKER = "\n\nMESSAGE TOO LONG"


def _truncate_with_too_long_marker(text: str) -> str:
    """Укладывает текст в лимит Telegram и добавляет маркер в конец."""
    max_body = TELEGRAM_MAX_MESSAGE_CHARS - len(_MESSAGE_TOO_LONG_MARKER)
    if max_body < 1:
        return _MESSAGE_TOO_LONG_MARKER[:TELEGRAM_MAX_MESSAGE_CHARS]
    if len(text) <= max_body:
        return text + _MESSAGE_TOO_LONG_MARKER
    return text[:max_body] + _MESSAGE_TOO_LONG_MARKER


def _is_message_too_long_error(exc: ApiTelegramException) -> bool:
    if exc.error_code != 400:
        return False
    desc = exc.description or ""
    return "MESSAGE_TOO_LONG" in desc or "message is too long" in desc.lower()


def _append_donation_footer(text: str, parse_mode: Optional[str]) -> str:
    """
    Для MarkdownV2 нельзя дописывать URL и скобки в «:)» без экранирования —
    Telegram вернёт ошибку парсинга сущностей. Ссылка оформляется через mlink.
    """
    url = (settings.payment_url or "").strip()
    if not url:
        return text
    if parse_mode == "MarkdownV2":
        return text + "\n\n" + mlink("Админ собирает деньги на кофе :)", url)
    return text + f"\n\nАдмин собирает деньги на кофе :)\n{url}"


class RuzBot(AsyncTeleBot):
    def __init__(self, version: str):
        super().__init__(settings.bot_token)
        self.version = version

    async def send_message(
        self,
        chat_id: Union[int, str],
        text: str,
        **kwargs,
    ) -> types.Message:
        parse_mode = kwargs.get("parse_mode", self.parse_mode)
        text = _append_donation_footer(text, parse_mode)
        try:
            return await super().send_message(chat_id, text, **kwargs)
        except ApiTelegramException as e:
            if _is_message_too_long_error(e):
                return await super().send_message(
                    chat_id, _truncate_with_too_long_marker(text), **kwargs
                )
            raise

    async def edit_message_text(self, text: str, **kwargs) -> Union[types.Message, bool]:
        parse_mode = kwargs.get("parse_mode", self.parse_mode)
        text = _append_donation_footer(text, parse_mode)
        try:
            return await super().edit_message_text(text, **kwargs)
        except ApiTelegramException as e:
            if _is_message_too_long_error(e):
                return await super().edit_message_text(
                    _truncate_with_too_long_marker(text), **kwargs
                )
            raise


bot = RuzBot(__version__)


@bot.message_handler(commands=["start"])
async def startCommand(message):
    """
    /start: главное меню или подсказки по регистрации (группа / незавершённая регистрация).
    """
    reply_message = (
        "Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать?\n"
    )
    markup = markups.generateStartMarkup()

    async with ruz_client() as client:
        try:
            user = await client.users.get_by_id(message.from_user.id)
        except RuzHttpError as e:
            if e.status_code == 404:
                user = None
            else:
                raise

        if user is not None and user.get("group_oid") and user.get("subgroup") is not None:
            pass
        elif user is not None and user.get("group_oid") and user.get("subgroup") is None:
            markup = quick_markup(
                {"Выбрать другую группу": {"callback_data": "configureGroup"}},
                row_width=1,
            )
            reply_message = (
                "Привет, я бот для просмотра расписания МГТУ.\n"
                "Группа выбрана — введите одну цифру подгруппы: 0, 1 или 2, чтобы завершить регистрацию.\n"
            )
        else:
            markup = quick_markup(
                {"Установить группу": {"callback_data": "configureGroup"}},
                row_width=1,
            )
            reply_message = (
                "Привет, я бот для просмотра расписания МГТУ. "
                "У тебя не установлена группа, друг.\n"
            )

    await bot.reply_to(message, reply_message, reply_markup=markup)
