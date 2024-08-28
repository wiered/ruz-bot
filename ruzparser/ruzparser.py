import json
from datetime import datetime, timedelta

import aiohttp
import requests

lession_number = {
    "08:30": 1,
    "10:10": 2,
    "12:40": 3,
    "14:20": 4,
    "16:00": 5,
    "17:40": 6
}

week_days = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

class RuzParser:
    """
    Class for parsing schedule from MSTUCA
    """
    def __init__(self):
        """
        Init class
        """
        self.group_url = "https://ruz.mstuca.ru/api/search?term={}&type=group"
        self.lessions_url = "https://ruz.mstuca.ru/api/schedule/group/{}?start={}&finish={}&lng=1"
    
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
        print(f"Running parse for {group} from {start_date} to {end_date}")
        async with aiohttp.ClientSession() as session:
            r = await session.get(self.lessions_url.format(group, start_date, end_date))
            if r.status != 200:
                return {}
            r.encoding = "Windows-1251"
            print(f"Status code: {r.status}")
        
        return await r.json()

    
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
        print(f'parseWeek: {group} {_timedelta}')
        
        date = datetime.today() + timedelta(days = _timedelta * 7)
        start = date - timedelta(days=date.weekday())
        end = start + timedelta(days=6)
        
        start = start.strftime('%Y.%m.%d')
        end = end.strftime('%Y.%m.%d')
        
        print(f'parseWeek: {start} {end}')
        return await self.parse(group, start, end)
            
    def getLessions(self, data, _timedelta = 0):
        """
        Format schedule for group for one day
        
        Args:
            data (dict): Schedule in JSON format
            _timedelta (int): Timedelta in days. Default is 0
        
        Returns:
            str: Formatted schedule
        """
        date = datetime.today() + timedelta(days = _timedelta)
        week_day = week_days.get(date.weekday())
        date = date.strftime('%d.%m')
        
        lessions = ""
        for i in range(len(data)): 
            lessions += f"-- {lession_number.get(data[i].get('beginLesson'))} пара [{data[i].get('beginLesson')} - {data[i].get('endLesson')}] --" + '\n'
            lessions += data[i].get("discipline") + f" ({self.parseKindOfWork(data[i].get('kindOfWork'))})" + '\n'
            lessions += f"Аудитория: {data[i].get('auditorium').split('/')[1]}" + '\n'
            lessions += f"Преподаватель: {data[i].get('lecturer_title')}, {data[i].get('lecturer_rank')}" + '\n'
        
        if lessions == "":
            return f"= {date} = \n\nПар нет"
        
        return f"= {week_day} ({date}) = \n{lessions}"
    
    def getLessionsFromWeek(self, data):
        """
        Format schedule for group for one week
        
        Args:
            data (dict): Schedule in JSON format
        
        Returns:
            str: Formatted schedule
        """
        dates = {
        }
        for i in range(len(data)):
            datetime_object = datetime.strptime(data[i].get("date"), '%Y-%m-%d')
            week_day = week_days.get(datetime_object.weekday())
            dates.update(
                {data[i].get("date"): f"_= {week_day} ({'.'.join(data[i].get('date').split('-')[1:])}) =_ \n"}
                )
        
        for i in range(len(data)):
            tmp = dates.get(data[i].get("date"))
            tmp += f"*-- {lession_number.get(data[i].get('beginLesson'))} пара [{data[i].get('beginLesson')} - {data[i].get('endLesson')}] --*" + '\n  '
            tmp += data[i].get("discipline") + f" ({self.parseKindOfWork(data[i].get('kindOfWork'))})" + '\n  '
            tmp += f"Аудитория: {data[i].get('auditorium').split('/')[1]}" + '\n  '
            tmp += f"Преподаватель: {data[i].get('lecturer_title')}, {data[i].get('lecturer_rank')}" + '\n'
            
            dates.update({data[i].get("date"): tmp})
        
        # split this by "-": list(dates.keys())[0] and replace "-" with dost, then conver to string
        
        if len(list(dates.keys())) == 0:
            return "Пар нет"
        
        lessions = "== Расписание на неделю {} - {} == \n\n".format(
            ".".join(list(dates.keys())[0].split('-'))[5:], 
            ".".join(list(dates.keys())[-1].split('-'))[5:]
            )
        for key in dates.keys():
            lessions += dates.get(key) + "\n"
        
        replacables = ['.', '-', '(', ')', "="]
        for ch in replacables:            
            lessions = lessions.replace(ch, f"\\{ch}")
        
        return lessions
    
    async def search_group(self, group_name):
        """
        Search group in MSTUCA
        """
        async with aiohttp.ClientSession() as session:
            r = await session.get(self.group_url.format(group_name))
            r.encoding = "Windows-1251"
        
        return await r.json()
    
    @staticmethod
    def parseKindOfWork(kindOfWork):
        """
        Parse kind of work
        """
        if kindOfWork == "Лекция":
            return "Лек."
        if kindOfWork == "Практические (семинарские) занятия":
            return "Пр. зан."
        
        return kindOfWork
    
        
# parser = RuzParser()
# parser.parseDate("2024.09.03")
# parser.printLessions()
