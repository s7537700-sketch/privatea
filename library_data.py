import json
import re
from calendar import monthrange
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import quote


CONTENT_PATH = Path(__file__).with_name("library_content.json")


def _load_content() -> dict:
    with CONTENT_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def _normalize_schedule(branch: dict) -> dict:
    schedule = branch.get("schedule")
    if schedule is None:
        return branch
    branch["schedule"] = {
        int(day): tuple(hours) if hours is not None else None
        for day, hours in schedule.items()
    }
    return branch


# === Парсер летнего расписания ===

_DAY_NAMES = {
    "понедельник": 0, "понедельника": 0, "понедельники": 0, "пн": 0,
    "вторник": 1, "вторника": 1, "вторники": 1, "вт": 1,
    "среда": 2, "среду": 2, "среды": 2, "ср": 2,
    "четверг": 3, "четверга": 3, "четверги": 3, "чт": 3,
    "пятница": 4, "пятницу": 4, "пятницы": 4, "пт": 4,
    "суббота": 5, "субботу": 5, "субботы": 5, "сб": 5,
    "воскресенье": 6, "воскресенья": 6, "воскресенью": 6, "вс": 6,
}

_TIME_RE = re.compile(r"(\d{1,2}:\d{2})\s*[–—\-]\s*(\d{1,2}:\d{2})")
_DAY_RANGE_RE = re.compile(r"^([А-Яа-яЁёA-Za-z]+)\s*[–—\-]\s*([А-Яа-яЁёA-Za-z]+)$")


def _norm_time(t: str) -> str:
    h, m = t.split(":")
    return f"{int(h):02d}:{m}"


def _parse_time_range(text: str) -> tuple[str, str] | None:
    m = _TIME_RE.search(text)
    if not m:
        return None
    return (_norm_time(m.group(1)), _norm_time(m.group(2)))


def _parse_day(token: str) -> int | None:
    return _DAY_NAMES.get(token.strip().lower().rstrip(",.;:"))


def _parse_day_list(text: str) -> list[int]:
    text = text.strip().lower()
    rng = _DAY_RANGE_RE.match(text)
    if rng:
        d1 = _parse_day(rng.group(1))
        d2 = _parse_day(rng.group(2))
        if d1 is not None and d2 is not None:
            if d1 <= d2:
                return list(range(d1, d2 + 1))
            return list(range(d1, 7)) + list(range(0, d2 + 1))
    out: list[int] = []
    for tok in re.split(r"[,\s/]+|\bи\b", text):
        wd = _parse_day(tok)
        if wd is not None and wd not in out:
            out.append(wd)
    return out


def parse_summer_schedule(text: str) -> dict | None:
    """Парсит текст летнего расписания.

    Возвращает {schedule, sanitary_weekday, sanitary_last_day}
    или None если не удалось распознать базовый интервал.
    """
    if not text:
        return None
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]
    if not lines:
        return None
    base = _parse_time_range(lines[0])
    if not base:
        return None
    schedule: dict[int, tuple[str, str] | None] = {i: base for i in range(7)}
    sanitary_weekday: int | None = None
    sanitary_last_day = False

    for ln in lines[1:]:
        low = ln.lower()

        if low.startswith("санитарный день") or low.startswith("санитарный"):
            after = ln.split(":", 1)[-1].strip().lower() if ":" in ln else low
            if "последний день" in after or "последнего дня" in after:
                sanitary_last_day = True
            else:
                m = re.search(r"последн(?:ий|яя|юю|его|ей|ие|ими)\s+([а-яё]+)", after)
                if m:
                    wd = _parse_day(m.group(1))
                    if wd is not None:
                        sanitary_weekday = wd
            continue

        if low.startswith("выходн"):
            after = ln.split(":", 1)[-1] if ":" in ln else ""
            for wd in _parse_day_list(after):
                schedule[wd] = None
            continue

        m = re.match(r"^([^:]+):\s*(.+)$", ln)
        if m:
            day_part, val_part = m.group(1), m.group(2)
            day_idxs = _parse_day_list(day_part)
            if not day_idxs:
                continue
            if "выходн" in val_part.lower():
                for wd in day_idxs:
                    schedule[wd] = None
            else:
                rng = _parse_time_range(val_part)
                if rng:
                    for wd in day_idxs:
                        schedule[wd] = rng

    return {
        "schedule": schedule,
        "sanitary_weekday": sanitary_weekday,
        "sanitary_last_day": sanitary_last_day,
    }


def _normalize_summer(branch: dict) -> dict:
    text = branch.get("summer_schedule")
    if isinstance(text, str) and text.strip():
        parsed = parse_summer_schedule(text)
        if parsed:
            branch["summer_schedule_struct"] = parsed["schedule"]
            branch["summer_sanitary_weekday"] = parsed["sanitary_weekday"]
            branch["summer_sanitary_last_day"] = parsed["sanitary_last_day"]
    return branch


CONTENT = _load_content()

BRANCHES = [_normalize_summer(_normalize_schedule(branch)) for branch in CONTENT["branches"]]
EVENTS = CONTENT.get("events", [])
MENU = CONTENT.get("menu", [])

URLS = CONTENT["urls"]
WEBSITE_URL = URLS["website"]
VK_URL = URLS["vk"]
CATALOG_URL = URLS["catalog"]
CONTACTS_PAGE_URL = URLS["contacts_page"]
AFISHA_VK_URL = URLS["afisha_vk"]
AFISHA_SITE_URL = URLS.get("afisha_site", "https://vdonlib.ru/event/")
PUSHKIN_KASSIR_URL = URLS.get("pushkin_kassir", "")

TEXTS = CONTENT["texts"]
CONTACTS_TEXT = TEXTS["contacts"]
REGISTER_FAQ = TEXTS["register_faq"]
SUMMER_SCHEDULE_TEXT = TEXTS.get("summer_schedule", "")
WELCOME_TEXT = TEXTS["welcome"]


def branch_by_id(bid: str) -> dict | None:
    return next((branch for branch in BRANCHES if branch["id"] == bid), None)


def event_by_id(eid: str) -> dict | None:
    return next((event for event in EVENTS if event["id"] == eid), None)


def pushkin_events() -> list[dict]:
    return [event for event in EVENTS if event.get("pushkin")]


def yandex_map_url(address: str) -> str:
    return f"https://yandex.ru/maps/?text={quote(f'Волгодонск, {address}')}"


def is_summer_now(today: date | None = None) -> bool:
    """Возвращает True с 1 июня по 31 августа включительно (МСК)."""
    if today is None:
        today = date.today()
    return today.month in (6, 7, 8)


def branch_summer_schedule(branch: dict) -> str:
    """Текст летнего расписания для конкретной библиотеки."""
    return branch.get("summer_schedule") or ""


def branch_active_schedule(branch: dict, today: date | None = None):
    """Активное расписание на дату: летнее с июня по август, иначе обычное."""
    if today is None:
        today = date.today()
    if is_summer_now(today):
        summer = branch.get("summer_schedule_struct")
        if summer:
            return summer
    return branch.get("schedule")


def _last_weekday_of_month(year: int, month: int, weekday: int) -> date:
    _, days = monthrange(year, month)
    last = date(year, month, days)
    while last.weekday() != weekday:
        last -= timedelta(days=1)
    return last


def branch_is_sanitary_today(branch: dict, today: date | None = None) -> bool:
    """True если сегодня санитарный день филиала."""
    if today is None:
        today = date.today()

    if is_summer_now(today) and branch.get("summer_schedule_struct"):
        if branch.get("summer_sanitary_last_day"):
            _, days = monthrange(today.year, today.month)
            return today.day == days
        wd = branch.get("summer_sanitary_weekday")
        if wd is None:
            return False
        if today.weekday() != wd:
            return False
        return today == _last_weekday_of_month(today.year, today.month, wd)

    if branch.get("sanitary_day"):
        if today.weekday() != 2:
            return False
        return today == _last_weekday_of_month(today.year, today.month, 2)
    return False
