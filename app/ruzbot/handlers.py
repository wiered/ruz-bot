import logging
import re

from telebot.async_telebot import AsyncTeleBot
from telebot.util import quick_markup
from utils import getRandomGroup

import db
from db import users
from ruzbot import commands
from ruzparser import RuzParser

async def callbackFilter(call) -> bool:
    """
    This function is a filter for the callback queries. 
    It always returns True, meaning that all callback queries are allowed.

    Args:
        call (CallbackQuery): The callback query object

    Returns:
        bool: Always True
    """
    return True


async def textCallbackHandler(callback, bot: AsyncTeleBot):
    match tuple(i for i, pattern in enumerate([
                                            r"\w+\d+",
                                            r"\d",
                                            ]) if re.match(pattern, callback.text)):
        case (0,):
            group_name = callback.text
            parser = RuzParser()
            groups_list = await parser.search_group(group_name)
            if not groups_list:
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

            await bot.reply_to(callback, "Выбери группу", reply_markup=markup)
        case (1, ):
            sub_group_number = int(callback.text)
            users.update_one({"id": callback.from_user.id}, {"$set": {"sub_group": sub_group_number}})
            message = await bot.reply_to(callback, "Ваша группа и подгруппа установлены!")
            
            await commands.sendProfileCommand(bot, message)
        case _:
            logging.warn("Wrong case")


async def buttonsCallback(callback, bot: AsyncTeleBot):
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
            await commands.backCommand(bot, callback.message)

        # If the callback query is for the parse day button
        case ['parseDay', *args]:
            # Call the date command with the argument from the callback query
            await commands.dateCommand(bot, callback.message, args[0])

        # If the callback query is for the parse week button
        case ['parseWeek', *args]:
            # Call the week command with the argument from the callback query
            await commands.weekCommand(bot, callback.message, args[0])
            
        # If the callback query is for the show profile button
        case ['showProfile']:
            # Call the send profile command with the callback query message
            await commands.sendProfileCommand(bot, callback.message)

        # If the callback query is for the configure group button
        case ['configureGroup']:
            # Call the set group command with the reply to message from the callback query
            await commands.setGroupCommand(bot, callback.message.reply_to_message)
            
        # If the callback query is for the configure sub group button    
        case ['configureSubGroup']:
            # Call the send profile command with the callback query message
            await commands.setSubGroupCommand(bot, callback.message)

        # If the callback query is for the set group button
        case ['setGroup', *args]:
            try:
                # Convert the first argument to an integer
                group = int(args[0])
                # Call the set group command with the callback query and the arguments
                additional_message = await commands.setGroup(bot, callback, group, args[1])
                # Call the back command with the additional message
                await commands.setSubGroupCommand(bot, callback.message)
            except ValueError:
                # If the conversion to an integer fails, return
                return
        
        # If the callback query is not for any of the above handlers
        case _:
            # Print a message indicating that the callback query is not supported
            logging.warn("Wrong comand")


def register_handlers(bot: AsyncTeleBot):
    bot.register_message_handler(textCallbackHandler, pass_bot=True)
    bot.register_callback_query_handler(callback = buttonsCallback, func = callbackFilter, pass_bot=True)
  