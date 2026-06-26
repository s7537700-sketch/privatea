"""Inline keyboard builders. Pure presentation layer — zero business logic."""

from maxapi.types import CallbackButton, LinkButton, RequestGeoLocationButton
from maxapi.utils.inline_keyboard import InlineKeyboardBuilder

from library_data import (
    AFISHA_VK_URL, BRANCHES, CATALOG_URL, CONTACTS_PAGE_URL,
    PUSHKIN_KASSIR_URL, VK_URL, WEBSITE_URL, WELCOME_TEXT,
    branch_by_id, yandex_map_url,
)
from bot.services import yandex_route_url

CATALOG_URL = CATALOG_URL  # local alias
EVENTS_URL = "https://vdonlib.ru/event/"


def main_menu_kb(menu: list) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for row in menu:
        if not row:
            continue
        btns = []
        for btn in row:
            payload = btn["payload"]
            if payload == "link:website":
                btns.append(LinkButton(text=btn["text"], url=WEBSITE_URL))
            else:
                btns.append(CallbackButton(text=btn["text"], payload=payload))
        b.row(*btns)
    return b.as_markup()


def branches_list_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    for br in BRANCHES:
        b.row(CallbackButton(text=br["short"], payload=f"branch:{br['id']}"))
    b.row(CallbackButton(text="« Назад", payload="menu:main"))
    return b.as_markup()


def branch_detail_kb(br: dict) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(LinkButton(text="🗺 На карте", url=yandex_map_url(br["address"])))
    if br.get("vk_url"):
        b.row(LinkButton(text="🔵 Страница ВК", url=br["vk_url"]))
    b.row(CallbackButton(text="« К списку", payload="menu:branches"),
          CallbackButton(text="🏠 Главная", payload="menu:main"))
    return b.as_markup()


def afisha_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(LinkButton(text="🌐 Афиша на сайте", url=EVENTS_URL))
    b.row(LinkButton(text="🔵 Афиша в ВК", url=AFISHA_VK_URL))
    b.row(CallbackButton(text="« Назад", payload="menu:main"))
    return b.as_markup()


def books_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text="🎲 Случайная книга", payload="menu:random_book"))
    b.row(LinkButton(text="📚 Электронный каталог", url=CATALOG_URL))
    b.row(CallbackButton(text="📞 Связаться", payload="menu:contacts"),
          CallbackButton(text="« Назад", payload="menu:main"))
    return b.as_markup()


def pushkin_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    if PUSHKIN_KASSIR_URL:
        b.row(LinkButton(text="🎭 События по Пушкинской карте", url=PUSHKIN_KASSIR_URL))
    b.row(CallbackButton(text="« Назад", payload="menu:main"))
    return b.as_markup()


def hours_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text="🏠 Главная", payload="menu:main"))
    return b.as_markup()


def back_to_main_kb() -> InlineKeyboardBuilder:
    return InlineKeyboardBuilder().row(CallbackButton(text="🏠 Главная", payload="menu:main")).as_markup()


def register_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(CallbackButton(text="📞 Связаться", payload="menu:contacts"))
    b.row(CallbackButton(text="🏠 Главная", payload="menu:main"))
    return b.as_markup()


def nearest_loc_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(RequestGeoLocationButton(text="📍 Отправить местоположение", quick=True))
    b.row(CallbackButton(text="« К списку библиотек", payload="menu:branches"))
    return b.as_markup()


def nearest_res_kb(ulat: float, ulon: float, br: dict) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(LinkButton(text="🧭 Маршрут в Яндекс Картах", url=yandex_route_url(ulat, ulon, br)))
    b.row(LinkButton(text="🗺 Библиотека на карте", url=yandex_map_url(br["address"])))
    b.row(CallbackButton(text="« К списку библиотек", payload="menu:branches"))
    return b.as_markup()


def rec_kb(books: list[dict], *, random_mode: bool = False) -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    if random_mode:
        b.row(CallbackButton(text="🎲 Ещё случайная книга", payload="menu:random_book"))
    b.row(LinkButton(text="Электронный каталог", url=CATALOG_URL))
    b.row(CallbackButton(text="Связаться", payload="menu:contacts"),
          CallbackButton(text="« Назад", payload="menu:main"))
    return b.as_markup()


def contacts_kb() -> InlineKeyboardBuilder:
    b = InlineKeyboardBuilder()
    b.row(LinkButton(text="🌐 Контакты всех библиотек", url=CONTACTS_PAGE_URL))
    b.row(LinkButton(text="🔵 ВК", url=VK_URL))
    b.row(LinkButton(text="🌐 Сайт", url=WEBSITE_URL))
    b.row(CallbackButton(text="🏠 Главная", payload="menu:main"))
    return b.as_markup()
