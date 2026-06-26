"""Message and callback handlers. Registered via register_all()."""

import logging
import random

from maxapi import Bot, Dispatcher
from maxapi.enums.parse_mode import ParseMode
from maxapi.types import (
    BotStarted, CallbackButton, Command, CommandStart,
    LinkButton, MessageCallback, MessageCreated,
)
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from library_data import (
    CONTACTS_TEXT, MENU, REGISTER_FAQ, WELCOME_TEXT,
    branch_by_id,
)
from bot.keyboards import (
    afisha_kb, back_to_main_kb, books_kb, branch_detail_kb,
    branches_list_kb, contacts_kb, hours_kb, main_menu_kb,
    nearest_loc_kb, nearest_res_kb, pushkin_kb, rec_kb, register_kb,
)
from bot.render import (
    local_rec, render_afisha, render_books_menu,
    render_branch_detail, render_hours, render_nearest, render_pushkin,
)
from bot.services import (
    MAX_READING_QUERY_CHARS, moscow_now, load_local_books,
    default_recs, find_books, choose_books, prefer_clean, is_generic,
    en_reading, dis_reading, in_reading, extract_location,
    _should_menu, _mkeys,
)

log = logging.getLogger("library-bot")


async def _edit(cb, text: str, kb) -> None:
    try:
        await cb.message.edit(text=text, attachments=[kb], parse_mode=ParseMode.HTML)
    except Exception:
        log.exception("edit failed, sending new message instead")
        try:
            await cb.message.answer(text=text, attachments=[kb], parse_mode=ParseMode.HTML)
        except Exception:
            log.exception("answer also failed")
            try:
                await cb.answer(notification="Не удалось обновить меню, нажмите /menu")
            except Exception:
                pass


async def _send_menu_bot(bot: Bot, cid, uid=None) -> None:
    if not _should_menu(cid, uid):
        return
    await bot.send_message(
        chat_id=cid, text=WELCOME_TEXT,
        attachments=[main_menu_kb(MENU)],
        parse_mode=ParseMode.HTML,
    )


async def _answer_menu(ev) -> None:
    try:
        cid, uid = ev.get_ids()
    except Exception:
        cid, uid = None, None
    if not _should_menu(cid, uid):
        return
    await ev.message.answer(
        text=WELCOME_TEXT,
        attachments=[main_menu_kb(MENU)],
        parse_mode=ParseMode.HTML,
    )


# ── dispatch table ───────────────────────────────────────────────

ROUTES = {
    "menu:main":      lambda: (WELCOME_TEXT, main_menu_kb(MENU)),
    "menu:branches":  lambda: ("🏛 <b>Библиотеки ЦБС г. Волгодонска</b>\n\nВыберите библиотеку:", branches_list_kb()),
    "menu:hours":     lambda: (render_hours(), hours_kb()),
    "menu:events":    lambda: (render_afisha(), afisha_kb()),
    "menu:pushkin":   lambda: (render_pushkin(), pushkin_kb()),
    "menu:register":  lambda: (REGISTER_FAQ, register_kb()),
    "menu:books":     lambda: (render_books_menu(), books_kb()),
}


async def _dispatch(cb, payload: str) -> None:
    if payload == "close":
        try:
            await cb.message.delete()
        except Exception:
            log.exception("delete error")
        return

    if payload.startswith("branch:"):
        bid = payload.split(":", 1)[1]
        br = branch_by_id(bid)
        if not br:
            await cb.answer(notification="Не найдена")
            return
        await _edit(cb, render_branch_detail(br, moscow_now()), branch_detail_kb(br))
        return

    if payload == "menu:random_book":
        en_reading(cb)
        recs = load_local_books()
        books = default_recs(recs, limit=50)
        if not books:
            await _edit(cb, "Не получилось выбрать книгу.", books_kb())
            return
        book = random.choice(books)
        await _edit(cb, local_rec("случайная книга", [book]), rec_kb([book], random_mode=True))
        return

    if payload == "menu:contacts":
        await _edit(cb, CONTACTS_TEXT, contacts_kb())
        return

    if payload == "menu:nearest":
        await _edit(cb,
                    "📍 Отправьте ваше местоположение, чтобы найти ближайшую библиотеку.",
                    nearest_loc_kb())
        return

    if payload not in ROUTES:
        await cb.answer(notification="Неизвестная команда")
        return

    if payload == "menu:main":
        dis_reading(cb)
    if payload == "menu:books":
        en_reading(cb)

    text, kb = ROUTES[payload]()
    await _edit(cb, text, kb)


# ── registration ─────────────────────────────────────────────────

def register_all(bot: Bot, dp: Dispatcher) -> None:
    @dp.bot_started()
    async def on_bot_started(ev: BotStarted) -> None:
        uid = getattr(getattr(ev, "user", None), "user_id", None)
        log.info("[started] chat=%s user=%s", ev.chat_id, uid)
        await _send_menu_bot(bot, ev.chat_id, uid)

    @dp.message_created(CommandStart())
    async def on_start(ev: MessageCreated) -> None:
        await _answer_menu(ev)

    @dp.message_created(Command("menu"))
    async def on_menu(ev: MessageCreated) -> None:
        await _answer_menu(ev)

    @dp.message_created(Command("help"))
    async def on_help(ev: MessageCreated) -> None:
        await ev.message.answer(
            text="ℹ️ <b>Помощь</b>\n\nКоманды:\n• /start — меню\n• /menu — меню\n• /help — помощь\n\nНавигация — через кнопки 👇",
            attachments=[main_menu_kb(MENU)],
            parse_mode=ParseMode.HTML,
        )

    @dp.message_created(Command("catalog"))
    async def on_catalog(ev: MessageCreated) -> None:
        from library_data import CATALOG_URL
        b = InlineKeyboardBuilder()
        b.row(LinkButton(text="📚 Открыть каталог", url=CATALOG_URL))
        b.row(CallbackButton(text="🏠 Главная", payload="menu:main"))
        await ev.message.answer(
            text="📚 <b>Электронные каталоги ЦБС</b>\n\n• Общий каталог\n• Периодика\n• Краеведение\n• ЛитРес\n• Атомная коллекция\n\n📞 +7 (8639) 22-60-21",
            attachments=[b.as_markup()],
            parse_mode=ParseMode.HTML,
        )

    @dp.message_created()
    async def on_text(ev: MessageCreated) -> None:
        txt = (ev.message.body.text or "").strip()
        if txt.startswith("/"):
            return

        loc = extract_location(ev)
        if loc:
            lat, lon = loc
            text, br, _ = render_nearest(lat, lon)
            if br:
                await ev.message.answer(
                    text=text,
                    attachments=[nearest_res_kb(lat, lon, br)],
                    parse_mode=ParseMode.HTML,
                )
            else:
                await ev.message.answer(
                    text=text,
                    attachments=[branches_list_kb()],
                    parse_mode=ParseMode.HTML,
                )
            return

        if not in_reading(ev):
            await ev.message.answer(
                text="Я пока отвечаю на текст только в разделе <b>Что почитать</b>.\nНажмите кнопку ниже.",
                attachments=[books_kb()],
                parse_mode=ParseMode.HTML,
            )
            return

        if not txt:
            await ev.message.answer(
                text=render_books_menu(),
                attachments=[books_kb()],
                parse_mode=ParseMode.HTML,
            )
            return
        if len(txt) > MAX_READING_QUERY_CHARS:
            await ev.message.answer(
                text=f"Слишком длинно. До {MAX_READING_QUERY_CHARS} символов.",
                attachments=[books_kb()],
                parse_mode=ParseMode.HTML,
            )
            return

        recs = load_local_books()
        if is_generic(txt):
            books = default_recs(recs)
        else:
            found = choose_books(find_books(txt, recs, limit=40), limit=20)
            books = prefer_clean(txt, found)
        if not books:
            await ev.message.answer(
                text="По этому запросу нет книг с аннотацией. Откройте каталог или «Случайная книга».",
                attachments=[books_kb()],
                parse_mode=ParseMode.HTML,
            )
            return
        await ev.message.answer(
            text=local_rec(txt, books),
            attachments=[rec_kb(books)],
            parse_mode=ParseMode.HTML,
        )

    @dp.message_callback()
    async def on_callback(cb: MessageCallback) -> None:
        p = cb.callback.payload or ""
        log.info("callback payload=%r user=%s", p, cb.callback.user.user_id)
        try:
            await _dispatch(cb, p)
        except Exception:
            log.exception("callback error")
            try:
                await cb.answer(notification="Ошибка, попробуйте ещё раз")
            except Exception:
                pass
