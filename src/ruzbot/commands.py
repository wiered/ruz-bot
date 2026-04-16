import logging
from collections import defaultdict
from datetime import datetime, timedelta

from telebot import types
from telebot.util import quick_markup

from ruzbot import cache, markups
from ruzbot.bot import __version__ as BOT_VERSION
from ruzbot.utils import ruz_client, remove_position
from ruzclient import UserCreate, UserScheduleLesson, UserUpdate
from ruzclient.errors import RuzHttpError
from ruzbot.deathnote import (
    is_dangerous_criminal,
    criminal_format_day_message,
    criminal_format_week_message,
)

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

# Как в bot_prototype: экранируем всё, кроме «ручных» звёздочек разметки в шаблоне.
_PROTOTYPE_ESCAPE_CHARS = [
    "_",
    "[",
    "]",
    "(",
    ")",
    "~",
    "`",
    ">",
    "#",
    "+",
    "-",
    "=",
    "|",
    "{",
    "}",
    ".",
    "!",
]

_DAYS_RU = (
    "Понедельник",
    "Вторник",
    "Среда",
    "Четверг",
    "Пятница",
    "Суббота",
    "Воскресенье",
)

_LESSON_NUMBER_MAP = {
    "08:30": "1",
    "10:10": "2",
    "12:40": "3",
    "14:20": "4",
    "16:00": "5",
    "18:00": "6",
    "19:40": "7",
    "20:00": "7",
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
        return "лекция"
    if "практ" in k or "семинар" in k:
        return "практика"
    if "лаб" in k:
        return "лабораторная работа"
    elif "конс" in k:
        return "консультация"
    elif "экз" in k:
        return "экзамен"
    elif "зач" in k:
        return "зачет"
    else:
        return kind_of_work


def _format_lesson_block(les: UserScheduleLesson) -> str:
    t1 = _time_hhmm(les["begin_lesson"])
    t2 = _time_hhmm(les["end_lesson"])
    emoji = _lesson_emoji(les["kind_of_work"])
    aud = les["auditorium_name"] or ""
    # bld = les["building"] or ""
    aud_line = f"{aud}"
    #  + (f" ({bld})" if bld else "")
    return (
        f"-- *{_LESSON_NUMBER_MAP.get(t1)} пара {t1} - {t2}* --\n"
        f"  {emoji} {les['discipline_name']} ({_lesson_type_mapper(les['kind_of_work'])})\n"
        f"  Аудитория: {aud_line}\n"
        f"  Преподаватель: {remove_position(les['lecturer_short_name'])}"
    )


def _format_day_message(lessons: list[UserScheduleLesson], target: datetime) -> str:
    day_date = target.strftime("%d.%m")
    day_name = _DAYS_RU[target.weekday()]
    lines = [
        f"== 🗓 Расписание на {target.strftime('%d.%m.%Y')} ==",
        f"\n= 📆 {day_name} ({day_date}) =",
    ]
    if not lessons:
        lines.append("  😴 Пар нет")
    else:
        for n, les in enumerate(
            sorted(lessons, key=lambda x: (x["begin_lesson"], x["lesson_id"]))
        ):
            lines.append(_format_lesson_block(les))
    return _escape_like_prototype("\n".join(lines))


def _format_week_message(anchor: datetime, lessons: list[UserScheduleLesson]) -> str:
    """Неделя пн–сб, как шесть дней в bot_prototype.format_schedule."""
    monday = anchor - timedelta(days=anchor.weekday())
    saturday = monday + timedelta(days=5)
    range_str = f"{monday.strftime('%d.%m')} - {saturday.strftime('%d.%m')}"

    by_date: dict[str, list[UserScheduleLesson]] = defaultdict(list)
    for les in lessons:
        by_date[les["date"]].append(les)

    lines: list[str] = [f"== 🗓 Расписание ({range_str}) =="]
    days_short = ("Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота")

    for i in range(6):
        d = monday + timedelta(days=i)
        d_iso = d.strftime("%Y-%m-%d")
        day_lbl = d.strftime("%d.%m")
        lines.append(f"\n*= 📆 {days_short[i]} ({day_lbl}) =*")
        day_entries = by_date.get(d_iso, [])
        if day_entries:
            for n, les in enumerate(
                sorted(day_entries, key=lambda x: (x["begin_lesson"], x["lesson_id"]))
            ):
                lines.append(_format_lesson_block(les))
        else:
            lines.append("  😴 Пар нет")

    return _escape_like_prototype("\n".join(lines))


def _lessons_for_date(
    lessons: list[UserScheduleLesson], target_date: datetime
) -> list[UserScheduleLesson]:
    target_iso = target_date.strftime("%Y-%m-%d")
    return [lesson for lesson in lessons if lesson["date"] == target_iso]


async def _fetch_user(client, user_id: int):
    async def loader():
        try:
            return await client.users.get_by_id(user_id)
        except RuzHttpError as e:
            if e.status_code == 404:
                return None
            raise

    return await cache.get_or_load_profile(user_id, loader)


def _normalize_parse_day_delta(date_arg) -> int:
    """
    Смещение в днях от сегодня. Строка YYYY-MM-DD → дельта к сегодня (старые кнопки с датой).
    Иначе — целое число как смещение (0/1 и навигация).
    """
    if date_arg is None:
        return 0
    s = str(date_arg).strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        try:
            d = datetime.strptime(s, "%Y-%m-%d").date()
            today = datetime.today().date()
            return (d - today).days
        except ValueError:
            logger.error(f"Invalid parseDay date '{s}', defaulting to 0")
            return 0
    try:
        return int(s)
    except ValueError:
        logger.error(f"Invalid parseDay arg '{s}', defaulting to 0")
        return 0


async def dateCommand(bot, message, date_arg, *, user_id: int):
    """
    Расписание на день через ``GET .../schedule/user/{id}/day``.
    """
    delta_days = _normalize_parse_day_delta(date_arg)
    logger.info(
        f"dateCommand called: user={user_id}, date_arg={date_arg!r} -> delta_days={delta_days}"
    )

    async with ruz_client() as client:
        target_date = datetime.today() + timedelta(days=delta_days)
        lessons = await cache.get_or_load_week_lessons(
            user_id,
            target_date.date(),
            lambda anchor_date: client.schedule.get_user_week(user_id, anchor_date),
        )

    if lessons is None:
        lessons = []
    day_lessons = _lessons_for_date(lessons, target_date)

    if is_dangerous_criminal(user_id):
        reply_message = criminal_format_day_message(day_lessons, target_date)
    else:
        reply_message = _format_day_message(day_lessons, target_date)

    reply_message = reply_message.replace("преподавател", "преподаватель")

    markup = quick_markup(
        {
            "Пред. день": {"callback_data": f"parseDay {delta_days - 1}"},
            "Назад": {"callback_data": "start"},
            "След. день": {"callback_data": f"parseDay {delta_days + 1}"},
        },
        row_width=3,
    )

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )
    await cache.store_screen_snapshot(
        user_id,
        cache.normalize_screen_key(f"parseDay {delta_days}"),
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
        source=f"parseDay {delta_days}",
    )
    logger.info(f"dateCommand completed: user={user_id}")


async def weekCommand(bot, message, _timedelta, *, user_id: int):
    """
    Расписание на неделю через ``GET .../schedule/user/{id}/week``.
    """
    logger.info(f"weekCommand called: user={user_id}, _timedelta={_timedelta!r}")

    async with ruz_client() as client:
        try:
            delta_weeks = int(_timedelta)
        except (TypeError, ValueError):
            delta_weeks = 0
            logger.error(f"Invalid _timedelta '{_timedelta}', defaulting to 0")

        base = datetime.today() + timedelta(weeks=delta_weeks)
        lessons = await cache.get_or_load_week_lessons(
            user_id,
            base.date(),
            lambda anchor_date: client.schedule.get_user_week(user_id, anchor_date),
        )
        last_update = datetime.now().strftime("%d.%m %H:%M:%S")

    if lessons is None:
        lessons = []

    if is_dangerous_criminal(user_id):
        temp_message = criminal_format_week_message(base, lessons)
    else:
        temp_message = _format_week_message(base, lessons)

    reply_message = (
        temp_message
        + "\n\n"
        + _escape_like_prototype(f"Последнее обновление: {last_update}")
    )
    reply_message = reply_message.replace("преподавател", "преподаватель")

    prev_week = delta_weeks - 1
    next_week = delta_weeks + 1
    markup = types.InlineKeyboardMarkup()
    markup.row(
        types.InlineKeyboardButton(
            "Пред. нед.", callback_data=f"parseWeek {prev_week}"
        ),
        types.InlineKeyboardButton("Назад", callback_data="start"),
        types.InlineKeyboardButton(
            "След. нед.", callback_data=f"parseWeek {next_week}"
        ),
    )
    markup.row(
        types.InlineKeyboardButton(
            "👤 На неделе",
            callback_data=f"weekTeachersList {delta_weeks} 0",
        ),
        types.InlineKeyboardButton(
            "📚 На неделе",
            callback_data=f"weekSubjectsList {delta_weeks} 0",
        ),
    )

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )
    await cache.store_screen_snapshot(
        user_id,
        cache.normalize_screen_key(f"parseWeek {delta_weeks}"),
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
        source=f"parseWeek {delta_weeks}",
    )
    logger.info(f"weekCommand completed: user={user_id}")


async def setGroupCommand(bot, message, *, user_id: int):
    logger.info(f"setGroupCommand called: user={user_id}")
    await bot.reply_to(
        message,
        "Введи имя группы полностью (например ИС221 или МАГ-М241): ",
    )


async def setSubGroupCommand(bot, message, *, user_id: int):
    logger.info(f"setSubGroupCommand called: user={user_id}")
    reply_message = (
        "Введите одну цифру подгруппы: 0, 1 или 2.\n"
        "Если номер не является числом, введите 0."
    )
    await bot.reply_to(message, reply_message)


async def sendProfileCommand(bot, message, *, user_id: int):
    logger.info(f"sendProfileCommand called: user={user_id}")

    async with ruz_client() as client:
        user = await _fetch_user(client, user_id)
        if not user or not user.get("group_oid") or user.get("subgroup") is None:
            await backCommand(bot, message, user_id=user_id)
            return

        group_oid = user.get("group_oid")
        subgroup = user.get("subgroup")
        username = user.get("username", "")
        created_at = user.get("created_at")
        last_used_at = user.get("last_used_at")

    safe_username = _escape_like_prototype(username or "")
    reply_message = (
        f"Ваш профиль: \n"
        f"group\\_oid: `{group_oid}`\n"
        f"Подгруппа: `{subgroup}`\n"
        f"username: @{safe_username}\n"
        f"created\\_at: `{created_at}`\n"
        f"last\\_used\\_at: `{last_used_at}`\n"
        f"bot\\_version: `{BOT_VERSION}`"
    )

    markup = quick_markup(
        {
            "Установить группу": {"callback_data": "configureGroup"},
            "Назад": {"callback_data": "start"},
            "GitHub": {"url": "https://github.com/wiered/ruz-bot/"},
        },
        row_width=2,
    )

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )
    await cache.store_screen_snapshot(
        user_id,
        "showProfile",
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
        source="showProfile",
    )
    logger.info(f"sendProfileCommand completed: user={user_id}")


async def setGroup(bot, callback, group_oid: int, group_label: str) -> None:
    """
    Создаёт или обновляет группу на сервере. Дальше бот просит подгруппу (0/1/2);
    при смене группы у существующего пользователя подгруппа на API не обнуляется —
    бэкенд не допускает subgroup=null при заданном group_oid.
    """
    user_id = callback.from_user.id
    logger.info(
        f"setGroup called: user_id={user_id}, group_oid={group_oid}, group_label={group_label!r}"
    )

    uname = callback.from_user.username or str(user_id)

    async with ruz_client() as client:
        hits = await client.groups.search_groups_by_name(group_label)
        hit = next((h for h in hits if h["oid"] == group_oid), None)
        if hit is None and hits:
            hit = hits[0]

        existing = await _fetch_user(client, user_id)

        if existing is None:
            payload = UserCreate(
                id=user_id,
                username=uname,
                group_oid=group_oid,
                subgroup=None,
                group_guid=hit["guid"] if hit else None,
                group_name=hit["name"] if hit else group_label,
                faculty_name=hit.get("faculty_name") if hit else None,
            )
            await client.users.create_user(payload)
            logger.info(
                f"User {user_id} created with group_oid={group_oid}, subgroup=null"
            )
            await cache.invalidate_user(user_id)
            return
        upd = UserUpdate(
            group_oid=group_oid,
            group_guid=hit["guid"] if hit else None,
            group_name=hit["name"] if hit else group_label,
            faculty_name=hit.get("faculty_name") if hit else None,
        )
        await client.users.update_user(user_id, upd)
        await cache.invalidate_user(user_id)
        logger.info(f"User {user_id} updated group_oid={group_oid}")


async def updateUserSubGroup(user_id: int, sub_group: int) -> None:
    async with ruz_client() as client:
        await client.users.update_user(user_id, UserUpdate(subgroup=sub_group))
    await cache.invalidate_user(user_id)


async def search_menu_stub_command(
    bot, message, *, user_id: int, screen_name: str = "searchStub"
) -> None:
    """Временная заглушка для «Преподаватели» / «Предметы» в главном меню."""
    reply_message = "Ой, это пока что недоступно"
    markup = quick_markup({"Назад": {"callback_data": "start"}}, row_width=1)
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=reply_message,
        reply_markup=markup,
    )
    await cache.store_screen_snapshot(
        user_id,
        screen_name,
        text=reply_message,
        reply_markup=markup,
        source=screen_name,
    )


async def backCommand(bot, message, additional_message: str = "", *, user_id: int):
    logger.info(
        f"backCommand called: user_id={user_id}, additional_message={additional_message!r}"
    )

    reply_message = (
        additional_message
        + "Привет, я бот для просмотра расписания МГТУ. Что хочешь узнать?\n"
    )
    markup = markups.generateStartMarkup()

    async with ruz_client() as client:
        user = await _fetch_user(client, user_id)

    if user is not None and user.get("group_oid") and user.get("subgroup") is not None:
        pass
    elif user is not None and user.get("group_oid") and user.get("subgroup") is None:
        markup = quick_markup(
            {"Выбрать другую группу": {"callback_data": "configureGroup"}},
            row_width=1,
        )
        reply_message = (
            "Привет, я бот для просмотра расписания МГТУ.\n"
            "Группа выбрана — введите одну цифру подгруппы: 0, 1 или 2 (завершение регистрации).\n"
        )
    else:
        markup = quick_markup(
            {"Установить группу": {"callback_data": "configureGroup"}},
            row_width=1,
        )
        reply_message = (
            "Привет, я бот для просмотра расписания МГТУ. "
            "У тебя не установлена группа, друг.\n"
        )

    await bot.edit_message_text(
        text=reply_message,
        chat_id=message.chat.id,
        message_id=message.message_id,
        reply_markup=markup,
    )
    if not additional_message:
        await cache.store_screen_snapshot(
            user_id,
            "start",
            text=reply_message,
            reply_markup=markup,
            source="start",
        )
    logger.info(f"backCommand completed: user_id={user_id}")
