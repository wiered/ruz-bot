import logging
import re

from telebot.async_telebot import AsyncTeleBot
from telebot.util import quick_markup

from ruzbot import cache
from ruzbot import commands, search_handlers
from ruzbot.utils import getRandomGroup, ruz_client
from ruzclient.errors import RuzHttpError


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


async def callbackFilter(call) -> bool:
    logger.debug(f"callbackFilter called for call_id={call.id}")
    return True


async def textCallbackHandler(callback, bot: AsyncTeleBot):
    """
    Текст: имя группы (паттерны как раньше) или одна цифра для подгруппы.
    """
    logger.info(
        f"textCallbackHandler invoked: user_id={callback.from_user.id}, text={callback.text!r}"
    )
    patterns = [r"\w+\d+", r"\w+-\w+\d+", r"\d"]
    match tuple(i for i, pattern in enumerate(patterns) if re.match(pattern, callback.text or "")):
        case (0,) | (1,):
            group_name = callback.text
            logger.debug(f"Group selection text detected: {group_name}")
            async with ruz_client() as client:
                groups_list = await client.groups.search_groups_by_name(group_name)
            if not groups_list:
                logger.warning(f"No groups found for '{group_name}'")
                await bot.reply_to(
                    callback,
                    f"❌ Указано недопустимое имя группы! Попробуйте ещё раз, например: {getRandomGroup()}",
                )
                return

            markup = quick_markup(
                {
                    g["name"]: {"callback_data": f"setGroup {g['oid']} {g['name']}"}
                    for g in groups_list
                },
                row_width=1,
            )

            logger.debug(f"Replying with {len(groups_list)} group options")
            await bot.reply_to(callback, "Выбери группу", reply_markup=markup)

        case (2,):
            sub_group_number = int(callback.text)
            if sub_group_number not in (0, 1, 2):
                await bot.reply_to(
                    callback,
                    "Для подгруппы допустимы только 0, 1 или 2. Введите одну цифру.",
                )
                return
            uid = callback.from_user.id
            async with ruz_client() as client:
                try:
                    u = await client.users.get_by_id(uid)
                except RuzHttpError as e:
                    if e.status_code == 404:
                        u = None
                    else:
                        raise
            if u is None:
                await bot.reply_to(
                    callback,
                    "Сначала выберите группу через «Установить группу» или /start.",
                )
                return
            prev = u.get("subgroup")
            logger.debug(f"Sub-group set/update: {sub_group_number} for user_id={uid}")
            await commands.updateUserSubGroup(uid, sub_group_number)
            msg = "Подгруппа установлена." if prev is None else "Подгруппа обновлена."
            message = await bot.reply_to(callback, msg)
            await commands.sendProfileCommand(bot, message, user_id=uid)

        case _:
            logger.warning(f"Wrong case in textCallbackHandler: {callback.text!r}")


async def buttonsCallback(callback, bot: AsyncTeleBot):
    logger.info(
        f"buttonsCallback invoked: user_id={callback.from_user.id}, data={callback.data!r}"
    )
    uid = callback.from_user.id

    if callback.data:
        if await cache.replay_screen_snapshot(bot, callback.message, uid, callback.data):
            await bot.answer_callback_query(callback.id)
            return

    match callback.data.split(" "):
        case ["start"]:
            logger.debug("Button 'start' pressed")
            await commands.backCommand(bot, callback.message, user_id=uid)

        case ["parseDay", *args]:
            date_arg = args[0] if args else None
            logger.debug(f"Button 'parseDay' pressed with arg={date_arg}")
            await commands.dateCommand(bot, callback.message, date_arg, user_id=uid)

        case ["parseWeek", *args]:
            date_arg = args[0] if args else None
            logger.debug(f"Button 'parseWeek' pressed with arg={date_arg}")
            await commands.weekCommand(bot, callback.message, date_arg, user_id=uid)

        case ["showProfile"]:
            logger.debug("Button 'showProfile' pressed")
            await commands.sendProfileCommand(bot, callback.message, user_id=uid)

        case ["configureGroup"]:
            logger.debug("Button 'configureGroup' pressed")
            await commands.setGroupCommand(bot, callback.message, user_id=uid)

        case ["setGroup", *rest]:
            if not rest:
                logger.error("setGroup callback missing oid")
                return
            try:
                group_oid = int(rest[0])
            except ValueError:
                logger.error(f"Invalid setGroup oid: {rest[0]!r}")
                return
            group_label = " ".join(rest[1:]).strip() if len(rest) > 1 else ""
            logger.debug(
                f"Button 'setGroup' pressed with group_oid={group_oid}, label={group_label!r}"
            )
            await commands.setGroup(bot, callback, group_oid, group_label)
            await bot.answer_callback_query(callback.id)
            await commands.setSubGroupCommand(bot, callback.message, user_id=uid)

        case ["searchTeacher"]:
            # await search_handlers.search_teacher_list_command(bot, callback.message, 0, user_id=uid)
            await commands.search_menu_stub_command(
                bot,
                callback.message,
                user_id=uid,
                screen_name=callback.data,
            )

        case ["teacherPage", page_s]:
            try:
                p = int(page_s)
            except ValueError:
                logger.error(f"Invalid teacherPage: {page_s!r}")
                return
            await search_handlers.search_teacher_list_command(bot, callback.message, p, user_id=uid)

        case ["teacherCard", lid_s, page_s]:
            try:
                lid = int(lid_s)
                lp = int(page_s)
            except ValueError:
                logger.error(f"Invalid teacherCard: {lid_s!r} {page_s!r}")
                return
            await search_handlers.teacher_card_command(bot, callback.message, lid, lp, user_id=uid)

        case ["lecturerDay", lid_s, dd_s, lp_s]:
            try:
                lid = int(lid_s)
                dd = int(dd_s)
                lp = int(lp_s)
            except ValueError:
                logger.error(f"Invalid lecturerDay: {callback.data!r}")
                return
            await search_handlers.lecturer_day_command(bot, callback.message, lid, dd, lp, user_id=uid)

        case ["lecturerWeek", lid_s, wd_s, lp_s]:
            try:
                lid = int(lid_s)
                wd = int(wd_s)
                lp = int(lp_s)
            except ValueError:
                logger.error(f"Invalid lecturerWeek: {callback.data!r}")
                return
            await search_handlers.lecturer_week_command(bot, callback.message, lid, wd, lp, user_id=uid)

        case ["searchSubject"]:
            # await search_handlers.search_subject_list_command(bot, callback.message, 0, user_id=uid)
            await commands.search_menu_stub_command(
                bot,
                callback.message,
                user_id=uid,
                screen_name=callback.data,
            )

        case ["subjectPage", page_s]:
            try:
                p = int(page_s)
            except ValueError:
                logger.error(f"Invalid subjectPage: {page_s!r}")
                return
            await search_handlers.search_subject_list_command(bot, callback.message, p, user_id=uid)

        case ["subjectCard", did_s, page_s]:
            try:
                did = int(did_s)
                lp = int(page_s)
            except ValueError:
                logger.error(f"Invalid subjectCard: {did_s!r} {page_s!r}")
                return
            await search_handlers.subject_card_command(bot, callback.message, did, lp, user_id=uid)

        case ["disciplineDay", did_s, dd_s, lp_s]:
            try:
                did = int(did_s)
                dd = int(dd_s)
                lp = int(lp_s)
            except ValueError:
                logger.error(f"Invalid disciplineDay: {callback.data!r}")
                return
            await search_handlers.discipline_day_command(bot, callback.message, did, dd, lp, user_id=uid)

        case ["disciplineWeek", did_s, wd_s, lp_s]:
            try:
                did = int(did_s)
                wd = int(wd_s)
                lp = int(lp_s)
            except ValueError:
                logger.error(f"Invalid disciplineWeek: {callback.data!r}")
                return
            await search_handlers.discipline_week_command(bot, callback.message, did, wd, lp, user_id=uid)

        case ["weekTeachersList", uwd_s, page_s]:
            try:
                uwd = int(uwd_s)
                p = int(page_s)
            except ValueError:
                logger.error(f"Invalid weekTeachersList: {callback.data!r}")
                return
            await search_handlers.week_teachers_list_command(bot, callback.message, uwd, p, user_id=uid)

        case ["weekSubjectsList", uwd_s, page_s]:
            try:
                uwd = int(uwd_s)
                p = int(page_s)
            except ValueError:
                logger.error(f"Invalid weekSubjectsList: {callback.data!r}")
                return
            await search_handlers.week_subjects_list_command(bot, callback.message, uwd, p, user_id=uid)

        case ["weekTeacherOpen", lid_s, uwd_s, page_s]:
            try:
                lid = int(lid_s)
                uwd = int(uwd_s)
                lp = int(page_s)
            except ValueError:
                logger.error(f"Invalid weekTeacherOpen: {callback.data!r}")
                return
            await search_handlers.week_teacher_open_command(bot, callback.message, lid, uwd, lp, user_id=uid)

        case ["weekSubjectOpen", did_s, uwd_s, page_s]:
            try:
                did = int(did_s)
                uwd = int(uwd_s)
                lp = int(page_s)
            except ValueError:
                logger.error(f"Invalid weekSubjectOpen: {callback.data!r}")
                return
            await search_handlers.week_subject_open_command(bot, callback.message, did, uwd, lp, user_id=uid)

        case ["lecturerDayW", lid_s, dd_s, lp_s, uwd_s]:
            try:
                lid = int(lid_s)
                dd = int(dd_s)
                lp = int(lp_s)
                uwd = int(uwd_s)
            except ValueError:
                logger.error(f"Invalid lecturerDayW: {callback.data!r}")
                return
            await search_handlers.lecturer_day_command(
                bot, callback.message, lid, dd, lp, user_id=uid, from_user_week=uwd
            )

        case ["lecturerWeekW", lid_s, swd_s, lp_s, uwd_s]:
            try:
                lid = int(lid_s)
                swd = int(swd_s)
                lp = int(lp_s)
                uwd = int(uwd_s)
            except ValueError:
                logger.error(f"Invalid lecturerWeekW: {callback.data!r}")
                return
            await search_handlers.lecturer_week_command(
                bot, callback.message, lid, swd, lp, user_id=uid, from_user_week=uwd
            )

        case ["disciplineDayW", did_s, dd_s, lp_s, uwd_s]:
            try:
                did = int(did_s)
                dd = int(dd_s)
                lp = int(lp_s)
                uwd = int(uwd_s)
            except ValueError:
                logger.error(f"Invalid disciplineDayW: {callback.data!r}")
                return
            await search_handlers.discipline_day_command(
                bot, callback.message, did, dd, lp, user_id=uid, from_user_week=uwd
            )

        case ["disciplineWeekW", did_s, swd_s, lp_s, uwd_s]:
            try:
                did = int(did_s)
                swd = int(swd_s)
                lp = int(lp_s)
                uwd = int(uwd_s)
            except ValueError:
                logger.error(f"Invalid disciplineWeekW: {callback.data!r}")
                return
            await search_handlers.discipline_week_command(
                bot, callback.message, did, swd, lp, user_id=uid, from_user_week=uwd
            )

        case _:
            logger.warning(f"Unsupported callback data: {callback.data!r}")


def register_handlers(bot: AsyncTeleBot):
    logger.info("Registering handlers with the bot")
    bot.register_message_handler(textCallbackHandler, pass_bot=True)
    bot.register_callback_query_handler(callback=buttonsCallback, func=callbackFilter, pass_bot=True)
    logger.info("Handlers registered successfully")
