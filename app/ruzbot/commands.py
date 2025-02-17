from datetime import datetime, timedelta
import logging
from telebot.util import quick_markup

from db import db
from ruzparser import RuzParser
from ruzbot import markups
from utils import formatters

async def dateCommand(bot, message, date: str):
    """
    Handler for the dateCommand callback query.
    It parses the schedule for the specified date and sends it back to the user.

    Args:
        message (Message): The message object
        date(str): The date in '%Y-%m-%d' format

    Returns:
        None
    """

    # convert _timedelta to int
    logging.debug('Running date command {}'.format(date))
    # get user id from message
    user_id = message.reply_to_message.from_user.id
    if not db.isUserHasSubGroup(user_id):
        await backCommand(bot, message)
        return
    # get user's group id from database
    user = db.getUser(user_id)
    group_id = user.get("group_id")


    target_date = datetime.today()
    try:
        flag = int(date)
        if flag == -1:
            target_date = datetime.today()
        elif flag == -2:
            target_date = datetime.today() + timedelta(days=1)
    except:
        # parse date
        target_date = datetime.strptime(date, '%Y-%m-%d')

    if db.isDayInDB(group_id, target_date):
        # get data from db
        data = db.getDay(user_id, target_date)
    else:
        # parse the schedule for the specified date
        parser = RuzParser()
        data = await parser.parseDay(group_id, target_date)

    reply_message = formatters.formatDayMessage(data, target_date)

    previous_day = (target_date - timedelta(days=1)).strftime('%Y-%m-%d')
    next_day = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')

    markup = quick_markup({
        "Пред. день": {'callback_data' : 'parseDay {}'.format(previous_day)},
        "Назад": {'callback_data' : 'start'},
        "След. день": {'callback_data' : 'parseDay {}'.format(next_day)}
    }, row_width=3)

    await bot.edit_message_text(
        text = reply_message,
        chat_id = message.chat.id,
        message_id = message.message_id,
        reply_markup = markup,
        parse_mode = 'MarkdownV2'
        )


async def weekCommand(bot, message, _timedelta):
    """
    Handler for the weekCommand callback query.
    It parses the schedule for the specified week and sends it back to the user.

    Args:
        message (Message): The message object
        _timedelta (str): The timedelta in weeks from the current week

    Returns:
        None
    """
    logging.debug('Running week command {}'.format(_timedelta))
    user_id = message.reply_to_message.from_user.id

    if not db.isUserHasSubGroup(user_id):
        await backCommand(bot, message)
        return

    # Get the user's group id from database
    user = db.getUser(user_id)
    group_id = user.get("group_id")

    # get date
    _timedelta = int(_timedelta)
    date = datetime.today() + timedelta(weeks=_timedelta)

    # check if week is chached or not
    if db.isWeekInDB(group_id, date):
        # if yes get data from db
        data, last_update = db.getWeek(user_id, date)
    else:
        parser = RuzParser()
        # if not, then parse it from site
        last_update = datetime.now().strftime("%d.%m %H:%M:%S")
        data = await parser.parseWeek(group_id, date)

    # Get the formatted schedule for the week
    reply_message = formatters.formatWeekMessage(data) + formatters.escapeMessage(f"Последнее обновление: {last_update}")
    # Create a markup with buttons for the previous week,
    #   next week and going back to the start
    markup = quick_markup({
        "Пред. нед.": {'callback_data' : 'parseWeek {}'.format(_timedelta - 1)},
        "Назад": {'callback_data' : 'start'},
        "След. нед.": {'callback_data' : 'parseWeek {}'.format(_timedelta + 1)}
    }, row_width=3)

    # Edit the message with the new text and reply markup
    await bot.edit_message_text(
        text = reply_message,
        chat_id = message.chat.id,
        message_id = message.message_id,
        reply_markup = markup,
        parse_mode = "MarkdownV2"
        )


async def setGroupCommand(bot, message):
    """
    Handler for the setGroupCommand callback query.
    It prompts the user to enter the name of their group.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    # Register the textCallback as a message handler
    # bot.register_message_handler(callback = textCallback, pass_bot=True, bot = bot)
    # Reply to the message with a prompt to enter the group name
    await bot.reply_to(
        message,
        "Введи имя группы полностью(например ИС221 или МАГ-М241): "
        )


async def setSubGroupCommand(bot, message):
    """
    Handler for the setGroupCommand callback query.
    It prompts the user to enter the name of their group.

    Args:
        message (Message): The message object

    Returns:
        None
    """

    # Reply to the message with a prompt to enter the group name
    reply_message: str = "Введите номер подгруппы. Номером подгруппы должно быть одно число."
    reply_message += "\nЕсли ваш номер подргуппы не является числом, то введите 0."
    await bot.reply_to(
        message,
        reply_message
        )


async def sendProfileCommand(bot, message):
    """
    Handler for the sendProfileCommand callback query.
    It shows the user's current group and provides buttons
    to change the group or go back to the start.

    Args:
        message (Message): The message object

    Returns:
        None
    """

    # Get user id from message
    user_id = message.reply_to_message.from_user.id
    if not db.isUserHasSubGroup(user_id):
        await backCommand(bot, message)

    # Get user from database
    user = db.getUser(user_id)
    # Get user's group id and name
    group_id = user.get("group_id")
    group_name = user.get("group_name")
    sub_group = user.get("sub_group")

    # Create a message with the user's group and buttons
    #   to change the group or go back to the start
    reply_message = f"Ваш профиль: \nГруппа: {group_name}\nПодгруппа: {sub_group}\ngroup_id: {group_id}\nbot_version: {bot.__version__}"
    markup = quick_markup({
        "Установить группу": {'callback_data' : 'configureGroup'},
        "Назад": {'callback_data' : 'start'},
        "GitHub": {'url' : 'https://github.com/wiered/ruz-bot'},
    }, row_width=2)

    # Edit the message with the new text and reply markup
    await bot.edit_message_text(
        text = reply_message,
        chat_id = message.chat.id,
        message_id = message.message_id,
        reply_markup = markup
        )


async def setGroup(bot, callback, group_id, group_name) -> str:
    """
    Sets a group for the user and saves it to the database.

    Args:
        callback (CallbackQuery): The callback query object.
        group_id (int): The user's group id.
        group_name (str): The user's group name.

    Returns:
        str: A message confirming that the group has been set.
    """

    # Get the user's id from the callback query
    user_id = callback.message.reply_to_message.from_user.id

    # If the user is not already in the database, add them
    if not db.isUserKnown(user_id):
        logging.debug(
            "Adding user into database: {} - {}".format(user_id, group_name)
            )
        db.addUser(user_id, group_id, group_name)
    else:
        logging.debug("Updating user in database: {} - {}".format(user_id, group_name))
        # Else update user in database
        db.updateUser(user_id, group_id, group_name)


async def backCommand(bot, message, additional_message: str = ""):
    """
    Handler for the back command.
    It shows the main menu with options to view the schedule for today,
    tomorrow, this week, next week, or to view the user's profile.

    Args:
        message (Message): The message object
        additional_message (str): An optional message
                                    to be displayed at the top of the menu

    Returns:
        None
    """

    # Create a message with buttons to view the schedule for
    #   today, tomorrow, this week, next week, or to view the user's profile
    reply_message = additional_message
    reply_message += "Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать?\n"
    markup = markups.generateStartMarkup()

    # Get user id from mesage
    user_id = message.reply_to_message.from_user.id

    if not db.isUserHasSubGroup(message.from_user.id):
        markup = quick_markup({
            "Установить подгруппу": {'callback_data' : 'configureSubGroup'},
        }, row_width=1)
        reply_message = "Привет, я бот для просмотра расписания МГТУ. У тебя не установленна подгруппа, друг.\n"

    # Check if user not in the database
    if not db.isUserKnown(user_id):
        # If the user is not in the database, show the "Set group" button
        markup = quick_markup({
            "Установить группу": {'callback_data' : 'group'},
        }, row_width=1)

    # Edit the message with the new text and reply markup
    await bot.edit_message_text(
        text = reply_message,
        chat_id = message.chat.id,
        message_id = message.message_id,
        reply_markup = markup
        )
