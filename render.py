"""Text rendering functions. Pure presentation — no side effects."""

import html as html_mod
import random
import re

from library_data import (
    AFISHA_SITE_URL, BRANCHES, PUSHKIN_KASSIR_URL,
    REGISTER_FAQ, WELCOME_TEXT, branch_by_id, is_summer_now,
    branch_active_schedule, branch_summer_schedule,
)
from bot.services import (
    WEEKDAYS_RU, MONTHS_RU_GEN, MONTHS_RU_SHORT,
    WEEKDAYS_SHORT, moscow_now, fmt_date_ru,
    branch_open_status, load_local_books, default_recs,
    find_books, choose_books, prefer_clean, is_generic,
    _book_branches, fmt_dist, nearest_branch,
)


def render_branch_detail(br: dict, now) -> str:
    phones_list = "\n".join(f"• {p}" for p in br["phones"])
    email = f"\n📧 E-mail: {br['email']}" if br.get("email") else ""
    note = f"\n\n<i>{br['note']}</i>" if br.get("note") else ""
    io, st = branch_open_status(br, now)
    em = {True: "🟢", False: "🔴"}.get(io, "⚪")
    today = now.date()
    summer_active = is_summer_now(today) and br.get("summer_schedule_struct") is not None
    active_sched = branch_active_schedule(br, today)
    hours_title = "🕐 <b>Часы работы (летнее расписание):</b>" if summer_active else "🕐 <b>Часы работы:</b>"
    summer_text = branch_summer_schedule(br)
    if summer_active:
        summer_block = "\n\n☀️ Сейчас действует <b>летнее расписание</b> (до 31 августа)."
    elif summer_text:
        summer_block = f"\n\n☀️ <b>Летнее расписание</b> (с 1 июня по 31 августа):\n<i>{summer_text}</i>"
    else:
        summer_block = ""
    return (
        f"🏛 <b>{br['name']}</b>\n\n"
        f"📍 {br['address']}\n📞 Телефон:\n{phones_list}{email}\n\n"
        f"{hours_title}\n{_format_schedule(active_sched)}\n\n{em} {st}"
        f"{summer_block}{note}"
    )


def render_books_menu() -> str:
    return (
        "📖 <b>Что почитать</b>\n\n"
        "Можно открыть каталог или написать здесь жанр/автора.\n\n"
        "<b>Доступные жанры:</b>\n"
        "детектив, фантастика, приключения, история, война, классика, "
        "психология, любовь, для детей, сказки, юмор, наука, биография\n\n"
        "🎲 Не знаете что выбрать? Нажмите «Случайная книга»."
    )


def render_afisha() -> str:
    return (
        "📅 <b>Афиша мероприятий</b>\n\n"
        "Актуальная афиша на официальных площадках ЦБС:\n\n"
        "• <b>Сайт</b> — полная программа с описаниями.\n"
        "• <b>ВК</b> — постеры, анонсы, фоторепортажи.\n\n"
        "<i>Нажмите на кнопку ниже.</i>"
    )


def render_pushkin() -> str:
    return (
        "🎟 <b>Пушкинская карта</b>\n\n"
        "По Пушкинской карте в библиотеках можно бесплатно посещать:\n"
        "• экскурсии, лекции, мастер-классы, концерты, спектакли, игры.\n\n"
        "<b>Как пользоваться:</b>\n"
        "1. Оформить карту на Госуслугах (14–22 лет).\n"
        "2. Найти мероприятие с отметкой «Пушкинская карта».\n"
        "3. Купить билет через кнопку ниже.\n\n"
        "📞 Подробнее: <b>+7 (8639) 22-68-76</b>"
    )


def render_hours() -> str:
    now = moscow_now()
    central = branch_by_id("central")
    io, st = branch_open_status(central, now)
    em = {True: "🟢", False: "🔴"}.get(io, "⚪")
    rows = []
    for br in BRANCHES:
        s, _ = branch_open_status(br, now)
        m = {True: "🟢", False: "🔴"}.get(s, "⚪")
        rows.append(f"{m} {br['short']}")
    return (
        f"🕐 <b>Работаем ли сейчас?</b>\n\n"
        f"МСК: {now.hour:02d}:{now.minute:02d} ({WEEKDAYS_RU[now.weekday()]}, {fmt_date_ru(now)})\n\n"
        f"<b>Модельная центральная библиотека (Ленина, 75):</b>\n{em} {st}\n\n"
        f"<b>Все филиалы:</b>\n" + "\n".join(rows)
        + "\n\n<i>Подробнее — «🏛 Библиотеки» → филиал.</i>"
    )


def _format_schedule(sched: dict | None) -> str:
    if sched is None:
        return "уточняйте по телефону"

    def ds(v):
        return "выходной" if v is None else f"{v[0]}–{v[1]}"

    days = [(WEEKDAYS_SHORT[i], ds(sched.get(i))) for i in range(7)]
    groups = []
    for s, v in days:
        if groups and groups[-1][1] == v:
            groups[-1][0].append(s)
        else:
            groups.append(([s], v))
    lines = []
    for dl, v in groups:
        lbl = dl[0] if len(dl) == 1 else (f"{dl[0]}, {dl[1]}" if len(dl) == 2 else f"{dl[0]}–{dl[-1]}")
        lines.append(f"{lbl}: {v}")
    return "\n".join(lines)


def render_nearest(lat: float, lon: float) -> tuple[str, dict, int] | tuple[str, None, None]:
    r = nearest_branch(lat, lon)
    if not r:
        return "Не получилось определить ближайшую библиотеку.", None, None
    br, m = r
    ph = ", ".join(html_mod.escape(p) for p in br.get("phones", [])) or "телефон не указан"
    text = (
        f"📍 Ближайшая: <b>{html_mod.escape(br['name'])}</b>\n\n"
        f"Адрес: {html_mod.escape(br['address'])}\nРасстояние: <b>{fmt_dist(m)}</b>\n"
        f"Телефон: {ph}\n\nМожно открыть маршрут или карту."
    )
    return text, br, m


# ── book rendering ───────────────────────────────────────────────

def local_rec(q: str, books: list[dict]) -> str:
    lines = [f"📖 <b>По запросу «{html_mod.escape(q.strip())}»</b>\n"]
    for i, b in enumerate(books, 1):
        t = html_mod.escape(str(b.get("title") or "Книга без названия"))
        a = str(b.get("author") or "").strip()
        hdr = f"<b>{t}</b>" + (f" — {html_mod.escape(a)}" if a else "")
        desc = _short_hook(b, q)
        branches = _book_branches(b)
        block = f"{i}. {hdr}\n\n{desc}"
        if branches:
            block += f"\n\n📍 Где взять: {html_mod.escape(branches)}"
        lines.append(block + "\n")
    return "\n".join(lines)


def _short_hook(book: dict, q: str) -> str:
    def ns(v):
        return re.sub(r"[ \t]+", " ", re.sub(r"\[[^\]]+\]", "", str(v or "")).replace("\xa0", " ")).strip(" .;:-\n\t")

    def cut(t):
        marks = (" Взять книгу", " Прочитать эту книгу", " Книгу можно взять",
                 " Информацию подготов", " Назад", " Для добавления комментария",
                 " Библиотеки:", " Язык:", " Страниц:", " Издательство:")
        s = re.sub(r"[ \t]+", " ", t)
        pos = -1
        for m in marks:
            p = s.find(m.strip())
            if p > 80 and (pos < 0 or p < pos):
                pos = p
        return s[:pos].strip(" .;:-") if pos > 0 else s

    BOOK_SECTIONS = ("О КНИГЕ И СЮЖЕТЕ:", "О КНИГЕ:", "О СЮЖЕТЕ:", "О ПРОИЗВЕДЕНИИ:",
                     "СЮЖЕТ:", "АННОТАЦИЯ:", "ОПИСАНИЕ:", "О РОМАНЕ:", "О ПОВЕСТИ:")
    AUTHOR_SECTIONS = ("ОБ АВТОРЕ:", "О АВТОРЕ:", "БИОГРАФИЯ АВТОРА:", "АВТОР:",
                       "ОБ АВТОРАХ:", "ИНФОРМАЦИЯ ОБ АВТОРЕ:")

    def find_book_section(text):
        upper = text.upper()
        for m in BOOK_SECTIONS:
            idx = upper.find(m)
            if idx < 0:
                continue
            after = text[idx + len(m):].strip()
            after_upper = after.upper()
            stops = AUTHOR_SECTIONS + (
                "БИБЛИОГРАФИЯ:", "ИЗДАТЕЛЬСТВО:", "ВЗЯТЬ КНИГУ",
                "ПРОЧИТАТЬ ЭТУ КНИГУ", "КНИГУ МОЖНО ВЗЯТЬ",
            )
            cut_at = len(after)
            for s in stops:
                p = after_upper.find(s)
                if p > 0 and p < cut_at:
                    cut_at = p
            section = after[:cut_at].strip()
            if len(section) > 40:
                return section
        return ""

    def strip_author_section(text):
        upper = text.upper()
        start = -1
        for m in AUTHOR_SECTIONS:
            idx = upper.find(m)
            if idx >= 0 and (start < 0 or idx < start):
                start = idx
        if start < 0:
            return text
        end = len(text)
        for m in BOOK_SECTIONS:
            idx = upper.find(m, start)
            if idx >= 0 and idx < end:
                end = idx
        return (text[:start] + text[end:]).strip()

    def collect_paras(raw_text, *, target=500, hard_limit=900):
        cleaned = strip_author_section(str(raw_text or ""))
        skip_prefixes = ("автор:", "издательство:", "год:", "страниц:", "язык:", "isbn:",
                         "взять книгу", "прочитать эту книгу", "книгу можно взять",
                         "назад", "для добавления комментария", "источник:",
                         "об авторе", "о авторе", "биография")
        skip_upper_markers = ("ОБ АВТОРЕ", "О АВТОРЕ", "БИОГРАФИЯ")
        raw_paras = [p.strip() for p in cleaned.split("\n") if p.strip()]
        clean = []
        seen = set()
        for p in raw_paras:
            c = ns(p)
            if len(c) < 30:
                continue
            low = c.lower()
            if any(low.startswith(w) for w in skip_prefixes):
                continue
            up = c.upper()
            if any(up.startswith(m) for m in skip_upper_markers):
                continue
            if c.endswith(":") and c.upper() == c and len(c) < 60:
                continue
            if c in seen:
                continue
            seen.add(c)
            clean.append(c)
        if not clean:
            return ""
        collected = []
        total = 0
        for p in clean:
            if total >= target and collected:
                break
            if total + len(p) > hard_limit and collected:
                break
            collected.append(p)
            total += len(p) + 2
        return "\n\n".join(collected)

    raw = book.get("raw_text") or book.get("description") or ""
    if not str(raw).strip():
        return "<i>Описание отсутствует</i>"

    section = find_book_section(str(raw))
    if section:
        return _smart_truncate(cut(ns(section)), 800)

    multi = collect_paras(raw, target=500, hard_limit=900)
    if multi and len(multi) > 100:
        return _smart_truncate(cut(multi), 800)

    desc = ns(book.get("description"))
    if desc and len(desc) > 50:
        return _smart_truncate(cut(desc), 700)

    return _smart_truncate(ns(raw), 700)


def _smart_truncate(text: str, limit: int = 600) -> str:
    if not text:
        return ""
    s = text.strip()
    if len(s) <= limit:
        return s
    cut_at = -1
    for ch in (".", "!", "?", "…"):
        p = s.rfind(ch, 0, limit)
        if p > cut_at:
            cut_at = p
    if cut_at >= int(limit * 0.5):
        return s[:cut_at + 1].strip()
    sp = s.rfind(" ", 0, limit)
    if sp > 0:
        return s[:sp].rstrip(" ,.;:-") + "…"
    return s[:limit].rstrip(" ,.;:-") + "…"
