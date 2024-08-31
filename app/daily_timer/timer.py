import asyncio
from datetime import datetime
import logging

from db import getAllGroupsList, saveMonthLessonsToDB, lessons
from ruzparser import RuzParser

class Timer:
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
        self._task.cancel()

async def isParsingTime():
    hour = int(datetime.today().strftime('%H'))
    if hour == 12 or hour == 16:
        await parseMonthlyScheduleForGroups()

async def parseMonthlyScheduleForGroups():
    await asyncio.sleep(0.1)
            
    parser = RuzParser()
    for group in getAllGroupsList():
        last_updated = lessons.find_one({"group_id": group}).get("last_update")
        if (datetime.now() - last_updated).total_seconds() < 3600:
            return
        
        lessons_for_group = await parser.parseSchedule(group)
        print(type(lessons_for_group))
        saveMonthLessonsToDB(group, lessons_for_group)
            
    return

async def timerPooling():
    polling = True
    try:
        while polling:
            timer = Timer(60, isParsingTime)
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        return
    finally:
        polling = False
        return
    