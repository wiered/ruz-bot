import asyncio
import logging
from datetime import datetime, timedelta

from db import db
from ruzparser import RuzParser

# --------------------
# Logging Configuration
# --------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

logger.propagate = False


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
        logger.debug(f"Timer initialized with timeout={timeout} seconds, callback={callback.__name__}")
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        """
        Wait for the timeout and call the callback.
        """
        logger.info(f"Timer sleeping for {self._timeout} seconds before executing callback")
        await asyncio.sleep(self._timeout)
        logger.info(f"Timer executing callback {self._callback.__name__}")
        try:
            await self._callback()
            logger.info(f"Callback {self._callback.__name__} completed successfully")
        except Exception as e:
            logger.error(f"Error in callback {self._callback.__name__}: {e}", exc_info=True)

    def cancel(self):
        """
        Cancel the timer and stop the callback from being called.
        """
        self._task.cancel()
        logger.info("Timer canceled")


async def parseMonthlyScheduleForGroups() -> None:
    """
    Parse the schedule for all groups and update the
    database if it's been more than an hour since the last update.
    """
    logger.info("parseMonthlyScheduleForGroups started: Updating schedules for all groups")
    await asyncio.sleep(0.1)

    parser = RuzParser()

    groups = db.getAllGroupsList()
    groups_count = len(groups)
    logger.debug(f"Found {groups_count} groups to check")

    for num, group in enumerate(groups, start=1):
        logger.debug(f"Processing group {group} ({num}/{groups_count})")
        last_update = db.getGroupLastUpdateTime(group)
        elapsed = (datetime.now() - last_update).total_seconds()
        logger.debug(f"Group {group} last update at {last_update} ({elapsed:.0f} seconds ago)")

        if elapsed < 3600:
            logger.info(f"Skipping group {group}: last update was {elapsed/60:.1f} minutes ago")
            continue

        user_count = db.getUserCountByGroup(group)
        logger.debug(f"Group {group} has {user_count} users")
        if user_count <= 3:
            logger.info(f"Deleting schedule for group {group} because user count ({user_count}) ≤ 3")
            db.deleteScheduleFromDB(group)
            continue

        logger.info(f"Parsing schedule for group {group} ({num}/{groups_count})")
        try:
            lessons_for_group = await parser.parseSchedule(group)
            logger.debug(f"Fetched {len(lessons_for_group)} lessons from parser for group {group}")
            db.saveScheduleToDB(group, lessons_for_group)
            logger.info(f"Saved schedule for group {group} to database")
        except Exception as e:
            logger.error(f"Error parsing schedule for group {group}: {e}", exc_info=True)

        logger.debug("Sleeping 20 seconds before next group")
        await asyncio.sleep(20)

    logger.info("parseMonthlyScheduleForGroups completed")


async def sleepUntilMidnight() -> None:
    """
    Sleep until the next midnight.
    """
    nowtime = datetime.now()
    tomorrow = (nowtime + timedelta(days=1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    seconds_until_midnight = (tomorrow - nowtime).total_seconds()
    logger.info(f"Sleeping for {seconds_until_midnight:.2f} seconds until midnight ({tomorrow})")
    try:
        await asyncio.sleep(seconds_until_midnight)
    except asyncio.CancelledError:
        logger.warning("sleepUntilMidnight was cancelled")
        raise


async def timerPooling() -> None:
    """
    Main function for the timer pool.
    It runs in an infinite loop and creates a new Timer every 60 seconds
    to call parseMonthlyScheduleForGroups.
    """
    logger.info("timerPooling started")
    try:
        await sleepUntilMidnight()

        while True:
            logger.debug("Woke up at midnight; scheduling parseMonthlyScheduleForGroups in 60 seconds")
            timer = Timer(60, parseMonthlyScheduleForGroups)

            logger.debug("Sleeping 60 seconds before scheduling next Timer")
            try:
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                logger.warning("timerPooling sleep canceled")
                break

            # After one minute, loop back to sleepUntilMidnight
            logger.debug("Loop iteration complete; sleeping until next midnight")
            await sleepUntilMidnight()

    except KeyboardInterrupt:
        logger.info("timerPooling stopped by KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Unexpected error in timerPooling: {e}", exc_info=True)
    finally:
        logger.info("timerPooling exiting")
