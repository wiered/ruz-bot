import os

from datetime import datetime, timedelta, date, time
from typing import List
from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGODB_ADRESS'), connect=True)
db = client.ruzbotdb
users = db.users
lessons = db.lessons

def getStartEndOfDay(target_date: date) -> tuple:
    """
    Returns the start and end of the day relative to the given target date.

    Args:
        target_date (date): The target date

    Returns:
        tuple: A tuple containing the start and end of the day
    """
    # Get the start of the day
    start_of_day = datetime.combine(target_date, time.min)
    
    # Get the end of the day
    end_of_day = datetime.combine(target_date, time.max)
    
    # Return the start and end of the day
    return start_of_day, end_of_day


def getStartAndEndOfWeek(reference_date: datetime) -> tuple:
    """
    Returns the start and end of the week relative to the given reference date.

    Args:
        reference_date (datetime): The reference date

    Returns:
        tuple: A tuple containing the start and end of the week
    """
    # Start of the week (Monday)
    start_of_week = reference_date - timedelta(days=reference_date.weekday())
    # End of the week (Sunday)
    _, end_of_week = getStartEndOfDay(start_of_week + timedelta(days=5))
    
    # Get the start of the day of the first day of the week
    start_of_week, _ = getStartEndOfDay(start_of_week)
    return start_of_week, end_of_week


def getPreviousAndNextMonthBounds(reference_date: datetime):
    """
    Returns the start of the previous month and the end of the next month
    relative to the given reference date.

    Args:
        reference_date (datetime): The reference date

    Returns:
        tuple: A tuple containing the start of the previous month and the end of the next month
    """
    # Step 1: Start of the previous month
    first_day_of_current_month = reference_date.replace(day=1)
    start_of_previous_month = first_day_of_current_month - timedelta(days=1)
    # Get the start of the day of the first day of the previous month
    start_of_previous_month, _ = getStartEndOfDay(start_of_previous_month.replace(day=1))

    # Step 2: End of the next month
    first_day_of_next_next_month = (first_day_of_current_month + timedelta(days=31)).replace(day=1)
    end_of_next_month = (first_day_of_next_next_month + timedelta(days=31)).replace(day=1) - timedelta(days=1)
    # Get the end of the day of the last day of the next month
    _, end_of_next_month = getStartEndOfDay(end_of_next_month)

    return start_of_previous_month, end_of_next_month


def saveMonthLessonsToDB(group_id: str, lessons_for_this_month: List[dict]):
    """
    Save the lessons for the given group to the database
    
    Args:
        group_id (str): The id of the group
        lessons_for_this_month (List[dict]): The lessons for the given group
    """
    # If the group is already cached, delete the old entry
    if lessons.count_documents({"group_id": group_id}) > 0:
        lessons.delete_one({"group_id": group_id})
    
    # Insert the new entry into the database
    lessons.insert_one({
        "group_id": group_id,
        "last_update": datetime.now(),
        "lessons": lessons_for_this_month
    })
    
        
def getAllGroupsList() -> List[str]:
    """
    Get a list of all the groups cached in the database
    
    Returns:
        List[str]: A list of group ids
    """
    # Get all the groups from the users collection
    return users.distinct("group_id")


def isGroupChached(group_id: str) -> bool:
    """
    Check if the group is cached in the database
    
    Args:
        group_id (str): Group id
    
    Returns:
        bool: True if the group is cached in the database, otherwise False
    """
    # If group exists in database, then it is cached
    if lessons.find_one({"group_id": group_id}):
        return True
    
    # If the group is not found, it is not cached
    return False


def isDayChached(group_id, date: datetime) -> bool:
    """
    Check if the day is cached in the database
    
    Args:
        group_id (str): Group id
        date (datetime): Date
    
    Returns:
        bool: True if the day is cached in the database, otherwise False
    """
    # If the group is not cached, the day is not cached
    # If group is not chached, the day is not cached
    if not isGroupChached(group_id):
        return False
    
    # Get the bounds of the previous and next month
    reference_date = datetime.now()
    start_of_previous_month, end_of_next_month = getPreviousAndNextMonthBounds(reference_date)
    
    # Check if the date is before the start of the previous month
    if (date - start_of_previous_month).total_seconds() < 0:
        # If it is, the day is not cached
        return False
    
    # Check if the date is after the end of the next month
    if (end_of_next_month - date).total_seconds() < 0:
        # If it is, the day is not cached
        return False
    
    # If the date is between the start of the previous month and the end of the next month
    # and the group is cached, then the day is cached
    return True
    
def isWeekChached(group_id, date):
    """
    Check if the week is cached in the database
    
    Args:
        group_id (str): Group id
        date (datetime): Date
    
    Returns:
        bool: True if the week is cached in the database, otherwise False
    """
    start, end = getStartAndEndOfWeek(date)
    if not isGroupChached(group_id):
        # If the group is not cached, the week is not cached
        return False
    
    reference_date = datetime.now()
    start_of_previous_month, end_of_next_month = getPreviousAndNextMonthBounds(reference_date)
    
    # Check if the week is before the start of the previous month
    if (start - start_of_previous_month).total_seconds() < 0:
        # If it is, the week is not cached
        return False
    
    # Check if the week is after the end of the next month
    if (end_of_next_month - end).total_seconds() < 0:
        # If it is, the week is not cached
        return False
    
    # If the week is between the start of the previous month and the end of the next month
    # and the group is cached, then the week is cached
    return True


def getDay(group_id, date: datetime) -> List[dict]:
    """
    Get all lessons for one day for given group and date
    
    Args:
        group_id (str): Group id
        date (datetime): Date
    
    Returns:
        List[dict]: Lessons in JSON format
    """
    date, _ = getStartEndOfDay(date)
    
    # Check if the day is cached
    if not isDayChached(group_id, date):
        raise ValueError
    
    # Get all lessons for the group
    group_lessons = lessons.find_one({"group_id": group_id}).get("lessons")
    
    # Initialize the list of lessons for the day
    day_lessons = []
    
    # Iterate over all lessons and select only those that are on the given day
    for lesson in group_lessons:
        # Check if the lesson is before the start of the day
        if (date - lesson.get("date")).total_seconds() > 0:
            pass
        # Check if the lesson is after the end of the day
        elif (lesson.get("date") - date).total_seconds() > 86300:
            break
        # If the lesson is on the given day, add it to the list
        else:
            day_lessons.append(lesson)
            
    return day_lessons   


def getWeek(group_id, date: datetime):
    """
    Get all lessons for a week for given group and date
    
    Args:
        group_id (str): Group id
        date (datetime): Date
    
    Returns:
        List[dict]: List of lessons in JSON format
    """
    start, end = getStartAndEndOfWeek(date)
    
    # Check if the week is cached
    if not isWeekChached(group_id, date):
        raise ValueError
    
    i = 0
    week_lessons = []
    
    # Get all lessons for the group
    group_lessons = lessons.find_one({"group_id": group_id}).get("lessons")
    
    # Iterate over all lessons and select only those that are in the given week
    for lesson in group_lessons:
        # Check if the lesson is before the start of the week
        if (start - lesson.get("date")).total_seconds() > 0:
            pass
        # Check if the lesson is after the end of the week
        elif (lesson.get("date") - end).total_seconds() > 86300:
            break
        # If the lesson is in the given week, add it to the list
        else:
            week_lessons.append(lesson)
            
    return week_lessons
