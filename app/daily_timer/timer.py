import asyncio
import logging
import os
from datetime import datetime, timedelta

from dotenv import load_dotenv

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

load_dotenv()


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

    groups = db.getAllGroupsListFromMongo()
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

        # user_count = db.getUserCountByGroup(group)
        # logger.debug(f"Group {group} has {user_count} users")
        # if user_count <= 3:
        #     logger.info(f"Deleting schedule for group {group} because user count ({user_count}) ≤ 3")
        #     db.deleteScheduleFromDB(group)
        #     continue

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


async def timerPooling() -> None:
    """
    Main function for the timer pool.
    It schedules parseMonthlyScheduleForGroups once per day at the hour/minute specified
    in the .env as TIMER_HOUR and TIMER_MINUTE.
    """
    # Read desired hour and minute from environment
    try:
        hour = int(os.environ.get("TIMER_HOUR", "0"))
        minute = int(os.environ.get("TIMER_MINUTE", "0"))
        logger.debug(f"Loaded TIMER_HOUR={hour}, TIMER_MINUTE={minute} from .env")
    except ValueError:
        logger.error("Invalid TIMER_HOUR or TIMER_MINUTE in .env; defaulting to 0:0")
        hour, minute = 0, 0

    logger.info("timerPooling started")
    try:
        while True:
            now = datetime.now()
            # Determine next run time
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            sleep_seconds = (next_run - now).total_seconds()
            logger.info(f"Sleeping for {sleep_seconds:.0f} seconds until next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                logger.warning("timerPooling sleep canceled before scheduled run")
                break

            # Execute the parsing job
            logger.info(f"Running scheduled parse at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            try:
                await parseMonthlyScheduleForGroups()
            except Exception as e:
                logger.error(f"Error during scheduled parseMonthlyScheduleForGroups: {e}", exc_info=True)

            # After running, loop back to calculate the next_run for tomorrow
    except KeyboardInterrupt:
        logger.info("timerPooling stopped by KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Unexpected error in timerPooling: {e}", exc_info=True)
    finally:
        logger.info("timerPooling exiting")
