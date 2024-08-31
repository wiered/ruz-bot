from datetime import datetime, timedelta

LESSON_NUMBER_DICT = {
    "08:30": 1,
    "10:10": 2,
    "12:40": 3,
    "14:20": 4,
    "16:00": 5,
    "17:40": 6
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

def getDate(date):
    if type (date) == str:
        datetime_object = datetime.strptime(date, '%Y-%m-%d')
    else:
        datetime_object = date
        
    return datetime_object

def formatDay(lesson):
    lessons =""
    
    lessons += f"*-- {LESSON_NUMBER_DICT.get(lesson.get('beginLesson'))} пара [{lesson.get('beginLesson')} - {lesson.get('endLesson')}] --*" + '\n  '
    lessons += lesson.get("discipline") + f" ({parseKindOfWork(lesson.get('kindOfWork'))})" + '\n  '
    lessons += f"Аудитория: {lesson.get('auditorium').split('/')[1]}" + '\n  '
    lessons += f"Преподаватель: {lesson.get('lecturer_title')}, {lesson.get('lecturer_rank')}" + '\n'
    
    return lessons

def escapeMessage(message):
    replacables = ['.', '-', '(', ')', "=", "{", "}"]
    for ch in replacables:            
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
    