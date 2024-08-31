import os

from datetime import datetime, timedelta
from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGODB_ADRESS'), connect=True)
db = client.ruzbotdb
users = db.users
lessons = db.lessons

def saveMonthLessonsToDB(lessons_for_this_month):
    lessons.insert_many(lessons_for_this_month)
        
    for lesson in lessons.find():
        date = datetime.strptime(lesson.get("date"), "%Y-%m-%d") + timedelta(minutes=1)
        lessons.update_one({"_id": lesson.get("_id")}, {"$set": {"date": date}})
