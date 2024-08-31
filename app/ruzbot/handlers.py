import logging
import re

from telebot.async_telebot import AsyncTeleBot
from telebot.util import quick_markup
from utils import getRandomGroup

import db
from db import users
from ruzbot import commands
from ruzparser import RuzParser

parser = RuzParser()

async def textCallbackHandler(callback, bot: AsyncTeleBot):
    match tuple(i for i, pattern in enumerate([
                                            r"\w+\d+",
                                            r"\d",
                                            ]) if re.match(pattern, callback.text)):
        case (0,):
            group_name = callback.text
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
            message = await bot.reply_to(callback, "Ваша подгруппа установлена!")
            
            additional_message = "Ваша подгруппа установлена: {}!\n\n".format(callback.text)
            await commands.backCommand(bot, message, additional_message)
        case _:
            logging.warn("Wrong case")

def register_handlers(bot: AsyncTeleBot):
    bot.register_message_handler(textCallbackHandler, pass_bot=True)
  