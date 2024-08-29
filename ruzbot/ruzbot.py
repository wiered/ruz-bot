import json
import logging
import os
import random
import re

import telebot
from telebot.async_telebot import AsyncTeleBot
from telebot.types import KeyboardButton, ReplyKeyboardMarkup
from telebot.util import quick_markup

from db import load_from_csv, write_to_csv
from ruzparser import RuzParser
from utils import RANDOM_GROUP_NAMES, Users

BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = AsyncTeleBot(BOT_TOKEN)
parser = RuzParser()

users = Users()

def load_users() -> None:
    """
    Loads users from the CSV file and adds them to the users dictionary.
    """
    for user in load_from_csv("/db/db.csv"):
        # Get the user's id, group id and group name from the CSV file
        user_id = int(user.get("id"))
        group_id = int(user.get("group_id"))
        group_name = user.get("group_name")

        # Add the user to the users dictionary
        users.addUser(user_id, group_id, group_name)

async def setGroup(callback, group_id, group_name) -> str:
    """
    Sets a group for the user and saves it to the database.

    Args:
        callback (CallbackQuery): The callback query object.
        group_id (int): The user's group id.
        group_name (str): The user's group name.

    Returns:
        str: A message confirming that the group has been set.
    """
    print("Saving")
    # Get the user's id from the callback query
    user_id = callback.message.reply_to_message.from_user.id
    # Add the user to the users dictionary with the given group id and name
    users.addUser(user_id, group_id, group_name)
    # Get the user from the users dictionary
    user = users.getUser(user_id)

    print("New user: {}: {} - {}".format(
        user_id, 
        user.get("group_id"),
        user.get("group_name"),
        ))
    
    # Convert the users dictionary to a list of dictionaries
    # users_json = users.getUsersJson()
    # Write the list of dictionaries to the CSV file
    # write_to_csv("/db/db.csv", users_json)
    
    # Return a message confirming that the group has been set
    return "Группа установлена: {} - {}\n\n".format(group_id, group_name)

async def buttonsCallback(callback):
    """
    Handles the callback queries for the buttons.

    The callback queries are handled using pattern matching. The data of the
    callback query is split by spaces and the first element is used to determine
    which handler to call.

    Args:
        callback (CallbackQuery): The callback query object

    Returns:
        None
    """
    match callback.data.split(" "):
        # If the callback query is for the start button
        case ['start']:
            # Call the back command
            await backCommand(callback.message)

        # If the callback query is for the parse day button
        case ['parseDay', *args]:
            # Call the date command with the argument from the callback query
            await dateCommand(callback.message, args[0])

        # If the callback query is for the parse week button
        case ['parseWeek', *args]:
            # Call the week command with the argument from the callback query
            await weekCommand(callback.message, args[0])

        # If the callback query is for the configure group button
        case ['configureGroup']:
            # Call the set group command with the reply to message from the callback query
            await setGroupCommand(callback.message.reply_to_message)

        # If the callback query is for the show profile button
        case ['showProfile']:
            # Call the send profile command with the callback query message
            await sendProfileCommand(callback.message)

        # If the callback query is for the set group button
        case ['setGroup', *args]:
            try:
                # Convert the first argument to an integer
                group = int(args[0])
                # Call the set group command with the callback query and the arguments
                additional_message = await setGroup(callback, group, args[1])
                # Call the back command with the additional message
                await backCommand(callback.message, additional_message)
            except ValueError:
                # If the conversion to an integer fails, return
                return
        
        # If the callback query is not for any of the above handlers
        case _:
            # Print a message indicating that the callback query is not supported
            print("Wrong comand")

async def textCallback(callback):
    match tuple(i for i, pattern in enumerate([r"\W*\d*"]) if re.match(pattern, callback.text)):
        case (0,):
            group_name = callback.text
            groups_list = await parser.search_group(group_name)
            if not groups_list:
                await bot.reply_to(callback, f"❌ Указано недопустимое имя группы! Попробуйте ещё раз, например: {random.choice(RANDOM_GROUP_NAMES)}")
                return

            markup = quick_markup({
                group.get("label"): {"callback_data": f"setGroup {group.get('id')} {group.get('label')}"} for group in groups_list
            }, row_width=1)

            await bot.reply_to(callback, "Выбери группу", reply_markup=markup)
        case _:
            print("Wrong case")
     
async def callbackFilter(call) -> bool:
    """
    This function is a filter for the callback queries. It always returns True, meaning that all callback queries are allowed.

    Args:
        call (CallbackQuery): The callback query object

    Returns:
        bool: Always True
    """
    return True

async def dateCommand(message, _timedelta):
    """
    Handler for the dateCommand callback query. It parses the schedule for the specified date and sends it back to the user.

    Args:
        message (Message): The message object
        _timedelta (str): The timedelta in days from the current date

    Returns:
        None
    """
    _timedelta = int(_timedelta)
    print('Running date command {}'.format(_timedelta))
    group_id = users.getUser(message.reply_to_message.from_user.id).get("group_id")
    data = await parser.parseDay(group_id, _timedelta)
    
    reply_message = parser.getLessions(data, _timedelta)
    markup = quick_markup({
        "Пред. день": {'callback_data' : 'parseDay {}'.format(_timedelta - 1)},
        "Назад": {'callback_data' : 'start'},
        "След. день": {'callback_data' : 'parseDay {}'.format(_timedelta + 1)}
    }, row_width=3)
    
    await bot.edit_message_text(reply_message, message.chat.id, message.message_id, reply_markup = markup)

async def weekCommand(message, _timedelta):
    """
    Handler for the weekCommand callback query. It parses the schedule for the specified week and sends it back to the user.

    Args:
        message (Message): The message object
        _timedelta (str): The timedelta in weeks from the current week

    Returns:
        None
    """
    _timedelta = int(_timedelta)
    print('Running week command {}'.format(_timedelta))
    # Get the user's group id from the users dictionary
    group_id = users.getUser(message.reply_to_message.from_user.id).get("group_id")
    # Parse the schedule for the specified week
    data = await parser.parseWeek(group_id, _timedelta)
    
    # Get the formatted schedule for the week
    reply_message = parser.getLessionsFromWeek(data)
    # Create a markup with buttons for the previous week, next week and going back to the start
    markup = quick_markup({
        "Пред. нед.": {'callback_data' : 'parseWeek {}'.format(_timedelta - 1)},
        "Назад": {'callback_data' : 'start'},
        "След. нед.": {'callback_data' : 'parseWeek {}'.format(_timedelta + 1)}
    }, row_width=3)
    
    # Edit the message with the new text and reply markup
    await bot.edit_message_text(reply_message, message.chat.id, message.message_id, reply_markup = markup, parse_mode = "MarkdownV2")

async def setGroupCommand(message):
    """
    Handler for the setGroupCommand callback query. It prompts the user to enter the name of their group.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    # Register the textCallback as a message handler
    bot.register_message_handler(callback = textCallback)
    # Reply to the message with a prompt to enter the group name
    await bot.reply_to(message, "Введи имя группы полностью(например ИС221): ")

async def sendProfileCommand(message):
    """
    Handler for the sendProfileCommand callback query. It shows the user's current group and provides buttons to change the group or go back to the start.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    user = users.getUser(message.reply_to_message.from_user.id)
    group_id = user.get("group_id")
    group_name = user.get("group_name")

    # Create a message with the user's group and buttons to change the group or go back to the start
    reply_message = "Ваша группа: {} - {}".format(group_id, group_name)
    markup = quick_markup({
        "Установить группу": {'callback_data' : 'configureGroup'},
        "Назад": {'callback_data' : 'start'},
        "GitHub": {'url' : 'https://github.com/wiered'},
    }, row_width=2)
    
    # Edit the message with the new text and reply markup
    await bot.edit_message_text(reply_message, message.chat.id, message.message_id, reply_markup = markup)

async def backCommand(message, additional_message: str = ""):
    """
    Handler for the back command. It shows the main menu with options to view the schedule for today, tomorrow, this week, next week, or to view the user's profile.

    Args:
        message (Message): The message object
        additional_message (str): An optional message to be displayed at the top of the menu

    Returns:
        None
    """
    reply_message = additional_message + "Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать? \nУчитывайте что бот в бете."
    markup = quick_markup({
        # Button to view the schedule for today
        "Сегодня": {'callback_data' : 'parseDay 0'},
        # Button to view the schedule for tomorrow
        "Завтра": {'callback_data' : 'parseDay 1'},
        # Button to view the schedule for this week
        "Эта неделя": {'callback_data' : 'parseWeek 0'},
        # Button to view the schedule for next week
        "Следующая неделя": {'callback_data' : 'parseWeek 1'},
        # Button to view the user's profile
        "Профиль": {'callback_data' : 'showProfile'},
    }, row_width=3)
    if not users.isUserKnown(message.reply_to_message.from_user.id):
        # If the user is not in the database, show the "Set group" button
        markup = quick_markup({
            "Установить группу": {'callback_data' : 'group'},
        }, row_width=1)
    
    # Edit the message with the new text and reply markup
    await bot.edit_message_text(reply_message, message.chat.id, message.message_id, reply_markup = markup)

@bot.message_handler(commands=['start'])
async def startCommand(message):
    """
    Handler for the /start command. It shows the main menu with options to view the schedule for today, tomorrow, this week, next week, or to view the user's profile.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    # Create a markup with buttons for the main menu
    markup = quick_markup({
        # Button to view the schedule for today
        "Сегодня": {'callback_data' : 'parseDay 0'},
        # Button to view the schedule for tomorrow
        "Завтра": {'callback_data' : 'parseDay 1'},
        # Button to view the schedule for this week
        "Эта неделя": {'callback_data' : 'parseWeek 0'},
        # Button to view the schedule for next week
        "Следующая неделя": {'callback_data' : 'parseWeek 1'},
        # Button to view the user's profile
        "Профиль": {'callback_data' : 'showProfile'},
    }, row_width=3)
    
    # If the user is not in the database, show the "Set group" button
    if not users.isUserKnown(message.from_user.id):
        markup = quick_markup({
            "Установить группу": {'callback_data' : 'configureGroup'},
        }, row_width=1)
    
    # Register the buttonsCallback function as a callback query handler
    bot.register_callback_query_handler(callback = buttonsCallback, func = callbackFilter)
    # Reply to the message with the main menu
    await bot.reply_to(message, """Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать?
Учитывайте что бот в бете.""", reply_markup = markup)

@bot.message_handler(commands=['getdb'])
async def getDB(message):
    """
    Handler for the /getdb command. It sends a JSON dump of all users in the database to the user.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    logging.info('/getdb command runned by: {}, {}'.format(
        message.from_user.id, type(message.from_user.id)
        ))
    # Only allow the admin to run this command
    if message.from_user.id != int(os.environ.get('ADMIN_ID')):
        return
    
    # Get all users from the database
    reply_message = json.dumps(users.getAllUsers(), ensure_ascii=False)
    
    # Send the JSON dump of users to the user
    await bot.reply_to(message, reply_message)

@bot.message_handler(commands=['setdb'])
async def setDB(message):
    """
    Handler for the /setdb command. It sets the database to the given path and saves it to the environment.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    logging.info('/setdb command runned by: {}, {}'.format(
        message.from_user.id, type(message.from_user.id)
        ))
    # Only allow the admin to run this command
    if message.from_user.id != int(os.environ.get('ADMIN_ID')):
        return
    
    # Get the new database path from the message
    db = json.loads(message.text, ensure_ascii=False)
    # Set the new database path
    users.setDB(db)
    # Reply to the user with a success message
    reply_message = 'База данных успешно обновлена'
    
    await bot.reply_to(message, reply_message)

load_users()
print(users.getAllUsers())
