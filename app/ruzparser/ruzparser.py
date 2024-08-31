import calendar
import json
import logging
from datetime import datetime, timedelta
from typing import List

import aiohttp
import requests

import db

GROUP_URL = "https://ruz.mstuca.ru/api/search?term={}&type=group"
LESSONS_URL = "https://ruz.mstuca.ru/api/schedule/group/{}?start={}&finish={}&lng=1"


class RuzParser:
    """
    Class for parsing schedule from MSTUCA
    """
    async def fetch(self, client: aiohttp.ClientSession, url: str) -> dict:
        """
        Fetches JSON data from the given URL.

        Args:
            client (aiohttp.ClientSession): The aiohttp client session.
            url (str): The URL to fetch.

        Returns:
            dict: The JSON data as a dictionary.
        """
        async with client.get(url) as resp:
            # Check if the request was successful
            assert resp.status == 200
            # Get the JSON data from the response
            return await resp.json(encoding="Windows-1251")
    
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
        logging.info(f"Running parse for {group} from {start_date} to {end_date}")
        async with aiohttp.ClientSession() as session:
            json: dict = await self.fetch(session, LESSONS_URL.format(group, start_date, end_date))
        
        return json
    
    async def parseDay(self, group: str, date: datetime) -> dict:
        """
        Parse schedule for group for one day
        
        Args:
            group (str): Group name
            date (date): date
        
        Returns:
            dict: Schedule in JSON format
        """
            
        date = date.strftime('%Y.%m.%d')
        return await self.parse(group, date, date)
    
    async def parseWeek(self, group: str, date: datetime) -> List[dict]:
        """
        Parse schedule for group for one week
        
        Args:
            group (str): Group name
            date (datetime): date
        
        Returns:
            List[dict]: Schedule in JSON format
        """
        logging.info(f'parseWeek: {group} {date}')
        
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)
        
        start = start.strftime('%Y.%m.%d')
        end = end.strftime('%Y.%m.%d')
        
        logging.info(f'parsing week {start} - {end}')
        return await self.parse(group, start, end)
    
    async def parseSchedule(self, group_id: str) -> List[dict]:
        """
        Parse schedule for group for one month
        
        Args:
            group_id (str): Group id
        
        Returns:
            List[dict]: Schedule in JSON format
        """
        logging.info(f'parsing this month for group {group_id}')
        
        first_date_of_this_month = datetime.today().replace(day=1)
        first_date_of_previous_month = (first_date_of_this_month - timedelta(days=2)).replace(day=1)
        
        last_day_of_this_month: int = calendar.monthrange(first_date_of_this_month.year, first_date_of_this_month.month)[1]
        last_date_of_this_month: datetime = first_date_of_this_month + timedelta(days = last_day_of_this_month - 1)
        
        first_date_of_next_month: datetime = (last_date_of_this_month + timedelta(days=2)).replace(day=1)
        last_day_of_next_month: int = calendar.monthrange(first_date_of_next_month.year, first_date_of_next_month.month)[1]
        last_date_of_next_month: datetime = first_date_of_next_month + timedelta(days = last_day_of_next_month - 1)
        
        start = first_date_of_previous_month.strftime('%Y.%m.%d')
        end = last_date_of_next_month.strftime('%Y.%m.%d')
        
        lessons_for_this_month: List[dict] = await self.parse(group_id, start, end)
        for lesson in lessons_for_this_month:
            date = datetime.strptime(lesson.get("date"), "%Y-%m-%d")
            lesson.update({"date": date})
            
        if len(lessons_for_this_month) < 1:
            return []
        
        return lessons_for_this_month
    
    async def search_group(self, group_name: str) -> List[dict]:
        """
        Search group in MSTUCA

        Args:
            group_name (str): Group name

        Returns:
            List[dict]: List of groups
        """
        async with aiohttp.ClientSession() as session:
            json = await self.fetch(session, GROUP_URL.format(group_name))
        
        return json
    