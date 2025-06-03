import logging
import re

from telebot.async_telebot import AsyncTeleBot
from telebot.util import quick_markup
from utils import getRandomGroup

from db import db
from ruzbot import commands
from ruzparser import RuzParser

# --------------------
# Logging Configuration
# --------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

logger.propagate = False


async def callbackFilter(call) -> bool:
    """
    This function is a filter for the callback queries.
    It always returns True, meaning that all callback queries are allowed.
    """
    logger.debug(f"callbackFilter called for call_id={call.id}")
    return True


async def textCallbackHandler(callback, bot: AsyncTeleBot):
    """
    Handle text-based callbacks matching certain patterns:
    - r"\w+\d+"     (e.g. "ABC123")
    - r"\w+-\w+\d+" (e.g. "AB-CD123")
    - r"\d"         (single digit for sub-group)
    """
    logger.info(f"textCallbackHandler invoked: user_id={callback.from_user.id}, text={callback.text!r}")
    patterns = [r"\w+\d+", r"\w+-\w+\d+", r"\d"]
    match tuple(i for i, pattern in enumerate(patterns) if re.match(pattern, callback.text)):
        case (0,) | (1,):
            group_name = callback.text
            logger.debug(f"Group selection text detected: {group_name}")
            parser = RuzParser()
            groups_list = await parser.search_group(group_name)
            if not groups_list:
                logger.warning(f"No groups found for '{group_name}'")
                await bot.reply_to(
                    callback,
                    f"❌ Указано недопустимое имя группы! Попробуйте ещё раз, например: {getRandomGroup()}"
                )
                return

            markup = quick_markup({
                group.get("label"):
                    {
                        "callback_data": f"setGroup {group.get('id')} {group.get('label')}"
                    } for group in groups_list
            }, row_width=1)

            logger.debug(f"Replying with {len(groups_list)} group options")
            await bot.reply_to(callback, "Выбери группу", reply_markup=markup)

        case (2,):
            sub_group_number = int(callback.text)
            logger.debug(f"Sub-group selection detected: {sub_group_number} for user_id={callback.from_user.id}")
            db.updateUserSubGroup(user_id=callback.from_user.id, sub_group=sub_group_number)
            message = await bot.reply_to(callback, "Ваша группа и подгруппа установлены!")
            logger.info(f"Updated sub_group={sub_group_number} for user_id={callback.from_user.id}")

            await commands.sendProfileCommand(bot, message)

        case _:
            logger.warning(f"Wrong case in textCallbackHandler: {callback.text!r}")


async def buttonsCallback(callback, bot: AsyncTeleBot):
    """
    Handles the callback queries for the buttons.
    Routes based on callback.data.
    """
    logger.info(f"buttonsCallback invoked: user_id={callback.from_user.id}, data={callback.data!r}")

    match callback.data.split(" "):
        case ['start']:
            logger.debug("Button 'start' pressed")
            await commands.backCommand(bot, callback.message)

        case ['parseDay', *args]:
            date_arg = args[0] if args else None
            logger.debug(f"Button 'parseDay' pressed with arg={date_arg}")
            await commands.dateCommand(bot, callback.message, date_arg)

        case ['parseWeek', *args]:
            date_arg = args[0] if args else None
            logger.debug(f"Button 'parseWeek' pressed with arg={date_arg}")
            await commands.weekCommand(bot, callback.message, date_arg)

        case ['showProfile']:
            logger.debug("Button 'showProfile' pressed")
            await commands.sendProfileCommand(bot, callback.message)

        case ['configureGroup']:
            logger.debug("Button 'configureGroup' pressed")
            await commands.setGroupCommand(bot, callback.message.reply_to_message)

        case ['configureSubGroup']:
            logger.debug("Button 'configureSubGroup' pressed")
            await commands.setSubGroupCommand(bot, callback.message)

        case ['setGroup', *args]:
            if len(args) < 2:
                logger.error(f"setGroup callback missing arguments: {args}")
                return
            try:
                group = int(args[0])
                label = args[1]
                logger.debug(f"Button 'setGroup' pressed with group={group}, label={label}")
                await commands.setGroup(bot, callback, group, label)
                await commands.setSubGroupCommand(bot, callback.message)
            except ValueError as e:
                logger.error(f"Invalid group id in setGroup callback: {args[0]!r} – {e}")
                return

        case _:
            logger.warning(f"Unsupported callback data: {callback.data!r}")


def register_handlers(bot: AsyncTeleBot):
    logger.info("Registering handlers with the bot")
    bot.register_message_handler(textCallbackHandler, pass_bot=True)
    bot.register_callback_query_handler(callback=buttonsCallback, func=callbackFilter, pass_bot=True)
    logger.info("Handlers registered successfully")
