import asyncio
import calendar
import logging
from datetime import datetime, timedelta
from typing import List
import calendar

import aiohttp
import requests

import db

logger = logging.getLogger(__name__)
if not logger.hasHandlers():
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
logger.propagate = False

GROUP_URL = "https://ruz.mstuca.ru/api/search?term={}&type=group"
LESSONS_URL = "https://ruz.mstuca.ru/api/schedule/group/{}?start={}&finish={}&lng=1"


class RuzParser:
    """
    Class for parsing schedule from MSTUCA
    """

    async def fetch(self, client: aiohttp.ClientSession, url: str, ssl=True) -> dict:
        """
        Fetches JSON data from the given URL.

        Args:
            client (aiohttp.ClientSession): The aiohttp client session.
            url (str): The URL to fetch.

        Returns:
            dict: The JSON data as a dictionary.
        """
        max_retries = 5
        backoff = 1  # initial backoff in seconds

        for attempt in range(1, max_retries + 1):
            logger.debug(f"[Attempt {attempt}] Fetching URL: {url}")
            async with client.get(url=url, ssl=ssl) as resp:
                status = resp.status

                if status == 200:
                    data = await resp.json(encoding="Windows-1251")
                    logger.debug(f"Successfully received data ({len(str(data))} bytes) from {url}")
                    return data

                if status == 429:
                    retry_after = resp.headers.get("Retry-After")
                    if retry_after is not None and retry_after.isdigit():
                        delay = int(retry_after)
                        logger.warning(f"Received 429, Retry-After={delay}s; sleeping {delay}s")
                        await asyncio.sleep(delay)
                    else:
                        logger.warning(f"Received 429 without Retry-After; sleeping {backoff}s")
                        await asyncio.sleep(backoff)
                        backoff *= 2
                    continue  # retry loop

                logger.error(f"Failed to fetch {url}: HTTP {status}")
                resp.raise_for_status()

        raise aiohttp.ClientError(f"Exceeded {max_retries} retries for URL: {url}")

    async def parse(self, group: str, start_date: str, end_date: str) -> dict:
        """
        Parse schedule for group from start_date to end_date

        Args:
            group (str): Group name
            start_date (str): Start date in format %Y.%m.%d
            end_date (str): End date in format %Y.%m.%d

        Returns:
            dict: Schedule in JSON format
        """
        logger.info(f"Running parse for group={group}, start={start_date}, end={end_date}")
        async with aiohttp.ClientSession() as session:
            json_data = await self.fetch(
                session, LESSONS_URL.format(group, start_date, end_date), ssl=False
            )
        logger.debug(f"parse returned {len(json_data)} entries for group={group}")
        return json_data

    async def parseDay(self, group: str, date: datetime) -> dict:
        """
        Parse schedule for group for one day

        Args:
            group (str): Group name
            date (datetime): date

        Returns:
            dict: Schedule in JSON format
        """
        date_str = date.strftime("%Y.%m.%d")
        logger.info(f"parseDay called for group={group}, date={date_str}")
        result = await self.parse(group, date_str, date_str)
        logger.debug(f"parseDay returned {len(result)} lessons for {group} on {date_str}")
        return result

    async def parseWeek(self, group: str, date: datetime) -> List[dict]:
        """
        Parse schedule for group for one week

        Args:
            group (str): Group name
            date (datetime): date

        Returns:
            List[dict]: Schedule in JSON format
        """
        logger.info(f"parseWeek called for group={group}, base_date={date.date()}")
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)

        start_str = start.strftime("%Y.%m.%d")
        end_str = end.strftime("%Y.%m.%d")

        logger.debug(f"Week range for {group}: {start_str} - {end_str}")
        result = await self.parse(group, start_str, end_str)
        logger.debug(f"parseWeek returned {len(result)} lessons for {group} week starting {start_str}")
        return result

    async def parseSchedule(self, group_id: str) -> List[dict]:
        """
        Parse schedule for group for one month

        Args:
            group_id (str): Group id

        Returns:
            List[dict]: Schedule in JSON format
        """
        logger.info(f"parseSchedule called for group={group_id}")

        first_this_month = datetime.today().replace(day=1)
        first_prev_month = (first_this_month - timedelta(days=2)).replace(day=1)

        last_day_this_month = calendar.monthrange(
            first_this_month.year, first_this_month.month
        )[1]
        last_this_month = first_this_month + timedelta(days=last_day_this_month - 1)

        first_next_month = (last_this_month + timedelta(days=2)).replace(day=1)
        last_day_next_month = calendar.monthrange(
            first_next_month.year, first_next_month.month
        )[1]
        last_next_month = first_next_month + timedelta(days=last_day_next_month - 1)

        start_str = first_prev_month.strftime("%Y.%m.%d")
        end_str = last_next_month.strftime("%Y.%m.%d")
        update_time = datetime.now().isoformat()

        logger.debug(
            f"Month bounds for {group_id}: start={start_str}, end={end_str}, update_time={update_time}"
            )
        raw = await self.parse(group_id, start_str, end_str)

        processed = []
        for lesson in raw:
            subgroup = 0
            list_sub = lesson.get("listSubGroups", [])
            if list_sub:
                subgroup = int(list_sub[0].get("subgroup")[-1])

            lesson["group_id"] = group_id
            lesson["subgroup"] = subgroup
            lesson["update_time"] = update_time
            processed.append(lesson)

        if not processed:
            logger.warning(f"No lessons returned for group {group_id}")
        else:
            logger.info(f"parseSchedule completed with {len(processed)} lessons for {group_id}")

        return processed


    async def search_group(self, group_name: str) -> List[dict]:
        """
        Search group in MSTUCA

        Args:
            group_name (str): Group name

        Returns:
            List[dict]: List of groups
        """
        logger.info(f"search_group called for name={group_name!r}")
        async with aiohttp.ClientSession() as session:
            json_data = await self.fetch(
                session, GROUP_URL.format(group_name), ssl=False
            )
        logger.debug(f"search_group returned {len(json_data)} results for {group_name!r}")
        return json_data


async def main():
    parser = RuzParser()
    print(await parser.search_group('ИС2'))
    print(await parser.parseWeek('625', datetime.now()))

if __name__ == '__main__':
    asyncio.run(main())
