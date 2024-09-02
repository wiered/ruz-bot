from datetime import datetime, timedelta

LESSON_NUMBER_DICT = {
    "08:30": 1,
    "10:10": 2,
    "12:40": 3,
    "14:20": 4,
    "16:00": 5,
    "18:00": 6
}

WEEK_DAYS_LABEL_DICT = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье"
}

def getDate(date: str | datetime) -> datetime:
    """
    Function to convert input date to datetime object.

    Args:
        date (str | datetime): The date to convert. If str, it should be in '%Y-%m-%d' format.
    
    Returns:
        datetime: The datetime object.
    """
    if isinstance(date, str):
        datetime_object = datetime.strptime(date, '%Y-%m-%d')
    else:
        datetime_object = date
        
    return datetime_object


def formatDay(lesson):
    """
    Format one lesson into a string.

    Args:
        lesson (dict): The lesson to format.

    Returns:
        str: The formatted lesson.
    """
    lessons = ""
    
    # Add the lesson number
    lessons += f"*-- {LESSON_NUMBER_DICT.get(lesson.get('beginLesson'))} пара [{lesson.get('beginLesson')} - {lesson.get('endLesson')}] --*" + '\n  '
    
    # Add the lesson discipline and kind of work
    lessons += lesson.get("discipline") + f" ({parseKindOfWork(lesson.get('kindOfWork'))})" + '\n  '
    
    # Add the lesson auditorium
    lessons += f"Аудитория: {lesson.get('auditorium').split('/')[1]}" + '\n  '
    
    # Add the lesson lecturer
    lessons += f"Преподаватель: {lesson.get('lecturer_title')}, {lesson.get('lecturer_rank')}" + '\n'
    
    return lessons


def escapeMessage(message):
    """
    Escape special characters in a string so that they won't break the Markdown formatting.

    Args:
        message (str): The string to escape.

    Returns:
        str: The escaped string.
    """
    
    # List of special characters that must be escaped
    replacables = ['.', '-', '(', ')', "=", "{", "}", "!"]  
    
    # Iterate over each character in the list
    for ch in replacables:
        # Replace the character with its escaped version
        message = message.replace(ch, f"\\{ch}")  
        
    return message


def formatDayMessage(data, _timedelta = 0):
    """
    Format message for group for one day
    
    Args:
        data (dict): Schedule in JSON format
        _timedelta (int): Timedelta in days. Default is 0
    
    Returns:
        str: Formatted message
    """
    date = datetime.today() + timedelta(days = _timedelta)
    week_day = WEEK_DAYS_LABEL_DICT.get(date.weekday())
    date = date.strftime('%d.%m')
    
    if len(data) == 0:
        return escapeMessage(f"= {date} = \n\nПар нет")
    
    lessons = ""
    for lesson in data:
        lessons += formatDay(lesson)
    
    return escapeMessage(f"= {week_day} ({date}) = \n{lessons}")


def formatWeekMessage(data):
    """
    Format message for group for one week
    
    Args:
        data (dict): Schedule in JSON format
    
    Returns:
        str: Formatted message
    """
    if len(data) == 0:
        return "Пар нет"
    
    dates = {
    }
    for i in range(len(data)):
        datetime_object = getDate(data[i].get("date"))
        week_day = WEEK_DAYS_LABEL_DICT.get(datetime_object.weekday())
        dates.update(
            {data[i].get("date"): f"_= {week_day} ({datetime_object.strftime('%d.%m')}) =_ \n"}
            )
    
    for lesson in data:
        tmp = dates.get(lesson.get("date")) + formatDay(lesson)
        dates.update({lesson.get("date"): tmp})
    
    datetime_object = getDate(data[0].get("date"))
    
    lessons = "== Расписание на неделю {} - {} == \n\n".format(
        datetime_object.strftime('%d.%m'), 
        (datetime_object + timedelta(days=5)).strftime('%d.%m')
        )
    for key in dates.keys():
        lessons += dates.get(key) + "\n"
    
    if len(lessons) > 4000:
        lessons = "Message too long\n\n"
    
    return escapeMessage(lessons)

def parseKindOfWork(kind_of_work):
    """
    Parse kind of work
    """
    if kind_of_work == "Лекции":
        return "Лек."
    if kind_of_work == "Практические (семинарские) занятия":
        return "Пр. зан."
    
    return kind_of_work
    