import asyncio
from datetime import datetime
import logging

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
    print(f"{hour = }, {type(hour) = }")
    print(f"{hour == 18 = }")
    if hour == 18 or hour == 19:
        logging.info(f"parsing Monthly Schedule For Groups, {hour = }")
        print("parsing Monthly Schedule For Groups, ")
        await parseMonthlyScheduleForGroups()

async def parseMonthlyScheduleForGroups() -> None:
    """
    Parse the schedule for all groups and update the 
        database if it's been more than an hour since the last update.
    """
    await asyncio.sleep(0.1)
            
    parser = RuzParser()
    for group in getAllGroupsList():
        print(f"{group = }")
        # Get the last update time from the database
        last_updated = lessons.find_one({"group_id": group}).get("last_update")
        last_updated_human = datetime.strftime(last_updated, "%d.%m %H:%M:%S")
        total_seconds = (datetime.now() - last_updated).total_seconds()
        print(f"{last_updated_human = }")
        print(f"{total_seconds = }, {type(total_seconds) = }")
        
        # If the last update was more than an hour ago, update the database
        if total_seconds > 3600:
            # Parse the schedule for the group
            lessons_for_group = await parser.parseSchedule(group)
            print(f"{len(lessons_for_group) = }")
            # Save the data to the database
            saveMonthLessonsToDB(group, lessons_for_group)
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
            timer = Timer(5, isParsingTime)
            # Wait 60 seconds before creating the next Timer
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        # If the user stops the program with Ctrl+C, exit the loop
        return
    finally:
        # Stop the loop and exit the function
        polling = False
        return
    