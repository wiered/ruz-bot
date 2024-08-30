import calendar
import json
from datetime import datetime, timedelta
import logging

import aiohttp
import requests

GROUP_URL = "https://ruz.mstuca.ru/api/search?term={}&type=group"
LESSIONS_URL = "https://ruz.mstuca.ru/api/schedule/group/{}?start={}&finish={}&lng=1"


class RuzParser:
    """
    Class for parsing schedule from MSTUCA
    """
    def __init__(self):
        """
        Init class
        """
        pass
    
    async def fetch(self, client: aiohttp.ClientSession, url: str) -> dict:
        """
        Fetches JSON data from the given URL.
        
        Args:
            client: The aiohttp client session.
            url: The URL to fetch.
        
        Returns:
            The JSON data as a dictionary.
        """
        async with client.get(url) as resp:
            # Check if the request was successful
            assert resp.status == 200
            # Get the JSON data from the response
            return await resp.json(encoding="Windows-1251")
    
    async def parse(self, group, start_date, end_date):
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
            json = await self.fetch(session, LESSIONS_URL.format(group, start_date, end_date))
        
        return json

    
    async def parseDay(self, group, _timedelta = 0):
        """
        Parse schedule for group for one day
        
        Args:
            group (str): Group name
            _timedelta (int): Timedelta in days. Default is 0
        
        Returns:
            dict: Schedule in JSON format
        """
        _timedelta = int(_timedelta)
        coof = 1
        if _timedelta < 0:
            coof = -1
            _timedelta = abs(_timedelta)
            
        date = datetime.today() + (timedelta(days=_timedelta) * coof)
        date = date.strftime('%Y.%m.%d')
        return await self.parse(group, date, date)
    
    async def parseWeek(self, group, _timedelta: int = 0):
        """
        Parse schedule for group for one week
        
        Args:
            group (str): Group name
            _timedelta (int): Timedelta in weeks. Default is 0
        
        Returns:
            dict: Schedule in JSON format
        """
        logging.info(f'parseWeek: {group} {_timedelta}')
        
        date = datetime.today() + timedelta(days = _timedelta * 7)
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)
        
        start = start.strftime('%Y.%m.%d')
        end = end.strftime('%Y.%m.%d')
        
        logging.info(f'parseWeek: {start} {end}')
        return await self.parse(group, start, end)
    
    async def parseThisMonth(self, group):
        """
        Parse schedule for group for one week
        
        Args:
            group (str): Group name
            _timedelta (int): Timedelta in weeks. Default is 0
        
        Returns:
            dict: Schedule in JSON format
        """
        logging.info(f'parsing this month for group {group}')
        
        first_day_of_month = datetime.today().replace(day=1)
        last_day_of_month =first_day_of_month + timedelta(
            days=calendar.monthrange(first_day_of_month.year, first_day_of_month.month)[1] - 1
            )
        
        start = first_day_of_month.strftime('%Y.%m.%d')
        end = last_day_of_month.strftime('%Y.%m.%d')
        
        return await self.parse(group, start, end)
    
    async def search_group(self, group_name):
        """
        Search group in MSTUCA
        """
        async with aiohttp.ClientSession() as session:
            json = await self.fetch(session, GROUP_URL.format(group_name))
        
        return json
