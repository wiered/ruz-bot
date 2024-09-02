import asyncio
from datetime import datetime
import logging

import db
from db import getAllGroupsList, saveMonthLessonsToDB, lessons
from ruzparser import RuzParser

class Timer:
    """
    Timer class for running callbacks after a certain amount of time.

    :param timeout: The time in seconds to wait before running the callback.
    :param callback: The function to be called after the timeout.
    """

    def __init__(self, timeout, callback):
        """
        Initialize the Timer.

        :param timeout: The time in seconds to wait before running the callback.
        :param callback: The function to be called after the timeout.
        """
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        """
        Wait for the timeout and call the callback.
        """
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
        """
        Cancel the timer and stop the callback from being called.
        """
        self._task.cancel()

async def isParsingTime() -> None:
    """
    Check if the current time is 06:00 or 12:00.
    If it is, run the parseMonthlyScheduleForGroups function to update the database.
    """
    hour = int(datetime.today().strftime('%H'))
    if hour == 6 or hour == 12:
        logging.info(f"parsing Monthly Schedule For Groups, {hour = }")
        await parseMonthlyScheduleForGroups()

async def parseMonthlyScheduleForGroups() -> None:
    """
    Parse the schedule for all groups and update the 
        database if it's been more than an hour since the last update.
    """
    await asyncio.sleep(0.1)
            
    parser = RuzParser()
    for group_id in getAllGroupsList():
        if db.users.count_documents({"group_id": group_id}) <= 3:
            db.deleteMonthFromDB(group_id)
            continue
        # Get the last update time from the database
        lesson = lessons.find_one({"group_id": group_id})
        
        if lesson: 
            last_updated = lesson.get("last_update")
            total_seconds = (datetime.now() - last_updated).total_seconds()
        else:
            total_seconds = 36000
        
        # If the last update was more than an hour ago, update the database
        if total_seconds > 3600:
            # Parse the schedule for the group
            lessons_for_group = await parser.parseSchedule(group_id)          
            # Save the data to the database
            saveMonthLessonsToDB(group_id, lessons_for_group)
            # Wait a bit before parsing the next group
            await asyncio.sleep(20)
            
    return


async def timerPooling() -> None:
    """
    Main function for the timer pool. 
    It runs in an infinite loop and creates a new Timer every 60 seconds.
    The Timer calls the isParsingTime function after 60 seconds.

    The loop can be stopped with Ctrl+C.
    """
    polling = True
    logging.info("Timer started")
    try:
        while polling:
            # Create a new Timer that calls isParsingTime after 60 seconds
            timer = Timer(600, isParsingTime)
            # Wait 60 seconds before creating the next Timer
            await asyncio.sleep(600)
    except KeyboardInterrupt:
        # If the user stops the program with Ctrl+C, exit the loop
        return
    finally:
        # Stop the loop and exit the function
        polling = False
        return
    