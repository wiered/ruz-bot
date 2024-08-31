import os

from pymongo import MongoClient

client = MongoClient(os.environ.get('MONGODB_ADRESS'), connect=True)
db = client.ruzbotdb
users = db.users
lessons = db.lessons
