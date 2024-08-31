import os

from datetime import datetime, timedelta
from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGODB_ADRESS'), connect=True)
db = client.ruzbotdb
users = db.users
lessons = db.lessons

def saveMonthLessonsToDB(group, lessons_for_this_month):
    if lessons.count_documents({"group_id": group}) > 0:
        lessons.delete_one({"group_id": group})
    
    lessons.insert_one({
        "group_id": group,
        "last_update": datetime.now().strftime("%Y-%m-%d"),
        "lessons": lessons_for_this_month
    })
        
def getAllGroupsList():
    return users.distinct("group_id")
