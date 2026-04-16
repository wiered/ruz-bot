"""
Поиск по преподавателям и дисциплинам (как в bot_prototype): списки из API,
расписание через ``RuzClient.search`` (:class:`ruzclient.http.endpoints.search.SearchEndpoints`).
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timedelta

from telebot import types
from telebot.util import quick_markup

from ruzbot import cache
from ruzbot import commands
from ruzbot.deathnote import (
    criminal_format_day_message,
    criminal_format_week_message,
    is_dangerous_criminal,
)
from ruzbot.utils import ruz_client, remove_position
from ruzclient import UserScheduleLesson
from ruzclient.errors import RuzHttpError

logger = logging.getLogger(__name__)

_PAGE_SIZE = 6


def _chunk_list(lst: list, chunk_size: int) -> list:
    return [lst[i : i + chunk_size] for i in range(0, len(lst), chunk_size)]


def _btn_label(prefix: str, title: str, max_len: int = 28) -> str:
    t = title if len(title) <= max_len else title[: max_len - 1] + "…"
    return f"{prefix} {t}"


def _commands_escape(s: str) -> str:
    return commands._escape_like_prototype(s)


async def _edit_and_cache(
    bot,
    message,
    *,
    user_id: int,
    screen_name: str,
    text: str,
    reply_markup=None,
    parse_mode: str | None = None,
) -> None:
    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
    )
    await cache.store_screen_snapshot(
        user_id,
        screen_name,
        text=text,
        reply_markup=reply_markup,
        parse_mode=parse_mode,
        source=screen_name,
    )


def _unique_lecturers_from_lessons(
    lessons: list[UserScheduleLesson],
) -> list[tuple[int, str]]:
    seen: dict[int, str] = {}
    for les in lessons:
        lid = les.get("lecturer_id")
        if lid is None:
            continue
        name = les.get("lecturer_short_name") or "?"
        if lid not in seen:
            seen[lid] = name
    return sorted(seen.items(), key=lambda x: (x[1].lower(), x[0]))


def _unique_disciplines_from_lessons(
    lessons: list[UserScheduleLesson],
) -> list[tuple[int, str]]:
    seen: dict[int, str] = {}
    for les in lessons:
        did = les.get("discipline_id")
        if did is None:
            continue
        name = les.get("discipline_name") or "?"
        if did not in seen:
            seen[did] = name
    return sorted(seen.items(), key=lambda x: (x[1].lower(), x[0]))


async def search_teacher_list_command(bot, message, page: int, *, user_id: int) -> None:
    async with ruz_client() as client:
        try:
            lecturers = await client.lecturers.list_lecturers()
        except RuzHttpError as e:
            logger.error("lecturer list failed: %s", e)
            return

    total = len(lecturers)
    if total == 0:
        markup = quick_markup({"Назад": {"callback_data": "start"}}, row_width=1)
        await _edit_and_cache(
            bot,
            message,
            user_id=user_id,
            screen_name=cache.normalize_screen_key(f"teacherPage {page}"),
            text="В базе пока нет преподавателей.",
            reply_markup=markup,
        )
        return

    pages = max(1, math.ceil(total / _PAGE_SIZE))
    page = page % pages
    start = page * _PAGE_SIZE
    display = lecturers[start : start + _PAGE_SIZE]

    markup = types.InlineKeyboardMarkup()
    for pair in _chunk_list(display, 2):
        row = [
            types.InlineKeyboardButton(
                _btn_label("👤", lec.get("short_name") or lec.get("full_name") or "?"),
                callback_data=f"teacherCard {lec['id']} {page}",
            )
            for lec in pair
        ]
        markup.row(*row)

    prev_p = (page - 1) % pages
    next_p = (page + 1) % pages
    markup.row(
        types.InlineKeyboardButton(
            "⬅️ Пред. стр.", callback_data=f"teacherPage {prev_p}"
        ),
        types.InlineKeyboardButton("🏠 Назад", callback_data="start"),
        types.InlineKeyboardButton(
            "➡️ След. стр.", callback_data=f"teacherPage {next_p}"
        ),
    )

    await bot.edit_message_text(
        chat_id=message.chat.id,
        message_id=message.message_id,
        text="Выберите преподавателя:",
        reply_markup=markup,
    )
    await cache.store_screen_snapshot(
        user_id,
        cache.normalize_screen_key(f"teacherPage {page}"),
        text="Выберите преподавателя:",
        reply_markup=markup,
        source=f"teacherPage {page}",
    )


async def teacher_card_command(
    bot, message, lecturer_id: int, list_page: int, *, user_id: int
) -> None:
    async with ruz_client() as client:
        try:
            lecturer = await client.lecturers.get_lecturer(lecturer_id)
        except RuzHttpError as e:
            logger.error("lecturer get failed: %s", e)
            return

    body = (
        f"👤 Преподаватель\n"
        f"🆔 ID: {lecturer.id}\n"
        f"📛 Имя: {lecturer.full_name}\n"
        f"🎓 Должность: {lecturer.rank}"
    )
    markup = quick_markup(
        {
            "📅 Сегодня": {"callback_data": f"lecturerDay {lecturer_id} 0 {list_page}"},
            "📅 Эта неделя": {
                "callback_data": f"lecturerWeek {lecturer_id} 0 {list_page}"
            },
            "К списку": {"callback_data": f"teacherPage {list_page}"},
            "🏠 Главная": {"callback_data": "start"},
        },
        row_width=2,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"teacherCard {lecturer_id} {list_page}"
        ),
        text=_commands_escape(body),
        reply_markup=markup,
    )


async def lecturer_day_command(
    bot,
    message,
    lecturer_id: int,
    day_delta: int,
    list_page: int,
    *,
    user_id: int,
    from_user_week: int | None = None,
) -> None:
    uwd = from_user_week
    if uwd is not None:
        back_cb = f"weekTeacherOpen {lecturer_id} {uwd} {list_page}"

        def day_line(dd: int) -> str:
            return f"lecturerDayW {lecturer_id} {dd} {list_page} {uwd}"
    else:
        back_cb = f"teacherCard {lecturer_id} {list_page}"

        def day_line(dd: int) -> str:
            return f"lecturerDay {lecturer_id} {dd} {list_page}"

    async with ruz_client() as client:
        target = datetime.today() + timedelta(days=day_delta)
        try:
            # Без group_id/sub_group: как CLI и документация — иначе часто пусто из‑за фильтра по чужой группе.
            lessons = await client.search.lecturer_day(lecturer_id, target.date())
        except RuzHttpError as e:
            logger.error("lecturer day failed: %s", e)
            return

        try:
            lecturer = await client.lecturers.get_lecturer(lecturer_id)
        except (RuzHttpError, ValueError):
            lecturer = None
    name = ""
    if lecturer is not None:
        name = lecturer.get("full_name") or lecturer.get("short_name") or ""

    if is_dangerous_criminal(user_id):
        body = criminal_format_day_message(lessons, target)
    else:
        body = commands._format_day_message(lessons, target)
    header = _commands_escape(f"👤 {name}\n\n") if name else ""
    reply_message = header + body
    reply_message = reply_message.replace("преподавател", "преподаватель")

    markup = quick_markup(
        {
            "Пред. день": {"callback_data": day_line(day_delta - 1)},
            "Назад": {"callback_data": back_cb},
            "След. день": {"callback_data": day_line(day_delta + 1)},
        },
        row_width=3,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"lecturerDayW {lecturer_id} {day_delta} {list_page} {uwd}"
            if uwd is not None
            else f"lecturerDay {lecturer_id} {day_delta} {list_page}"
        ),
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )


async def lecturer_week_command(
    bot,
    message,
    lecturer_id: int,
    week_delta: int,
    list_page: int,
    *,
    user_id: int,
    from_user_week: int | None = None,
) -> None:
    uwd = from_user_week
    if uwd is not None:
        back_cb = f"weekTeacherOpen {lecturer_id} {uwd} {list_page}"

        def week_line(wd: int) -> str:
            return f"lecturerWeekW {lecturer_id} {wd} {list_page} {uwd}"
    else:
        back_cb = f"teacherCard {lecturer_id} {list_page}"

        def week_line(wd: int) -> str:
            return f"lecturerWeek {lecturer_id} {wd} {list_page}"

    async with ruz_client() as client:
        base = datetime.today() + timedelta(weeks=week_delta)
        try:
            lessons = await client.search.lecturer_week(lecturer_id, base.date())
        except RuzHttpError as e:
            text = _commands_escape(
                f"Не удалось загрузить расписание: HTTP {e.status_code}"
            )
            markup = quick_markup({"Назад": {"callback_data": back_cb}}, row_width=1)
            await _edit_and_cache(
                bot,
                message,
                user_id=user_id,
                screen_name=cache.normalize_screen_key(
                    f"lecturerWeekW {lecturer_id} {week_delta} {list_page} {uwd}"
                    if uwd is not None
                    else f"lecturerWeek {lecturer_id} {week_delta} {list_page}"
                ),
                text=text,
                reply_markup=markup,
            )
            return

        try:
            lecturer = await client.lecturers.get_lecturer(lecturer_id)
        except (RuzHttpError, ValueError):
            lecturer = None
    name = ""
    if lecturer is not None:
        name = lecturer.get("full_name") or lecturer.get("short_name") or ""

    last_update = datetime.now().strftime("%d.%m %H:%M:%S")
    if is_dangerous_criminal(user_id):
        temp = criminal_format_week_message(base, lessons)
    else:
        temp = commands._format_week_message(base, lessons)
    header = _commands_escape(f"👤 {name}\n\n") if name else ""
    reply_message = (
        header
        + temp
        + "\n\n"
        + _commands_escape(f"Последнее обновление: {last_update}")
    )
    reply_message = reply_message.replace("преподавател", "преподаватель")

    prev_w = week_delta - 1
    next_w = week_delta + 1
    markup = quick_markup(
        {
            "Пред. нед.": {"callback_data": week_line(prev_w)},
            "Назад": {"callback_data": back_cb},
            "След. нед.": {"callback_data": week_line(next_w)},
        },
        row_width=3,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"lecturerWeekW {lecturer_id} {week_delta} {list_page} {uwd}"
            if uwd is not None
            else f"lecturerWeek {lecturer_id} {week_delta} {list_page}"
        ),
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )


# --- Дисциплины ---


async def search_subject_list_command(bot, message, page: int, *, user_id: int) -> None:
    async with ruz_client() as client:
        try:
            items = await client.disciplines.list_disciplines()
        except RuzHttpError as e:
            logger.error("discipline list failed: %s", e)
            return
    total = len(items)
    if total == 0:
        markup = quick_markup({"Назад": {"callback_data": "start"}}, row_width=1)
        await _edit_and_cache(
            bot,
            message,
            user_id=user_id,
            screen_name=cache.normalize_screen_key(f"subjectPage {page}"),
            text="В базе пока нет дисциплин.",
            reply_markup=markup,
        )
        return

    pages = max(1, math.ceil(total / _PAGE_SIZE))
    page = page % pages
    start = page * _PAGE_SIZE
    display = items[start : start + _PAGE_SIZE]

    markup = types.InlineKeyboardMarkup()
    for pair in _chunk_list(display, 2):
        row = [
            types.InlineKeyboardButton(
                _btn_label("📚", d.get("name") or "?"),
                callback_data=f"subjectCard {d['id']} {page}",
            )
            for d in pair
        ]
        markup.row(*row)

    prev_p = (page - 1) % pages
    next_p = (page + 1) % pages
    markup.row(
        types.InlineKeyboardButton(
            "⬅️ Пред. стр.", callback_data=f"subjectPage {prev_p}"
        ),
        types.InlineKeyboardButton("🏠 Назад", callback_data="start"),
        types.InlineKeyboardButton(
            "➡️ След. стр.", callback_data=f"subjectPage {next_p}"
        ),
    )

    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(f"subjectPage {page}"),
        text="Выберите предмет:",
        reply_markup=markup,
    )


async def subject_card_command(
    bot, message, discipline_id: int, list_page: int, *, user_id: int
) -> None:
    async with ruz_client() as client:
        try:
            d = await client.disciplines.get_discipline(discipline_id)
        except (RuzHttpError, ValueError) as e:
            logger.error("discipline get failed: %s", e)
            return
    exam = d.get("examtype") or "—"
    body = (
        f"📚 Предмет\n"
        f"🆔 ID: {d.get('id')}\n"
        f"📖 Название: {d.get('name', '')}\n"
        f"📝 Контроль: {exam}"
    )
    markup = quick_markup(
        {
            "📅 Сегодня": {
                "callback_data": f"disciplineDay {discipline_id} 0 {list_page}"
            },
            "📅 Эта неделя": {
                "callback_data": f"disciplineWeek {discipline_id} 0 {list_page}"
            },
            "К списку": {"callback_data": f"subjectPage {list_page}"},
            "🏠 Главная": {"callback_data": "start"},
        },
        row_width=2,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"subjectCard {discipline_id} {list_page}"
        ),
        text=_commands_escape(body),
        reply_markup=markup,
    )


async def discipline_day_command(
    bot,
    message,
    discipline_id: int,
    day_delta: int,
    list_page: int,
    *,
    user_id: int,
    from_user_week: int | None = None,
) -> None:
    uwd = from_user_week
    if uwd is not None:
        back_cb = f"weekSubjectOpen {discipline_id} {uwd} {list_page}"

        def day_line(dd: int) -> str:
            return f"disciplineDayW {discipline_id} {dd} {list_page} {uwd}"
    else:
        back_cb = f"subjectCard {discipline_id} {list_page}"

        def day_line(dd: int) -> str:
            return f"disciplineDay {discipline_id} {dd} {list_page}"

    async with ruz_client() as client:
        target = datetime.today() + timedelta(days=day_delta)
        try:
            lessons = await client.search.discipline_day(discipline_id, target.date())
        except RuzHttpError as e:
            text = _commands_escape(
                f"Не удалось загрузить расписание: HTTP {e.status_code}"
            )
            markup = quick_markup({"Назад": {"callback_data": back_cb}}, row_width=1)
            await _edit_and_cache(
                bot,
                message,
                user_id=user_id,
                screen_name=cache.normalize_screen_key(
                    f"disciplineDayW {discipline_id} {day_delta} {list_page} {uwd}"
                    if uwd is not None
                    else f"disciplineDay {discipline_id} {day_delta} {list_page}"
                ),
                text=text,
                reply_markup=markup,
            )
            return

        raw = None
        try:
            raw = await client.disciplines.get_discipline(discipline_id)
        except (RuzHttpError, ValueError) as e:
            logger.error("discipline get failed: %s", e)
    title = ""
    if raw is not None:
        title = raw.get("name") or ""

    if is_dangerous_criminal(user_id):
        body = criminal_format_day_message(lessons, target)
    else:
        body = commands._format_day_message(lessons, target)
    header = _commands_escape(f"📚 {title}\n\n") if title else ""
    reply_message = header + body
    reply_message = reply_message.replace("преподавател", "преподаватель")

    markup = quick_markup(
        {
            "Пред. день": {"callback_data": day_line(day_delta - 1)},
            "Назад": {"callback_data": back_cb},
            "След. день": {"callback_data": day_line(day_delta + 1)},
        },
        row_width=3,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"disciplineDayW {discipline_id} {day_delta} {list_page} {uwd}"
            if uwd is not None
            else f"disciplineDay {discipline_id} {day_delta} {list_page}"
        ),
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )


async def discipline_week_command(
    bot,
    message,
    discipline_id: int,
    week_delta: int,
    list_page: int,
    *,
    user_id: int,
    from_user_week: int | None = None,
) -> None:
    uwd = from_user_week
    if uwd is not None:
        back_cb = f"weekSubjectOpen {discipline_id} {uwd} {list_page}"

        def week_line(wd: int) -> str:
            return f"disciplineWeekW {discipline_id} {wd} {list_page} {uwd}"
    else:
        back_cb = f"subjectCard {discipline_id} {list_page}"

        def week_line(wd: int) -> str:
            return f"disciplineWeek {discipline_id} {wd} {list_page}"

    async with ruz_client() as client:
        base = datetime.today() + timedelta(weeks=week_delta)
        try:
            lessons = await client.search.discipline_week(discipline_id, base.date())
        except RuzHttpError as e:
            text = _commands_escape(
                f"Не удалось загрузить расписание: HTTP {e.status_code}"
            )
            markup = quick_markup({"Назад": {"callback_data": back_cb}}, row_width=1)
            await _edit_and_cache(
                bot,
                message,
                user_id=user_id,
                screen_name=cache.normalize_screen_key(
                    f"disciplineWeekW {discipline_id} {week_delta} {list_page} {uwd}"
                    if uwd is not None
                    else f"disciplineWeek {discipline_id} {week_delta} {list_page}"
                ),
                text=text,
                reply_markup=markup,
            )
            return

        raw = None
        try:
            raw = await client.disciplines.get_discipline(discipline_id)
        except (RuzHttpError, ValueError) as e:
            logger.error("discipline get failed: %s", e)
    title = ""
    if raw is not None:
        title = raw.get("name") or ""

    last_update = datetime.now().strftime("%d.%m %H:%M:%S")
    if is_dangerous_criminal(user_id):
        temp = criminal_format_week_message(base, lessons)
    else:
        temp = commands._format_week_message(base, lessons)
    header = _commands_escape(f"📚 {title}\n\n") if title else ""
    reply_message = (
        header
        + temp
        + "\n\n"
        + _commands_escape(f"Последнее обновление: {last_update}")
    )
    reply_message = reply_message.replace("преподавател", "преподаватель")

    prev_w = week_delta - 1
    next_w = week_delta + 1
    markup = quick_markup(
        {
            "Пред. нед.": {"callback_data": week_line(prev_w)},
            "Назад": {"callback_data": back_cb},
            "След. нед.": {"callback_data": week_line(next_w)},
        },
        row_width=3,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"disciplineWeekW {discipline_id} {week_delta} {list_page} {uwd}"
            if uwd is not None
            else f"disciplineWeek {discipline_id} {week_delta} {list_page}"
        ),
        text=reply_message,
        reply_markup=markup,
        parse_mode="MarkdownV2",
    )


async def week_teachers_list_command(
    bot, message, user_week_delta: int, page: int, *, user_id: int
) -> None:
    async with ruz_client() as client:
        base = datetime.today() + timedelta(weeks=user_week_delta)
        try:
            lessons = await cache.get_or_load_week_lessons(
                user_id,
                base.date(),
                lambda anchor_date: client.schedule.get_user_week(user_id, anchor_date),
            )
        except RuzHttpError as e:
            logger.error("week schedule for weekTeachersList: %s", e)
            text = _commands_escape(
                f"Не удалось загрузить расписание: HTTP {e.status_code}"
            )
            markup = quick_markup(
                {"Назад": {"callback_data": f"parseWeek {user_week_delta}"}},
                row_width=1,
            )
            await _edit_and_cache(
                bot,
                message,
                user_id=user_id,
                screen_name=cache.normalize_screen_key(
                    f"weekTeachersList {user_week_delta} {page}"
                ),
                text=text,
                reply_markup=markup,
            )
            return
    lessons = lessons or []

    pairs = _unique_lecturers_from_lessons(lessons)
    if not pairs:
        markup = quick_markup(
            {"Назад к неделе": {"callback_data": f"parseWeek {user_week_delta}"}},
            row_width=1,
        )
        await _edit_and_cache(
            bot,
            message,
            user_id=user_id,
            screen_name=cache.normalize_screen_key(
                f"weekTeachersList {user_week_delta} {page}"
            ),
            text="На этой неделе нет занятий с известным преподавателем.",
            reply_markup=markup,
        )
        return

    pages = max(1, math.ceil(len(pairs) / _PAGE_SIZE))
    page = page % pages
    start = page * _PAGE_SIZE
    display = pairs[start : start + _PAGE_SIZE]

    markup = types.InlineKeyboardMarkup()
    for pair in _chunk_list(display, 2):
        row = [
            types.InlineKeyboardButton(
                _btn_label("👤", (remove_position(title))),
                callback_data=f"weekTeacherOpen {lid} {user_week_delta} {page}",
            )
            for lid, title in pair
        ]
        markup.row(*row)

    prev_p = (page - 1) % pages
    next_p = (page + 1) % pages
    markup.row(
        types.InlineKeyboardButton(
            "⬅️ Пред. стр.", callback_data=f"weekTeachersList {user_week_delta} {prev_p}"
        ),
        types.InlineKeyboardButton(
            "🏠 Назад", callback_data=f"parseWeek {user_week_delta}"
        ),
        types.InlineKeyboardButton(
            "➡️ След. стр.", callback_data=f"weekTeachersList {user_week_delta} {next_p}"
        ),
    )

    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"weekTeachersList {user_week_delta} {page}"
        ),
        text="Преподаватели на выбранной неделе (по вашему расписанию):",
        reply_markup=markup,
    )


async def week_teacher_open_command(
    bot,
    message,
    lecturer_id: int,
    user_week_delta: int,
    list_page: int,
    *,
    user_id: int,
) -> None:
    async with ruz_client() as client:
        try:
            lec = await client.lecturers.get_lecturer(lecturer_id)
        except ValueError:
            logger.error("lecturer not found: %s", lecturer_id)
            return
        except RuzHttpError as e:
            logger.error("lecturer get failed: %s", e)
            return
    body = (
        f"👤 Преподаватель\n"
        f"🆔 ID: {lec.get('id')}\n"
        f"📛 Имя: {lec.get('full_name', '')}\n"
        f"🎓 Должность: {lec.get('rank', '')}"
    )
    markup = quick_markup(
        {
            "📅 Сегодня": {
                "callback_data": f"lecturerDayW {lecturer_id} 0 {list_page} {user_week_delta}"
            },
            "📅 Эта неделя": {
                "callback_data": f"lecturerWeekW {lecturer_id} {user_week_delta} {list_page} {user_week_delta}"
            },
            "К списку": {
                "callback_data": f"weekTeachersList {user_week_delta} {list_page}"
            },
            "🏠 Главная": {"callback_data": "start"},
        },
        row_width=2,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"weekTeacherOpen {lecturer_id} {user_week_delta} {list_page}"
        ),
        text=_commands_escape(body),
        reply_markup=markup,
    )


async def week_subjects_list_command(
    bot, message, user_week_delta: int, page: int, *, user_id: int
) -> None:
    async with ruz_client() as client:
        base = datetime.today() + timedelta(weeks=user_week_delta)
        try:
            lessons = await cache.get_or_load_week_lessons(
                user_id,
                base.date(),
                lambda anchor_date: client.schedule.get_user_week(user_id, anchor_date),
            )
        except RuzHttpError as e:
            logger.error("week schedule for weekSubjectsList: %s", e)
            text = _commands_escape(
                f"Не удалось загрузить расписание: HTTP {e.status_code}"
            )
            markup = quick_markup(
                {"Назад": {"callback_data": f"parseWeek {user_week_delta}"}},
                row_width=1,
            )
            await _edit_and_cache(
                bot,
                message,
                user_id=user_id,
                screen_name=cache.normalize_screen_key(
                    f"weekSubjectsList {user_week_delta} {page}"
                ),
                text=text,
                reply_markup=markup,
            )
            return
    lessons = lessons or []

    pairs = _unique_disciplines_from_lessons(lessons)
    if not pairs:
        markup = quick_markup(
            {"Назад к неделе": {"callback_data": f"parseWeek {user_week_delta}"}},
            row_width=1,
        )
        await _edit_and_cache(
            bot,
            message,
            user_id=user_id,
            screen_name=cache.normalize_screen_key(
                f"weekSubjectsList {user_week_delta} {page}"
            ),
            text="На этой неделе нет предметов с известным ID в расписании.",
            reply_markup=markup,
        )
        return

    pages = max(1, math.ceil(len(pairs) / _PAGE_SIZE))
    page = page % pages
    start = page * _PAGE_SIZE
    display = pairs[start : start + _PAGE_SIZE]

    markup = types.InlineKeyboardMarkup()
    for pair in _chunk_list(display, 2):
        row = [
            types.InlineKeyboardButton(
                _btn_label("📚", title),
                callback_data=f"weekSubjectOpen {did} {user_week_delta} {page}",
            )
            for did, title in pair
        ]
        markup.row(*row)

    prev_p = (page - 1) % pages
    next_p = (page + 1) % pages
    markup.row(
        types.InlineKeyboardButton(
            "⬅️ Пред. стр.", callback_data=f"weekSubjectsList {user_week_delta} {prev_p}"
        ),
        types.InlineKeyboardButton(
            "🏠 Назад", callback_data=f"parseWeek {user_week_delta}"
        ),
        types.InlineKeyboardButton(
            "➡️ След. стр.", callback_data=f"weekSubjectsList {user_week_delta} {next_p}"
        ),
    )

    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"weekSubjectsList {user_week_delta} {page}"
        ),
        text="Предметы на выбранной неделе (по вашему расписанию):",
        reply_markup=markup,
    )


async def week_subject_open_command(
    bot,
    message,
    discipline_id: int,
    user_week_delta: int,
    list_page: int,
    *,
    user_id: int,
) -> None:
    async with ruz_client() as client:
        try:
            d = await client.disciplines.get_discipline(discipline_id)
        except (RuzHttpError, ValueError) as e:
            logger.error("discipline get failed: %s", e)
            return
    exam = d.get("examtype") or "—"
    body = (
        f"📚 Предмет\n"
        f"🆔 ID: {d.get('id')}\n"
        f"📖 Название: {d.get('name', '')}\n"
        f"📝 Контроль: {exam}"
    )
    markup = quick_markup(
        {
            "📅 Сегодня": {
                "callback_data": f"disciplineDayW {discipline_id} 0 {list_page} {user_week_delta}"
            },
            "📅 Эта неделя": {
                "callback_data": f"disciplineWeekW {discipline_id} {user_week_delta} {list_page} {user_week_delta}"
            },
            "К списку": {
                "callback_data": f"weekSubjectsList {user_week_delta} {list_page}"
            },
            "🏠 Главная": {"callback_data": "start"},
        },
        row_width=2,
    )
    await _edit_and_cache(
        bot,
        message,
        user_id=user_id,
        screen_name=cache.normalize_screen_key(
            f"weekSubjectOpen {discipline_id} {user_week_delta} {list_page}"
        ),
        text=_commands_escape(body),
        reply_markup=markup,
    )
