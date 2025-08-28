import asyncio
import logging
import os

from dotenv import load_dotenv

import ruzparser
from daily_timer import timerPooling
from db import db
from ruzbot import bot
from ruzbot.handlers import register_handlers

load_dotenv()

DO_UPDATE = bool(int(os.environ.get("DOUPDATE")))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

async def updateLessonsSchedulesChache() -> None:
    """
    Updates the lessons for all groups in the database.

    This function is called at the start of the program if configured.

    :return: None
    """

    logging.info("Startup schedules update...")

    # Get all groups from the database
    groups = db.getAllGroupsList()

    # Get parser
    parser = ruzparser.RuzParser()

    groups_count = len(groups)
    # For each group, parse the schedule and save it to the database
    for num, group in enumerate(groups):
        logging.debug(f"Parsing... {group} ({num+1}/{groups_count})")
        # Parse the schedule for the group
        lessons_for_group = await parser.parseSchedule(group)

        # Save the schedule to the database
        db.saveScheduleToDB(group, lessons_for_group)
        await asyncio.sleep(20)

async def startBot():

    logging.info("Starting bot...")

    # Register the textCallback as a message handler
    register_handlers(bot)

    await bot.polling()

async def startTimer():
    logging.info("Starting timer...")

    await timerPooling()

async def main():
    """
    Main entry point of the program.

    This function starts the bot.
    """

    if DO_UPDATE:
        await updateLessonsSchedulesChache()

    # Creating tasks for bot and timer
    bot_task = asyncio.create_task(startBot())
    timer_task = asyncio.create_task(startTimer())

    await bot_task
    await timer_task

if __name__ == "__main__":
    asyncio.run(main())
