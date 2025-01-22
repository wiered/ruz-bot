import asyncio
from datetime import datetime, timedelta
import logging

from db import db
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

    logging.info(f"parsing Monthly Schedule For Groups")
    await parseMonthlyScheduleForGroups()

async def parseMonthlyScheduleForGroups() -> None:
    """
    Parse the schedule for all groups and update the
        database if it's been more than an hour since the last update.
    """
    logging.info("Updating schedules")
    await asyncio.sleep(0.1)

    # Create parser object
    parser = RuzParser()

    # get all groups from database
    groups = db.getAllGroupsList()
    groups_count = len(groups)

    for num, group in enumerate(groups):
        # Get the last update time from the database
        last_update = db.getGroupLastUpdateTime(group)

        # If group schedule is updated less than a hour ago, skip updating
        if (datetime.now() - last_update).seconds < 3600:
            continue

        # If the group has less than 3 users, delete the schedule
        if db.getUserCountByGroup(group) <= 3:
            db.deleteScheduleFromDB(group)
            continue

        logging.info(f"Parsing... {group} ({num+1}/{groups_count})")
        lessons_for_group = await parser.parseSchedule(group)
        db.saveScheduleToDB(group, lessons_for_group)
        await asyncio.sleep(20)

    return

async def sleepUntilMidnight() -> None:
    nowtime = datetime.now()
    tomorrow = (nowtime + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
        )
    seconds_until_midnight = (tomorrow - nowtime).total_seconds()
    print(f"Sleeping for {seconds_until_midnight:.2f} seconds until midnight...")
    await asyncio.sleep(seconds_until_midnight)

async def timerPooling() -> None:
    """
    Main function for the timer pool.
    It runs in an infinite loop and creates a new Timer every 60 seconds.
    The Timer calls the isParsingTime function after 60 seconds.

    The loop can be stopped with Ctrl+C.
    """
    polling = True
    print("Timer started")
    logging.info("Timer started")
    try:
        await sleepUntilMidnight()

        while polling:
            # Waiting until midnight
            await sleepUntilMidnight()

            # Create a new Timer that calls isParsingTime after 60 seconds
            timer = Timer(60, isParsingTime)

            # Sleeping 60 seconds for no reason
            await asyncio.sleep(60)

    except KeyboardInterrupt:
        # If the user stops the program with Ctrl+C, exit the loop
        return
    finally:
        # Stop the loop and exit the function
        polling = False
        return
