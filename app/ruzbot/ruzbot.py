import os

from telebot.async_telebot import AsyncTeleBot
from telebot.util import quick_markup

from db import db
from ruzbot import markups

BOT_TOKEN = os.environ.get('BOT_TOKEN')

bot = AsyncTeleBot(BOT_TOKEN)


@bot.message_handler(commands=['start'])
async def startCommand(message):
    """
    Handler for the /start command. 
    It shows the main menu with options to view the schedule for today, 
    tomorrow, this week, next week, or to view the user's profile.

    Args:
        message (Message): The message object

    Returns:
        None
    """
    reply_message = "Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать?\n"
    
    # Create a markup with buttons for the main menu
    markup = markups.start_markup
    
    if not db.isUserHasSubGroup(message.from_user.id):
        markup = quick_markup({
            "Установить подгруппу": {'callback_data' : 'configureSubGroup'},
        }, row_width=1)
        reply_message = "Привет, я бот для просмотра расписания МГТУ. У тебя не установленна подгруппа, друг.\n"
    
    # If the user is not in the database, show the "Set group" button
    if not db.isUserKnown(message.from_user.id):
        markup = quick_markup({
            "Установить группу": {'callback_data' : 'configureGroup'},
        }, row_width=1)
        
    # Register the buttonsCallback function as a callback query handler
    
    # Reply to the message with the main menu
    await bot.reply_to(
        message, 
        reply_message, 
        reply_markup = markup)


print(list(db.users.find()))
