import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Optional

import utils
from dotenv import load_dotenv
from sqlalchemy import (JSON, BigInteger, Column, Date, DateTime, ForeignKey,
                        Integer, String, create_engine, or_)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker

# --------------------
# Logging Configuration
# --------------------
logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.StreamHandler()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)

logger.propagate = False


load_dotenv()
# SQLAlchemy setup
DATABASE_URL = os.environ.get("POSTGRESQL_URL")  # e.g. "postgresql+psycopg2://user:pass@host/dbname"
logger.debug(f"Using DATABASE_URL={DATABASE_URL}")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

Base = declarative_base()


# --------------------
# SQLAlchemy Models
# --------------------

class Group(Base):
    __tablename__ = "groups"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    # Relationship to lessons and users
    lessons = relationship("Lesson", back_populates="group", cascade="all, delete-orphan")
    users = relationship("User", back_populates="group")


class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True, index=True)  # Telegram user_id
    group_id = Column(Integer, ForeignKey("groups.id"), nullable=False)
    group_name = Column(String, nullable=False)
    sub_group = Column(Integer, nullable=True)

    group = relationship("Group", back_populates="users")


class Lesson(Base):
    __tablename__ = "lessons"

    id = Column(Integer, primary_key=True, autoincrement=True)
    group_id = Column(Integer, ForeignKey("groups.id"), index=True, nullable=False)
    date = Column(Date, index=True, nullable=False)
    subgroup = Column(Integer, index=True, nullable=False)
    update_time = Column(DateTime, nullable=False)
    data = Column(JSON, nullable=False)  # stores full lesson JSON as in Mongo

    group = relationship("Group", back_populates="lessons")


# Create tables (if not already present)
logger.debug("Creating database tables if they do not exist...")
Base.metadata.create_all(bind=engine)


# --------------------
# DataBase Class
# --------------------

class DataBase:
    def __init__(self):
        logger.info("Initializing DataBase instance")

        # PostgreSQL session
        self._Session = SessionLocal
        logger.info("DataBase initialized successfully")

    # --------------------
    # Internal Helpers
    # --------------------

    def _get_pg_session(self):
        logger.debug("Opening new PostgreSQL session")
        return self._Session()

    def _ensure_group_in_postgres(self, session, group_id: int, group_name: str):
        """
        Ensure that a Group row exists in Postgres. If not, create it.
        """
        logger.debug(f"_ensure_group_in_postgres called with group_id={group_id}, group_name={group_name}")
        grp = session.query(Group).filter_by(id=int(group_id)).first()
        if not grp:
            logger.info(f"Group {group_id} not found in Postgres; creating new group with name '{group_name}'")
            grp = Group(id=int(group_id), name=group_name)
            session.add(grp)
            session.commit()
            logger.debug(f"Group {group_id} created")
        else:
            logger.debug(f"Group {group_id} already exists")
        return grp

    # --------------------
    # User-related Methods
    # --------------------

    def isUserKnown(self, user_id: int) -> bool:
        """
        Returns True if the user is known.
        """
        logger.debug(f"isUserKnown called for user_id={user_id}")
        session = self._get_pg_session()
        try:
            # Check Postgres
            user_pg = session.query(User).filter_by(id=user_id).first()
            if user_pg:
                logger.debug(f"User {user_id} found in Postgres")
                return True

            logger.debug(f"User {user_id} not found")
            return False
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in isUserKnown")

    def isUserHasSubGroup(self, user_id: int) -> bool:
        """
        Checks if a user has a subgroup in the database.
        Returns True if sub_group is not None, False otherwise.
        """
        logger.debug(f"isUserHasSubGroup called for user_id={user_id}")
        session = self._get_pg_session()
        has_subgroup = False
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                logger.debug(f"User {user_id} not found")
                return False

            logger.debug(f"[isUserHasSubGroup] user_id={user_id}, sub_group={user.sub_group!r}")
            if user.sub_group is not None:
                has_subgroup = True

            return has_subgroup
        finally:
            session.close()
            logger.debug(f"[isUserHasSubGroup] returning {has_subgroup}")

    def getUser(self, user_id: int) -> Optional[dict]:
        """
        Return the user as a dict: {"id": ..., "group_id": ..., "group_name": ..., "sub_group": ...}
        """
        logger.debug(f"getUser called for user_id={user_id}")
        session = self._get_pg_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                logger.debug(f"User {user_id} not found")
                return None

            result = {
                "id": user.id,
                "group_id": user.group_id,
                "group_name": user.group_name,
                "sub_group": user.sub_group,
            }
            logger.debug(f"getUser returning {result}")
            return result
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in getUser")

    def addUser(self, user_id: int, group_id: str, group_name: str, sub_group: Optional[int] = None):
        """
        Insert a new user into Postgres. Also ensure group exists.
        """
        logger.info(f"addUser called: user_id={user_id}, group_id={group_id}, group_name='{group_name}', sub_group={sub_group}")
        session = self._get_pg_session()
        try:
            # Ensure group exists
            self._ensure_group_in_postgres(session, group_id, group_name)

            # Insert user
            new_user = User(id=user_id, group_id=group_id, group_name=group_name, sub_group=sub_group)
            session.add(new_user)
            session.commit()
            logger.info(f"User {user_id} added to Postgres")
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in addUser")

    def updateUser(self, user_id: int, group_id: str, group_name: str, sub_group: Optional[int] = None):
        """
        Update an existing user's group_id, group_name, sub_group.
        """
        logger.info(f"updateUser called: user_id={user_id}, group_id={group_id}, group_name='{group_name}', sub_group={sub_group}")
        session = self._get_pg_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                logger.debug(f"User {user_id} not found; creating new user")
                self.addUser(user_id, group_id, group_name, sub_group)
                return

            # Ensure group exists
            self._ensure_group_in_postgres(session, group_id, group_name)

            # Update fields
            user.group_id = group_id
            user.group_name = group_name
            user.sub_group = sub_group
            session.commit()
            logger.info(f"User {user_id} updated in Postgres")
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in updateUser")

    def updateUserSubGroup(self, user_id: int, sub_group: int):
        """
        Update only the sub_group field of a user.
        """
        logger.info(f"updateUserSubGroup called: user_id={user_id}, sub_group={sub_group}")
        session = self._get_pg_session()
        try:
            user = session.query(User).filter_by(id=user_id).first()
            if not user:
                logger.warning(f"User {user_id} not found anywhere; cannot update sub_group")
                return

            user.sub_group = sub_group
            session.commit()
            logger.info(f"User {user_id} sub_group updated to {sub_group}")
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in updateUserSubGroup")

    def getUserCountByGroup(self, group_id: str) -> int:
        """
        Count how many users have this group_id.
        """
        logger.debug(f"getUserCountByGroup called for group_id={group_id}")
        session = self._get_pg_session()
        try:
            count = session.query(User).filter_by(group_id=group_id).count()
            logger.debug(f"Count for group_id={group_id} is {count}")
            return count
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in getUserCountByGroup")

    # --------------------
    # Group & Lessons-related Methods
    # --------------------

    def isGroupInDB(self, group_id: str) -> bool:
        """
        In Postgres: we interpret "group cached" to mean: lessons exist for that group.
        """
        logger.debug(f"isGroupInDB called for group_id={group_id}")
        # Check Postgres first
        session = self._get_pg_session()
        try:
            exists_in_pg = session.query(Lesson).filter_by(group_id=group_id).first() is not None
            if exists_in_pg:
                logger.debug(f"Group {group_id} found in Postgres lessons")
                return True
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in isGroupInDB")

    def isDateRangeInDB(self, group_id: str, start: datetime, end: datetime) -> bool:
        """
        Check if the group's lessons are "cached" and date range [start, end] lies between
        previous-month-start and next-month-end relative to today.
        Same logic as in Mongo version, but "is cached" means either Postgres has any lessons for group.
        """
        logger.debug(f"isDateRangeInDB called for group_id={group_id}, start={start}, end={end}")
        # If group not cached at all, return False
        if not self.isGroupInDB(group_id):
            logger.debug(f"Group {group_id} not cached; returning False")
            return False

        # Compute bounds
        reference_date = datetime.today()
        start_of_previous_month, end_of_next_month = utils.getPreviousAndNextMonthBounds(reference_date)
        logger.debug(f"Bounds: start_of_previous_month={start_of_previous_month}, end_of_next_month={end_of_next_month}")

        # Check if start < start_of_previous_month
        if (start - start_of_previous_month).total_seconds() < 0:
            logger.debug("Start is before start_of_previous_month; returning False")
            return False

        # Check if end > end_of_next_month
        if (end_of_next_month - end).total_seconds() < 0:
            logger.debug("End is after end_of_next_month; returning False")
            return False

        logger.debug("Date range is within cached bounds; returning True")
        return True

    def isDayInDB(self, group_id: str, date: datetime) -> bool:
        """
        Equivalent to Mongo version: shift date by +3h, then check date range.
        """
        logger.debug(f"isDayInDB called for group_id={group_id}, date={date}")
        shifted = date + timedelta(hours=3)
        result = self.isDateRangeInDB(group_id, shifted, shifted)
        logger.debug(f"isDayInDB returning {result}")
        return result

    def isWeekInDB(self, group_id: str, date: datetime) -> bool:
        logger.debug(f"isWeekInDB called for group_id={group_id}, date={date}")
        start, end = utils.getStartAndEndOfWeek(date)
        result = self.isDateRangeInDB(group_id, start, end)
        logger.debug(f"isWeekInDB returning {result}")
        return result

    def getLessonsForGroup(self, group_id: str) -> List[dict]:
        """
        Return all lessons for a group as a list of dicts. We order by update_time descending
        so that getGroupLastUpdateTime can pick the first.
        """
        logger.debug(f"getLessonsForGroup called for group_id={group_id}")
        session = self._get_pg_session()
        try:
            lessons = (
                session.query(Lesson)
                .filter_by(group_id=group_id)
                .all()
            )
            data_list = [lesson.data for lesson in lessons]
            logger.debug(f"getLessonsForGroup returning {len(data_list)} lessons")
            return data_list
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in getLessonsForGroup")

    def getGroupLastUpdateTime(self, group_id: str) -> datetime:
        """
        Return the most recent update_time for the group's lessons. If none exist, return Jan 1 1970.
        """
        logger.debug(f"getGroupLastUpdateTime called for group_id={group_id}")
        session = self._get_pg_session()
        try:
            latest = (
                session.query(Lesson.update_time)
                .filter_by(group_id=group_id)
                .order_by(Lesson.update_time.desc())
                .first()
            )
            if not latest:
                fallback = datetime.strptime("01-01-1970", "%m-%d-%Y")
                logger.debug(f"No lessons found; returning fallback {fallback}")
                return fallback
            logger.debug(f"Latest update_time for group {group_id} is {latest[0]}")
            return latest[0]
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in getGroupLastUpdateTime")

    def _sort_by_begin_lesson(self, data):
        return sorted(data, key=lambda x: int(x["beginLesson"][0:2]), reverse=False)

    def _sort_lessons(self, data):
        logger.debug(f"_sort_lessons called for {len(data)} lessons")

        grouped = defaultdict(list)
        for item in data:
            grouped[item["date"]].append(item)

        sorted_dates = sorted(grouped.keys(), key=lambda x: datetime.strptime(x, "%Y-%m-%d"))
        sorted_grouped_lists = [grouped[date] for date in sorted_dates]

        sorted_data = [
            item for sublist in [self._sort_by_begin_lesson(sublist) for sublist in sorted_grouped_lists] for item in sublist
        ]

        return sorted_data

    def getLessonsInDateRange(
        self, group_id: str, start_date: datetime, end_date: datetime, sub_group: int
    ) -> List[dict]:
        """
        Return lessons where:
          - group_id matches
          - date between start_date and end_date (inclusive)
          - subgroup is either sub_group or 0
        """
        logger.debug(
            f"getLessonsInDateRange called for group_id={group_id}, "
            f"start_date={start_date}, end_date={end_date}, sub_group={sub_group}"
        )
        # Normalize to date objects if datetime passed
        sd = start_date.date() if isinstance(start_date, datetime) else start_date
        ed = end_date.date() if isinstance(end_date, datetime) else end_date

        session = self._get_pg_session()
        try:
            lessons = (
                session.query(Lesson)
                .filter(
                    Lesson.group_id == group_id,
                    Lesson.date.between(sd, ed),
                    or_(Lesson.subgroup == sub_group, Lesson.subgroup == 0)
                )
                .all()
            )

            data_list = self._sort_lessons([lesson.data for lesson in lessons])
            logger.debug(f"getLessonsInDateRange returning {len(data_list)} lessons")
            return data_list
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in getLessonsInDateRange")

    def saveScheduleToDB(self, group_id: str, lessons_for_this_month: List[dict]):
        """
        Save the lessons for the given group to Postgres. If any lessons_for_this_month,
        delete existing lessons for that group, then insert new ones.
        Each lesson dict is assumed to have at least these keys:
          - "date": a date string or datetime.date object
          - "subgroup": int
          - "update_time": datetime
          - plus arbitrary other keys which we store under data JSON.
        """
        logger.info(f"saveScheduleToDB called for group_id={group_id}, lessons_count={len(lessons_for_this_month)}")
        if len(lessons_for_this_month) == 0:
            logger.debug("No lessons to save; exiting saveScheduleToDB")
            return

        session = self._get_pg_session()
        try:
            # Ensure group exists (group_name not critical here; use existing or dummy)
            grp = session.query(Group).filter_by(id=group_id).first()
            if not grp:
                user_pg = session.query(User).filter_by(group_id=group_id).first()
                if user_pg:
                    grp_name = user_pg.group_name
                logger.info(f"Creating Group {group_id} for schedule save with name '{grp_name}'")
                grp = Group(id=group_id, name=grp_name)
                session.add(grp)
                session.commit()
                logger.debug(f"Group {group_id} created")

            # Delete existing lessons for this group
            deleted = session.query(Lesson).filter_by(group_id=group_id).delete()
            session.commit()
            logger.debug(f"Deleted {deleted} existing lessons for group {group_id}")

            # Bulk insert new lessons
            to_insert = []
            for lesson in lessons_for_this_month:
                raw_date = lesson.get("date")
                if isinstance(raw_date, str):
                    date_obj = datetime.fromisoformat(raw_date).date()
                elif isinstance(raw_date, datetime):
                    date_obj = raw_date.date()
                else:
                    date_obj = raw_date  # already a date

                subgroup = lesson.get("subgroup", 0)
                update_time = lesson.get("update_time")
                if isinstance(update_time, str):
                    update_time_obj = datetime.fromisoformat(update_time)
                else:
                    update_time_obj = update_time

                new_lesson = Lesson(
                    group_id=group_id,
                    date=date_obj,
                    subgroup=subgroup,
                    update_time=update_time_obj,
                    data=lesson,
                )
                to_insert.append(new_lesson)

            session.bulk_save_objects(to_insert)
            session.commit()
            logger.info(f"Saved {len(to_insert)} lessons for group {group_id}")
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in saveScheduleToDB")

    def deleteScheduleFromDB(self, group_id: str):
        """
        Delete all lessons for a given group_id from Postgres.
        """
        logger.info(f"deleteScheduleFromDB called for group_id={group_id}")
        session = self._get_pg_session()
        try:
            deleted = session.query(Lesson).filter_by(group_id=group_id).delete()
            session.commit()
            logger.debug(f"Deleted {deleted} lessons for group {group_id}")
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in deleteScheduleFromDB")

    def getDay(self, user_id: int, date: datetime) -> List[dict]:
        """
        Get all lessons for one day for given user and date.
        Raises ValueError if the day is not cached.
        """
        logger.debug(f"getDay called for user_id={user_id}, date={date}")
        day_start, _ = utils.getStartEndOfDay(date)

        user = self.getUser(user_id)
        if not user:
            logger.error(f"getDay: User {user_id} not found in either DB")
            raise ValueError(f"User {user_id} not found in either DB")

        group_id = user.get("group_id")
        sub_group = user.get("sub_group")

        if not self.isDayInDB(group_id, day_start):
            logger.warning(f"getDay: Day {day_start} for group {group_id} not cached; raising ValueError")
            raise ValueError

        lessons = self.getLessonsInDateRange(group_id, day_start, day_start, sub_group)
        logger.debug(f"getDay returning {len(lessons)} lessons")
        return lessons

    def getWeek(self, user_id: int, date: datetime):
        """
        Get all lessons for a week for given user and date.
        Returns (list_of_lessons, last_update_str)
        Raises ValueError if week not cached.
        """
        logger.debug(f"getWeek called for user_id={user_id}, date={date}")
        start, end = utils.getStartAndEndOfWeek(date)

        user = self.getUser(user_id)
        if not user:
            logger.error(f"getWeek: User {user_id} not found in either DB")
            raise ValueError(f"User {user_id} not found in either DB")

        group_id = user.get("group_id")
        sub_group = user.get("sub_group")

        if not self.isWeekInDB(group_id, date):
            logger.warning(f"getWeek: Week starting {start} for group {group_id} not cached; raising ValueError")
            raise ValueError

        lessons = self.getLessonsForGroup(group_id)
        if len(lessons) == 0:
            fallback = datetime.strptime("01-01-1970", "%m-%d-%Y").strftime("%d.%m %H:%M:%S")
            last_update_str = fallback
            logger.debug(f"getWeek: No lessons found; using fallback last_update={last_update_str}")
        else:
            latest = lessons[0].get("update_time")
            if isinstance(latest, str):
                latest_dt = datetime.fromisoformat(latest)
            else:
                latest_dt = latest
            last_update_str = latest_dt.strftime("%d.%m %H:%M:%S")
            logger.debug(f"getWeek: last_update_str={last_update_str}")

        lessons_in_range = self.getLessonsInDateRange(group_id, start, end, sub_group)
        logger.debug(f"getWeek returning {len(lessons_in_range)} lessons and last_update={last_update_str}")
        return lessons_in_range, last_update_str

    def getGroupsList(self) -> List[str]:
        """
        Return a list of all group_ids present among users in Postgres.
        """
        logger.debug("getGroupsList called")
        session = self._get_pg_session()
        try:
            groups = session.query(User.group_id).distinct().all()
            result = [g[0] for g in groups]
            logger.debug(f"getGroupsList returning {result}")
            return result
        finally:
            session.close()
            logger.debug("PostgreSQL session closed in getGroupsList")

    def getAllGroupsList(self) -> List[str]:
        """
        Alias for getGroupsList
        """
        logger.debug("getAllGroupsList called")
        return self.getGroupsList()

db = DataBase()
