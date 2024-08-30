from datetime import datetime, timedelta

LESSION_NUMBER_DICT = {
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

def formatDay(data, _timedelta = 0):
    """
    Format schedule for group for one day
    
    Args:
        data (dict): Schedule in JSON format
        _timedelta (int): Timedelta in days. Default is 0
    
    Returns:
        str: Formatted schedule
    """
    date = datetime.today() + timedelta(days = _timedelta)
    week_day = WEEK_DAYS_LABEL_DICT.get(date.weekday())
    date = date.strftime('%d.%m')
    
    lessions = ""
    for i in range(len(data)): 
        lessions += f"-- {LESSION_NUMBER_DICT.get(data[i].get('beginLesson'))} пара [{data[i].get('beginLesson')} - {data[i].get('endLesson')}] --" + '\n'
        lessions += data[i].get("discipline") + f" ({parseKindOfWork(data[i].get('kindOfWork'))})" + '\n'
        lessions += f"Аудитория: {data[i].get('auditorium').split('/')[1]}" + '\n'
        lessions += f"Преподаватель: {data[i].get('lecturer_title')}, {data[i].get('lecturer_rank')}" + '\n'
    
    if lessions == "":
        return f"= {date} = \n\nПар нет"
    
    return f"= {week_day} ({date}) = \n{lessions}"
    
def formatWeek(data):
    """
    Format schedule for group for one week
    
    Args:
        data (dict): Schedule in JSON format
    
    Returns:
        str: Formatted schedule
    """
    dates = {
    }
    for i in range(len(data)):
        datetime_object = datetime.strptime(data[i].get("date"), '%Y-%m-%d')
        week_day = WEEK_DAYS_LABEL_DICT.get(datetime_object.weekday())
        dates.update(
            {data[i].get("date"): f"_= {week_day} ({'.'.join(data[i].get('date').split('-')[1:])}) =_ \n"}
            )
    
    for i in range(len(data)):
        tmp = dates.get(data[i].get("date"))
        tmp += f"*-- {LESSION_NUMBER_DICT.get(data[i].get('beginLesson'))} пара [{data[i].get('beginLesson')} - {data[i].get('endLesson')}] --*" + '\n  '
        tmp += data[i].get("discipline") + f" ({parseKindOfWork(data[i].get('kindOfWork'))})" + '\n  '
        tmp += f"Аудитория: {data[i].get('auditorium').split('/')[1]}" + '\n  '
        tmp += f"Преподаватель: {data[i].get('lecturer_title')}, {data[i].get('lecturer_rank')}" + '\n'
        
        dates.update({data[i].get("date"): tmp})
    
    # split this by "-": list(dates.keys())[0] and replace "-" with dost, then conver to string
    
    if len(list(dates.keys())) == 0:
        return "Пар нет"
    
    lessions = "== Расписание на неделю {} - {} == \n\n".format(
        ".".join(list(dates.keys())[0].split('-'))[5:], 
        ".".join(list(dates.keys())[-1].split('-'))[5:]
        )
    for key in dates.keys():
        lessions += dates.get(key) + "\n"
    
    replacables = ['.', '-', '(', ')', "="]
    for ch in replacables:            
        lessions = lessions.replace(ch, f"\\{ch}")
    
    return lessions
    
def parseKindOfWork(kindOfWork):
    """
    Parse kind of work
    """
    if kindOfWork == "Лекция":
        return "Лек."
    if kindOfWork == "Практические (семинарские) занятия":
        return "Пр. зан."
    
    return kindOfWork
    