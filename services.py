"""Shared utilities: time helpers, book search, location, keepalive."""

import html
import json
import logging
import math
import os
import random
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote

from library_data import (
    BRANCHES, branch_active_schedule, branch_by_id,
    branch_is_sanitary_today, is_summer_now,
)

log = logging.getLogger("library-bot")

# ── path & constants ────────────────────────────────────────────

PROJECT_DIR = Path(__file__).resolve().parent.parent
VDONLIB_PREVIEW_JSON = PROJECT_DIR / "vdonlib_books_preview.json"
MAX_BOOKS_FOR_AI = 5
MAX_READING_QUERY_CHARS = 100
LOCAL_BOOKS_CACHE: list[dict] | None = None
READING_MODE: set[tuple[str, int]] = set()

# ── time helpers ─────────────────────────────────────────────────

WEEKDAYS_SHORT = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
WEEKDAYS_RU = ["понедельник", "вторник", "среда", "четверг", "пятница", "суббота", "воскресенье"]
MONTHS_RU_GEN = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
MONTHS_RU_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


def fmt_date_ru(d: date) -> str:
    return f"{d.day} {MONTHS_RU_GEN[d.month - 1]} {d.year}"


def moscow_now() -> datetime:
    return datetime.utcnow() + timedelta(hours=3)


# ── schedule / status ────────────────────────────────────────────

def _h2m(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def branch_open_status(br: dict, now: datetime) -> tuple[bool | None, str]:
    sched = branch_active_schedule(br, now.date())
    if sched is None:
        return None, "Расписание уточняйте по телефону или в ВК."
    if branch_is_sanitary_today(br, now.date()):
        return False, "Сегодня <b>санитарный день</b>."
    w = now.weekday()
    t = sched.get(w)
    if t is None:
        return False, f"Сегодня ({WEEKDAYS_RU[w]}) — <b>выходной</b>."
    om, cm = _h2m(t[0]), _h2m(t[1])
    cur = now.hour * 60 + now.minute
    if cur < om:
        return False, f"Ещё не открылись. Сегодня работаем с <b>{t[0]}</b> до <b>{t[1]}</b>."
    if cur >= cm:
        return False, f"Уже закрылись. Сегодня работали с {t[0]} до {t[1]}."
    left = cm - cur
    h, m = divmod(left, 60)
    ls = f"{h} ч {m} мин" if h else f"{m} мин"
    return True, f"Сейчас работаем — открыты до <b>{t[1]}</b> (осталось {ls})."


# ── book search ──────────────────────────────────────────────────

def norm(v: str) -> str:
    t = str(v or "").lower().replace("ё", "е")
    return re.sub(r"(.)\1{2,}", r"\1\1", t)


def base_tokens(q: str) -> list[str]:
    sw = {"посоветуй", "совет", "дай", "подбери", "книг", "книга", "книгу", "книги",
          "что", "почитать", "хочу", "мне", "пожалуйста"}
    return [t for t in re.findall(r"[a-zа-я0-9]+", norm(q))
            if len(t) > 1 and not any(t.startswith(s) for s in sw)]


def query_tokens(q: str) -> list[str]:
    raw = base_tokens(q)
    syn = {
        "романтик": ["любовь", "любовный", "отношения", "чувства", "влюбленность"],
        "любовь": ["романтической", "отношения", "чувства", "влюбленность"],
        "фэнтези": ["фантастика", "магия", "мистика"],
        "боевик": ["действие", "приключение", "опасность", "война"],
        "детектив": ["тайна", "расследование", "загадка", "преступление"],
    }
    exp = list(raw)
    for t in raw:
        for k, v in syn.items():
            if t.startswith(k) or k.startswith(t):
                exp.extend(v)
    return list(dict.fromkeys(exp))


def book_count(q: str) -> int:
    t = norm(q)
    m = re.search(r"\b([1-5])\b", t)
    if m:
        return int(m.group(1))
    w = {"одн": 1, "две": 2, "два": 2, "три": 3, "четыр": 4, "пят": 5}
    for p, c in w.items():
        if any(tk.startswith(p) for tk in t.split()):
            return c
    return 3


def book_text(book: dict) -> str:
    return norm(" ".join(str(book.get(f, "")) for f in ["title", "author", "description", "metadata"]))


def load_local_books() -> list[dict]:
    global LOCAL_BOOKS_CACHE
    if LOCAL_BOOKS_CACHE is not None:
        return LOCAL_BOOKS_CACHE
    if not VDONLIB_PREVIEW_JSON.is_file():
        return []
    try:
        LOCAL_BOOKS_CACHE = json.loads(VDONLIB_PREVIEW_JSON.read_text(encoding="utf-8"))
        return LOCAL_BOOKS_CACHE
    except Exception:
        log.exception("vdonlib preview load error")
        return []


def find_books(q: str, records: list[dict], limit: int = MAX_BOOKS_FOR_AI) -> list[dict]:
    tokens, raw = query_tokens(q), base_tokens(q)
    if not tokens:
        return []
    phrase = norm(q)
    scored = []
    for b in records:
        hs = book_text(b)
        sc = 0
        if phrase and phrase in hs:
            sc += 10
        for t in raw:
            if t in hs:
                sc += 6
            if t in norm(b.get("title")):
                sc += 7
            if t in norm(b.get("author")):
                sc += 4
        for t in tokens:
            if t in hs:
                sc += 1
            if t in norm(b.get("title")):
                sc += 3
            if t in norm(b.get("author")):
                sc += 2
        if sc:
            scored.append((sc, b))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [b for _, b in scored[:limit]]


def is_bulletin(b: dict) -> bool:
    t = norm(b.get("title"))
    return "бюллетень" in t or "новых поступ" in t or norm(b.get("source_type")) in {"novelty", "edition"}


def choose_books(books: list[dict], limit: int = MAX_BOOKS_FOR_AI) -> list[dict]:
    cards = [b for b in books if b.get("source_type") in {"book_disassembly", "novelty_book"}]
    if cards:
        return cards[:limit]
    clean = [b for b in books if not is_bulletin(b) and (b.get("author") or b.get("description"))]
    return clean[:limit]


def is_generic(q: str) -> bool:
    t = norm(q)
    return any(v in t for v in ("посовет", "подбер", "рекоменд", "дай")) and not base_tokens(q)


def default_recs(records: list[dict], limit: int = MAX_BOOKS_FOR_AI) -> list[dict]:
    blocked = ("справочник", "сборник", "указатель", "бюллетень", "новые поступления")
    pref = [b for b in records
            if b.get("source_type") == "book_disassembly" and (b.get("description") or b.get("raw_text"))
            and not any(w in norm(b.get("title")) for w in blocked)]
    return (pref or choose_books(records, limit))[:limit]


def prefer_clean(q: str, books: list[dict], limit: int = MAX_BOOKS_FOR_AI) -> list[dict]:
    good = [b for b in books if b.get("description") and len(str(b["description"]).strip()) > 50]
    return (good or books)[:limit]


def _book_branches(book: dict) -> str:
    md = book.get("metadata") or {}
    if not isinstance(md, dict):
        return ""
    bids = md.get("branches") or []
    if not isinstance(bids, list):
        return ""
    names = []
    for bid in bids:
        br = branch_by_id(str(bid))
        if not br:
            continue
        name = br.get("short") or br.get("name") or ""
        if name:
            names.append(name)
    return ", ".join(names)


# ── location ─────────────────────────────────────────────────────

BRANCH_COORDS = {
    "central": (47.5159, 42.1509), "cdb": (47.5147, 42.1518),
    "lib3": (47.5074, 42.1748), "lib4": (47.5120, 42.1964),
    "lib5": (47.5122, 42.1967), "lib6": (47.5127, 42.1833),
    "lib8": (47.5209, 42.1952), "lib9": (47.5214, 42.1667),
    "lib10": (47.5320, 42.1985), "lib11": (47.5264, 42.1946),
    "lib12": (47.5121, 42.1607),
}


def dist_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    R = 6371000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def fmt_dist(m: int) -> str:
    return f"{m} м" if m < 1000 else f"{m / 1000:.1f} км".replace(".", ",")


def nearest_branch(lat: float, lon: float) -> tuple[dict, int] | None:
    cand = [(dist_m(lat, lon, BRANCH_COORDS[br["id"]][0], BRANCH_COORDS[br["id"]][1]), br)
            for br in BRANCHES if br["id"] in BRANCH_COORDS]
    if not cand:
        return None
    d, br = min(cand, key=lambda x: x[0])
    return br, d


def yandex_route_url(flat: float, flon: float, br: dict) -> str:
    from library_data import yandex_map_url
    c = BRANCH_COORDS.get(br["id"])
    if not c:
        return yandex_map_url(br["address"])
    return f"https://yandex.ru/maps/?rtext={flat},{flon}~{c[0]},{c[1]}&rtt=mt"


def extract_location(ev) -> tuple[float, float] | None:
    body = getattr(ev.message, "body", None)
    for a in getattr(body, "attachments", None) or []:
        lat, lon = getattr(a, "latitude", None), getattr(a, "longitude", None)
        if lat and lon:
            return float(lat), float(lon)
    return None


# ── reading mode ─────────────────────────────────────────────────

def _rkey_ev(ev) -> tuple[str, int] | None:
    try:
        cid, uid = ev.get_ids()
    except Exception:
        return None
    return _rkey(cid, uid)


def _rkey(cid, uid) -> tuple[str, int] | None:
    if cid is not None:
        return ("c", int(cid))
    if uid is not None:
        return ("u", int(uid))
    return None


def en_reading(ev) -> None:
    k = _rkey_ev(ev)
    if k:
        READING_MODE.add(k)


def dis_reading(ev) -> None:
    k = _rkey_ev(ev)
    if k:
        READING_MODE.discard(k)


def in_reading(ev) -> bool:
    k = _rkey_ev(ev)
    return k in READING_MODE if k else False


# ── menu dedup ───────────────────────────────────────────────────

_last_menu: dict[str, float] = {}
_DEDUP_WIN = 3.0


def _mkeys(cid, uid=None) -> list[str]:
    ks = []
    if cid is not None:
        ks.append(f"c:{cid}")
    if uid is not None:
        ks.append(f"u:{uid}")
    return ks


def _should_menu(cid, uid=None) -> bool:
    ks = _mkeys(cid, uid)
    if not ks:
        return True
    now = time.monotonic()
    for k in ks:
        if now - _last_menu.get(k, 0) < _DEDUP_WIN:
            return False
    for k in ks:
        _last_menu[k] = now
    return True


# ── keepalive ────────────────────────────────────────────────────

def _keepalive() -> None:
    port = os.getenv("PORT")
    if not port:
        return
    try:
        pi = int(port)
    except Exception:
        log.warning("PORT=%r not int", port)
        return
    import threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"OK")

        def log_message(self, *args) -> None:
            pass

    def _srv() -> None:
        try:
            s = ThreadingHTTPServer(("0.0.0.0", pi), H)
            log.info("keepalive :%s", pi)
            s.serve_forever()
        except Exception:
            log.exception("keepalive fail")

    threading.Thread(target=_srv, daemon=True).start()
