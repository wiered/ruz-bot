import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telebot.util import quick_markup

from ruzbot import markups
from ruzbot.bot import __version__ as BOT_VERSION
from ruzbot.utils import ruz_client
from ruzclient import UserCreate, UserScheduleLesson, UserUpdate
from ruzclient.errors import RuzHttpError

list_of_dangerous_criminals_whom_I_dont_want_to_see_in_my_bot = [
    "930307939"
]

def is_dangerous_criminal(user_id: int) -> bool:
    return str(user_id) in list_of_dangerous_criminals_whom_I_dont_want_to_see_in_my_bot

_PROTOTYPE_ESCAPE_CHARS = ["_", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"]

_DAYS_RU = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

_NUM_EMOJI_MAPPING = {
    1: "1️⃣",
    2: "2️⃣",
    3: "3️⃣",
    4: "4️⃣",
    5: "5️⃣",
    6: "6️⃣",
    7: "7️⃣",
    8: "8️⃣",
    9: "9️⃣"
}

def _escape_like_prototype(schedule_text: str) -> str:
    """Тот же приём, что в bot_prototype.start: символы MarkdownV2, кроме `*`."""
    for char in _PROTOTYPE_ESCAPE_CHARS:
        schedule_text = schedule_text.replace(char, "\\" + char)
    return schedule_text

def _lesson_emoji(kind_of_work: str) -> str:
    """📚 лекция, ✏ практика, 🧪 лаб — по аналогии с EMOJIES в bot_prototype."""
    k = (kind_of_work or "").lower()
    if "лек" in k:
        return "📚"
    if "практ" in k or "семинар" in k:
        return "✏"
    if "лаб" in k:
        return "🧪"
    return "📚"

def _time_hhmm(s: str) -> str:
    return s[:5] if len(s) >= 5 else s

def _lesson_type_mapper(kind_of_work: str) -> str:
    k = (kind_of_work or "").lower()
    if "лек" in k:
        return "📚 лекция"
    if "практ" in k or "семинар" in k:
        return "✏️практика"
    if "лаб" in k:
        return "🧪 лабораторная работа"
    elif "конс" in k:
        return "💬 консультация"
    elif "экз" in k:
        return "🎓 экзамен"
    elif "зач" in k:
        return "🎓 зачет"
    else:
        return f"🍆 {kind_of_work}"

def _format_lesson_block(les: UserScheduleLesson, n: int) -> str:
    t1 = _time_hhmm(les["begin_lesson"])
    t2 = _time_hhmm(les["end_lesson"])
    emoji = _lesson_emoji(les["kind_of_work"])
    aud = les["auditorium_name"] or ""
    bld = les["building"] or ""
    aud_line = f"{aud} 🏢" + (f" 🏢 ({bld}) 🏢" if bld else "🏢🏢🏢 🏢")
    return (
        f"-- *{_NUM_EMOJI_MAPPING.get(n, str(n))} пара {t1} - {t2}* --\n"
        f"  {emoji} {les['discipline_name']} ({_lesson_type_mapper(les['kind_of_work'])})\n"
        f"  🏢 Аудитория 🏢: 🏢{aud_line}🏢\n"
        f"  👩 Преподаватель 👩: 👩{les['lecturer_short_name']}👩\n"
        f"  🍆🍆🍆🍆🍆🍆🍆🍆🍆🍆"
        f"  🍆🍆🍆🍆🍆🍆🍆🍆🍆🍆"
    )

def criminal_format_day_message(lessons: list[UserScheduleLesson], target: datetime) -> str:
    day_date = target.strftime("%d.%m")
    day_name = _DAYS_RU[target.weekday()]
    lines = [
        f"== 🗓 Расписание 🗓 🗓 🗓 на 🗓 {target.strftime('%d.%m.%Y')} 🗓 ==",
        f"\n= 📆 {day_name} 📆 ({day_date}) 📆 =",
    ]
    if not lessons:
        lines.append("  😴 Пар 😴 нет 😴")
    else:
        for n, les in enumerate(sorted(lessons, key=lambda x: (x["begin_lesson"], x["lesson_id"]))):
            lines.append(_format_lesson_block(les, n + 1))
    return _escape_like_prototype("\n".join(lines))

def criminal_format_week_message(anchor: datetime, lessons: list[UserScheduleLesson]) -> str:
    """Неделя пн–сб, как шесть дней в bot_prototype.format_schedule."""
    monday = anchor - timedelta(days=anchor.weekday())
    saturday = monday + timedelta(days=5)
    range_str = f"{monday.strftime('%d.%m')} - {saturday.strftime('%d.%m')}"

    by_date: dict[str, list[UserScheduleLesson]] = defaultdict(list)
    for les in lessons:
        by_date[les["date"]].append(les)

    lines: list[str] = [f"== 🗓 Расписание 🗓 (🗓 {range_str} 🗓) =="]
    days_short = ("📆 Понедельник", "📆 Вторник", "📆 Среда", "📆 Четверг", "📆 Пятница", "📆 Суббота")

    for i in range(6):
        d = monday + timedelta(days=i)
        d_iso = d.strftime("%Y-%m-%d")
        day_lbl = d.strftime("%d.%m")
        lines.append(f"\n*= 📆 {days_short[i]} 📆 ({day_lbl}) 📆 =*")
        day_entries = by_date.get(d_iso, [])
        if day_entries:
            for n, les in enumerate(sorted(day_entries, key=lambda x: (x["begin_lesson"], x["lesson_id"]))):
                lines.append(_format_lesson_block(les, n + 1))
        else:
            lines.append("  😴 Пар 😴 нет")

        lines.append("🍆🍆🍆🍆🍆🍆🍆🍆🍆🍆")
        lines.append("🍆🍆🍆🍆🍆🍆🍆🍆🍆🍆")
        lines.append("🍆🍆🍆🍆🍆🍆🍆🍆🍆🍆")

    return _escape_like_prototype("\n".join(lines))
