from datetime import datetime, timedelta
from telebot.util import quick_markup

def generateStartMarkup():
    today = datetime.today().strftime('%Y-%m-%d')
    tommorrow = (datetime.today() + timedelta(days=1)).strftime('%Y-%m-%d')
    return quick_markup({
        # Button to view the schedule for today
        "Сегодня": {'callback_data' : f'parseDay {today}'},
        # Button to view the schedule for tomorrow
        "Завтра": {'callback_data' : f'parseDay {tommorrow}'},
        # Button to view the schedule for this week
        "Эта неделя": {'callback_data' : 'parseWeek 0'},
        # Button to view the schedule for next week
        "Следующая неделя": {'callback_data' : 'parseWeek 1'},
        # Button to view the user's profile
        "Профиль": {'callback_data' : 'showProfile'},
    }, row_width=2)

start_markup = quick_markup({
        # Button to view the schedule for today
        "Сегодня": {'callback_data' : 'parseDay 0'},
        # Button to view the schedule for tomorrow
        "Завтра": {'callback_data' : 'parseDay 1'},
        # Button to view the schedule for this week
        "Эта неделя": {'callback_data' : 'parseWeek 0'},
        # Button to view the schedule for next week
        "Следующая неделя": {'callback_data' : 'parseWeek 1'},
        # Button to view the user's profile
        "Профиль": {'callback_data' : 'showProfile'},
    }, row_width=2)
