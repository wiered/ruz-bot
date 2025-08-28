import logging
from datetime import datetime, timedelta
from telebot.util import quick_markup

from db import db
from ruzparser import RuzParser
from ruzbot import markups
from utils import formatters

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

async def dateCommand(bot, message, date: str):
    """
    Handler for the dateCommand callback query.
    It parses the schedule for the specified date and sends it back to the user.
    """
    logger.info(f"dateCommand called: user={message.reply_to_message.from_user.id}, date={date!r}")
    user_id = message.reply_to_message.from_user.id

    if not db.isUserHasSubGroup(user_id):
        logger.warning(f"User {user_id} has no sub_group; redirecting to backCommand")
        await backCommand(bot, message)
        return

    user = db.getUser(user_id)
    group_id = user.get("group_id")
    logger.debug(f"Fetched user from DB: user_id={user_id}, group_id={group_id}, sub_group={user.get('sub_group')!r}")

    # Determine target_date
    target_date = datetime.today()
    try:
        flag = int(date)
        if flag == -1:
            target_date = datetime.today()
        elif flag == -2:
            target_date = datetime.today() + timedelta(days=1)
        logger.debug(f"Date flag interpreted: flag={flag}, target_date={target_date.date()}")
    except ValueError:
        target_date = datetime.strptime(date, '%Y-%m-%d')
        logger.debug(f"Parsed date string: target_date={target_date.date()}")

    # Fetch or parse data
    if db.isDayInDB(group_id, target_date):
        logger.debug(f"Day {target_date.date()} is cached for group {group_id}; fetching from DB")
        data = db.getDay(user_id, target_date)
    else:
        logger.info(f"Day {target_date.date()} not in DB; parsing from site")
        parser = RuzParser()
        data = await parser.parseDay(group_id, target_date)

    reply_message = formatters.formatDayMessage(data, target_date)
    logger.debug(f"Formatted day message length: {len(reply_message)} characters")

    previous_day = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
    logger.debug(f"Navigation dates: previous={previous_day}, next={next_day}")

    markup = quick_markup({
        "Пред. день": {'callback_data': f'parseDay {previous_day}'},
        "Назад": {'callback_data': 'start'},
        "След. день": {'callback_data': f'parseDay {next_day}'}
    }, row_width=3)

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode='MarkdownV2'
    )
    logger.info(f"dateCommand completed: edited message for user={user_id}")


async def weekCommand(bot, message, _timedelta):
    """
    Handler for the weekCommand callback query.
    It parses the schedule for the specified week and sends it back to the user.
    """
    logger.info(f"weekCommand called: user={message.reply_to_message.from_user.id}, _timedelta={_timedelta!r}")
    user_id = message.reply_to_message.from_user.id

    if not db.isUserHasSubGroup(user_id):
        logger.warning(f"User {user_id} has no sub_group; redirecting to backCommand")
        await backCommand(bot, message)
        return

    user = db.getUser(user_id)
    group_id = user.get("group_id")
    logger.debug(f"Fetched user from DB: user_id={user_id}, group_id={group_id}, sub_group={user.get('sub_group')!r}")

    try:
        delta_weeks = int(_timedelta)
        logger.debug(f"Converted _timedelta to int: delta_weeks={delta_weeks}")
    except ValueError:
        delta_weeks = 0
        logger.error(f"Invalid _timedelta '{_timedelta}', defaulting to 0")

    date = datetime.today() + timedelta(weeks=delta_weeks)
    logger.debug(f"Week base date: {date.date()}")

    if db.isWeekInDB(group_id, date):
        logger.debug(f"Week starting {date.date()} is cached for group {group_id}; fetching from DB")
        data, last_update = db.getWeek(user_id, date)
    else:
        logger.info(f"Week starting {date.date()} not in DB; parsing from site")
        last_update = datetime.now().strftime("%d.%m %H:%M:%S")
        parser = RuzParser()
        data = await parser.parseWeek(group_id, date)

    reply_message = formatters.formatWeekMessage(date, data) + formatters.escapeMessage(f"Последнее обновление: {last_update}")
    logger.debug(f"Formatted week message length: {len(reply_message)} characters")

    prev_week = delta_weeks - 1
    next_week = delta_weeks + 1
    logger.debug(f"Week navigation: prev={prev_week}, next={next_week}")

    markup = quick_markup({
        "Пред. нед.": {'callback_data': f'parseWeek {prev_week}'},
        "Назад": {'callback_data': 'start'},
        "След. нед.": {'callback_data': f'parseWeek {next_week}'}
    }, row_width=3)

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode="MarkdownV2"
    )
    logger.info(f"weekCommand completed: edited message for user={user_id}")


async def setGroupCommand(bot, message):
    """
    Handler for the setGroupCommand callback query.
    It prompts the user to enter the name of their group.
    """
    logger.info(f"setGroupCommand called: user={message.from_user.id if message.from_user else 'unknown'}")
    await bot.reply_to(
        message,
        "Введи имя группы полностью(например ИС221 или МАГ-М241): "
    )
    logger.debug("Prompted user to enter group name")


async def setSubGroupCommand(bot, message):
    """
    Handler for the setSubGroupCommand callback query.
    It prompts the user to enter the number of their subgroup.
    """
    logger.info(f"setSubGroupCommand called: user={message.from_user.id if message.from_user else 'unknown'}")
    reply_message = (
        "Введите номер подгруппы. Номером подгруппы должно быть одно число.\n"
        "Если ваш номер подргуппы не является числом, то введите 0."
    )
    await bot.reply_to(message, reply_message)
    logger.debug("Prompted user to enter sub_group number")


async def sendProfileCommand(bot, message):
    """
    Handler for the sendProfileCommand callback query.
    It shows the user's current group and provides buttons
    to change the group or go back to the start.
    """
    logger.info(f"sendProfileCommand called: user={message.reply_to_message.from_user.id}")
    user_id = message.reply_to_message.from_user.id

    if not db.isUserHasSubGroup(user_id):
        logger.warning(f"User {user_id} has no sub_group; redirecting to backCommand")
        await backCommand(bot, message)
        return

    user = db.getUser(user_id)
    if not user:
        logger.error(f"sendProfileCommand: user {user_id} not found in DB")
        return

    group_id = user.get("group_id")
    group_name = user.get("group_name")
    sub_group = user.get("sub_group")
    logger.debug(f"Fetched user from DB: user_id={user_id}, group_name={group_name}, sub_group={sub_group}, group_id={group_id}")

    reply_message = (
        f"Ваш профиль: \n"
        f"Группа: {group_name}\n"
        f"Подгруппа: {sub_group}\n"
        f"group_id: {group_id}\n"
        f"bot_version: {bot.__version__}"
    )
    markup = quick_markup({
        "Установить группу": {'callback_data': 'configureGroup'},
        "Назад": {'callback_data': 'start'},
        "GitHub": {'url': 'https://github.com/wiered/ruz-bot'},
    }, row_width=2)

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup
    )
    logger.info(f"sendProfileCommand completed: profile shown for user={user_id}")


async def setGroup(bot, callback, group_id, group_name) -> str:
    """
    Sets a group for the user and saves it to the database.
    """
    user_id = callback.message.reply_to_message.from_user.id
    logger.info(f"setGroup called: user_id={user_id}, group_id={group_id}, group_name={group_name!r}")

    if not db.isUserKnown(user_id):
        logger.debug(f"User {user_id} not known; adding to DB with group_id={group_id}, group_name={group_name!r}")
        db.addUser(user_id, group_id, group_name)
        logger.info(f"User {user_id} added with group {group_name}")
    else:
        logger.debug(f"User {user_id} already known; updating group to {group_id}, name={group_name!r}")
        db.updateUser(user_id, group_id, group_name)
        logger.info(f"User {user_id} updated to group {group_name}")


async def backCommand(bot, message, additional_message: str = ""):
    """
    Handler for the back command.
    It shows the main menu with options to view the schedule for today,
    tomorrow, this week, next week, or to view the user's profile.
    """
    user_id = message.reply_to_message.from_user.id
    logger.info(f"backCommand called: user_id={user_id}, additional_message={additional_message!r}")

    reply_message = additional_message + "Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать?\n"
    markup = markups.generateStartMarkup()
    logger.debug("Generated start markup")

    if not db.isUserHasSubGroup(user_id):
        logger.warning(f"User {user_id} has no sub_group; showing only setSubGroup button")
        markup = quick_markup({
            "Установить подгруппу": {'callback_data': 'configureSubGroup'},
        }, row_width=1)
        reply_message = "Привет, я бот для просмотра расписания МГТУ. У тебя не установленна подгруппа, друг.\n"

    if not db.isUserKnown(user_id):
        logger.warning(f"User {user_id} not known; showing only setGroup button")
        markup = quick_markup({
            "Установить группу": {'callback_data': 'group'},
        }, row_width=1)

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup
    )
    logger.info(f"backCommand completed: menu shown for user={user_id}")
