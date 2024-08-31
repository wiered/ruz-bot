import os

from datetime import datetime, timedelta, date, time
from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGODB_ADRESS'), connect=True)
db = client.ruzbotdb
users = db.users
lessons = db.lessons

def getStartEndOfDay(target_date: date):
    start_of_day = datetime.combine(target_date, time.min)
    end_of_day = datetime.combine(target_date, time.max)
    return start_of_day, end_of_day

def getStartAndEndOfWeek(reference_date: datetime):
    # Start of the week (Monday)
    start_of_week = reference_date - timedelta(days=reference_date.weekday())
    # End of the week (Sunday)
    _, end_of_week = getStartEndOfDay(start_of_week + timedelta(days=5))
    
    start_of_week, _ = getStartEndOfDay(start_of_week)
    return start_of_week, end_of_week

def getPreviousAndNextMonthBounds(reference_date: datetime):
    # Step 1: Start of the previous month
    first_day_of_current_month = reference_date.replace(day=1)
    start_of_previous_month = first_day_of_current_month - timedelta(days=1)
    start_of_previous_month, _= getStartEndOfDay(start_of_previous_month.replace(day=1))

    # Step 2: End of the next month
    first_day_of_next_next_month = (first_day_of_current_month + timedelta(days=31)).replace(day=1)
    end_of_next_month = (first_day_of_next_next_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    _, end_of_next_month = getStartEndOfDay(end_of_next_month)

    return start_of_previous_month, end_of_next_month

def saveMonthLessonsToDB(group_id, lessons_for_this_month):
    if lessons.count_documents({"group_id": group_id}) > 0:
        lessons.delete_one({"group_id": group_id})
    
    lessons.insert_one({
        "group_id": group_id,
        "last_update": datetime.now(),
        "lessons": lessons_for_this_month
    })
        
def getAllGroupsList():
    return users.distinct("group_id")

def isGroupChached(group_id):
    if lessons.find_one({"group_id": group_id}):
        return True
    
    return False

def isDayChached(group_id, date):
    if not isGroupChached(group_id):
        return False
    
    reference_date = datetime.now()
    start_of_previous_month, end_of_next_month = getPreviousAndNextMonthBounds(reference_date)
    if (date - start_of_previous_month).total_seconds() < 0:
        return False
    
    if (end_of_next_month - date).total_seconds() < 0:
        return False
    
    return True
    
def isWeekChached(group_id, start, end):
    if not isGroupChached(group_id):
        return False
    
    reference_date = datetime.now()
    start_of_previous_month, end_of_next_month = getPreviousAndNextMonthBounds(reference_date)
    if (start - start_of_previous_month).total_seconds() < 0:
        return False
    
    if (end_of_next_month - end).total_seconds() < 0:
        return False
    
    return True

def getDay(group_id, _timedelta):
    date, _ = getStartEndOfDay(datetime.now() + timedelta(days=_timedelta))
    if not isDayChached(group_id, date):
        raise ValueError
    
    i = 0
    day_lessons = []
    group_lessons = lessons.find_one({"group_id": group_id}).get("lessons")
    for lesson in group_lessons:
        if (date - lesson.get("date")).total_seconds() > 0:
            pass
        elif (lesson.get("date") - date).total_seconds() > 86300:
            break
        else:
            day_lessons.append(lesson)
            
    return day_lessons   

def getWeek(group_id, _timedelta):
    start, end = getStartAndEndOfWeek(datetime.now() + timedelta(days=_timedelta * 7))
    if not isWeekChached(group_id, start, end):
        raise ValueError
    
    i = 0
    week_lessons = []
    group_lessons = lessons.find_one({"group_id": group_id}).get("lessons")
    for lesson in group_lessons:
        if (start - lesson.get("date")).total_seconds() > 0:
            pass
        elif (lesson.get("date") - end).total_seconds() > 86300:
            break
        else:
            week_lessons.append(lesson)
            
    return week_lessons

