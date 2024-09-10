import os

from datetime import datetime
from typing import List
from pymongo import MongoClient

import utils

class DataBase():
    def __init__(self):
        self._client = MongoClient(os.environ.get('MONGODB_ADRESS'), connect=True)
        self._db = self._client.ruzbotdb
        self._users = self._db.users
        self._lessons = self._db.lessons
        
    @property
    def client(self):
        return self._client
    
    @property
    def db(self):
        return self._db
    
    @property
    def users(self):
        return self._users
    
    @property
    def lessons(self):
        return self._lessons
    
    def isUserKnown(self, user_id):
        if self.users.find_one({"id":user_id}):
            return True
        
        return False
    
    def isUserHasSubGroup(self, user_id: int) -> bool:
        """
        Checks if a user has a subgroup in the database.

        Args:
            user_id (int): The ID of the user to check.

        Returns:
            bool: True if the user has a subgroup, False otherwise.
        """
        
        # If found user with user_id and no subgroup then False
        if self.users.find_one(
            {"id":user_id, "sub_group": {"$exists": False}}
            ):
            return True
        
        # Else True
        return True
    
    def isGroupInDB(self, group_id: str) -> bool:
        """
        Check if the group is cached in the database
        
        Args:
            group_id (str): Group id
        
        Returns:
            bool: True if the group is cached in the database, otherwise False
        """
        # If group exists in database, then it is cached
        if self.lessons.find_one({"group_id": group_id}):
            return True
        
        # If the group is not found, it is not cached
        return False
    
    def isDateRangeInDB(self, group_id: str, start: datetime, end: datetime) -> bool:
        # If the group is not cached, the day is not cached
        # If group is not chached, the day is not cached
        if not self.isGroupInDB(group_id):
            return False
        
        # Get the bounds of the previous and next month
        reference_date = datetime.now()
        start_of_previous_month, end_of_next_month = utils.getPreviousAndNextMonthBounds(reference_date)
        
        # Check if the start of range is before the start of the previous month
        if (start - start_of_previous_month).total_seconds() < 0:
            # If it is, the range is not cached
            return False
        
        # Check if the end of range is after the end of the next month
        if (end_of_next_month - end).total_seconds() < 0:
            # If it is, the range is not cached
            return False
        
        # If the date is between the start of the previous month and the end of the next month
        # and the group is cached, then the day is cached
        return True
    
    def isDayInDB(self, group_id, date: datetime) -> bool:
        """
        Check if the day is cached in the database
        
        Args:
            group_id (str): Group id
            date (datetime): Date
        
        Returns:
            bool: True if the day is cached in the database, otherwise False
        """
        return self.isDateRangeInDB(group_id, date, date)
        
    def isWeekInDB(self, group_id, date):
        """
        Check if the week is cached in the database
        
        Args:
            group_id (str): Group id
            date (datetime): Date
        
        Returns:
            bool: True if the week is cached in the database, otherwise False
        """
        start, end = utils.getStartAndEndOfWeek(date)
        return self.isDateRangeInDB(group_id, start, end)
    
    def getUser(self, user_id):
        return self.users.find_one({"id": user_id})
    
    def getUserCountByGroup(self, group_id):
        return self.users.count_documents({"group_id": group_id})
    
    def getLessonsForGroup(self, group_id):
        return self.lessons.find({"group_id": group_id})
    
    def addUser(self, user_id, group_id, group_name, sub_group = None):
        self.users.insert_one({
            "id": user_id,
            "group_id": group_id,
            "group_name": group_name,
            "sub_group": sub_group
        })
    
    def updateUser(self, user_id, group_id, group_name, sub_group = None):
        self.users.update_one({ "id": user_id }, 
                              { "$set": {
                                  "group_id": group_id,
                                  "group_name": group_name,
                                  "sub_group": sub_group
                                  }
                              }
                              )
    
    def updateUserSubGroup(self, user_id, sub_group):
        self.users.update_one({ "id": user_id }, 
                              {
                                  "$set": {"sub_group": sub_group}
                              }
                              )
    
    def getLessonsInDateRange(self, all_lessons_list, start_date, end_date, sub_group):
        lessons_list = []
        
        for lesson in all_lessons_list:
            # Check if the lesson is before the start of the day
            if (start_date - lesson.get("date")).total_seconds() > 0:
                pass
            # Check if the lesson is after the end of the day
            elif (lesson.get("date") - end_date).total_seconds() > 86300:
                break
            # If the lesson is on the given day, add it to the list
            else:
                if utils.isSubGroupValid(lesson, sub_group):
                    lessons_list.append(lesson)
                
        return lessons_list   
    
    def getDay(self, user_id, date: datetime):
        """
        Get all lessons for one day for given group and date
        
        Args:
            user_id (str): Telegram user id
            date (datetime): Date
        
        Returns:
            List[dict]: Lessons in JSON format
        """
        date, _ = utils.getStartEndOfDay(date)
        
        user = self.users.find_one({"id": user_id})
        group_id = user.get("group_id")
        sub_group = user.get("sub_group")
        
        # Check if the day is cached
        if not self.isDayInDB(group_id, date):
            raise ValueError
        
        # Get all lessons for the group
        group_lessons = self.lessons.find_one({"group_id": group_id}).get("lessons")
        
        # Return the lessons for the given day
        return self.getLessonsInDateRange(group_lessons, date, date, sub_group)
        
    def getWeek(self, user_id, date: datetime):
        """
        Get all lessons for a week for given group and date
            
        Args:
            user_id (str): Telegram user id
            date (datetime): Date
            
        Returns:
            List[dict]: List of lessons in JSON format
        """
        start, end = utils.getStartAndEndOfWeek(date)
        
        user = self.getUser(user_id)
        group_id = user.get("group_id")
        sub_group = user.get("sub_group")
            
        # Check if the week is cached
        if not self.isWeekInDB(group_id, date):
            raise ValueError
            
        # Get all lessons for the group
        group_lessons = self.getLessonsForGroup(group_id)
        last_update = group_lessons.get("last_update").strftime("%d.%m %H:%M:%S")
        
        return self.getLessonsInDateRange(group_lessons.get("lessons"), start, end, sub_group), last_update

    def getGroupsList(self) -> List[str]:
        """
        Get a list of all the groups cached in the database
        
        Returns:
            List[str]: A list of group ids
        """
        # Get all the groups from the users collection
        return self.users.distinct("group_id")

    def saveScheduleToDB(self, group_id: str, lessons_for_this_month: List[dict]):
        """
        Save the lessons for the given group to the database
        
        Args:
            group_id (str): The id of the group
            lessons_for_this_month (List[dict]): The lessons for the given group
        """
        # If the group is already cached, delete the old entry
        self.deleteMonthFromDB(group_id)
        
        # Insert the new entry into the database
        self.lessons.insert_one({
            "group_id": group_id,
            "last_update": datetime.now(),
            "lessons": lessons_for_this_month
        })
        
    def deleteScheduleFromDB(self, group_id: str):
        if self.lessons.count_documents({"group_id": group_id}) > 0:
            self.lessons.delete_one({"group_id": group_id})
    
    
db = DataBase()

