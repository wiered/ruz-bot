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


async def parseMonthlyScheduleForGroups() -> None:
    """
    Parse schedules for all groups in parallel (with a limit on concurrent workers).
    """
    logger.info("parseMonthlyScheduleForGroups started: Updating schedules for all groups")
    await asyncio.sleep(0.1)

    parser = RuzParser()

    groups = db.getAllGroupsListFromMongo()
    groups_count = len(groups)
    logger.debug(f"Found {groups_count} groups to check")

    max_concurrent_tasks = int(os.environ.get("MAX_WORKERS", "5"))
    logger.info(f"Limiting to {max_concurrent_tasks} concurrent workers")
    sem = asyncio.Semaphore(max_concurrent_tasks)

    async def worker(group_id: str):
        """
        Worker task that fetches and saves schedule for a single group.
        """
        async with sem:
            logger.debug(f"Starting parse for group {group_id}")
            try:
                last_update = db.getGroupLastUpdateTime(group_id)
                elapsed = (datetime.now() - last_update).total_seconds()
                logger.debug(f"Group {group_id}: last update was {elapsed:.0f} seconds ago")

                if elapsed < 3600:
                    logger.info(
                        f"Skipping {group_id}: last update was {elapsed/60:.1f} minutes ago"
                    )
                    return

                logger.info(f"Parsing schedule for group {group_id}")
                lessons = await parser.parseSchedule(group_id)
                if lessons:
                    db.saveScheduleToDB(group_id, lessons)
                    logger.info(f"Saved {len(lessons)} lessons for {group_id} to database")
                else:
                    logger.warning(f"No lessons returned for group {group_id}")
            except Exception as exc:
                logger.error(f"Error parsing group {group_id}: {exc}", exc_info=True)

    tasks = [asyncio.create_task(worker(g)) for g in groups]
    await asyncio.gather(*tasks)

    logger.info("parseMonthlyScheduleForGroups: All groups processed")


async def timerPooling() -> None:
    """
    Main loop that runs parseMonthlyScheduleForGroups once per day at TIMER_HOUR:TIMER_MINUTE.
    """
    try:
        hour = int(os.environ.get("TIMER_HOUR", "0"))
        minute = int(os.environ.get("TIMER_MINUTE", "0"))
        logger.debug(f"Loaded TIMER_HOUR={hour}, TIMER_MINUTE={minute} from .env")
    except ValueError:
        logger.error("Invalid TIMER_HOUR or TIMER_MINUTE in .env; defaulting to 00:00")
        hour, minute = 0, 0

    logger.info("timerPooling started")
    try:
        while True:
            now = datetime.now()
            next_run = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            sleep_seconds = (next_run - now).total_seconds()
            logger.info(
                f"Sleeping for {sleep_seconds:.0f} seconds until next run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            try:
                await asyncio.sleep(sleep_seconds)
            except asyncio.CancelledError:
                logger.warning("timerPooling sleep canceled before scheduled run")
                break

            logger.info(f"Running scheduled parse at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            try:
                await parseMonthlyScheduleForGroups()
            except Exception as e:
                logger.error(f"Error during scheduled parseMonthlyScheduleForGroups: {e}", exc_info=True)

    except KeyboardInterrupt:
        logger.info("timerPooling stopped by KeyboardInterrupt")
    except Exception as e:
        logger.error(f"Unexpected error in timerPooling: {e}", exc_info=True)
    finally:
        logger.info("timerPooling exiting")
