import asyncio
import os

import db
import ruzparser
from ruzbot import bot
from daily_timer import timerPooling
from ruzbot.handlers import register_handlers

async def updateLessonsSchedulesChache() -> None:
    """
    Updates the lessons for all groups in the database.
    
    This function is called periodically to update the lessons for all groups in the database.
    
    :return: None
    """
    
    if bool(os.environ.get('DOUPDATE')):
        return
        
    # Get all groups from the database
    groups = db.getAllGroupsList()
    
    # Get parser
    parser = ruzparser.RuzParser()
    
    # For each group, parse the schedule and save it to the database
    for group in groups:
        print(f"Parsing {group}")
        # Parse the schedule for the group
        lessons_for_group = await parser.parseSchedule(group)
        
        # Save the schedule to the database
        db.saveMonthLessonsToDB(group, lessons_for_group)
        await asyncio.sleep(20)

async def startBot():
    # Register the textCallback as a message handler
    register_handlers(bot)
    
    await bot.polling()
    
async def startTimer():
    await timerPooling()
    
async def main():
    """
    Main entry point of the program.

    This function starts the bot.
    """
    
    await updateLessonsSchedulesChache()
    
    # Creating tasks for bot and timer
    bot_task = asyncio.create_task(startBot())
    timer_task = asyncio.create_task(startTimer())
    
    await bot_task
    await timer_task
    
if __name__ == "__main__":
    asyncio.run(main())
