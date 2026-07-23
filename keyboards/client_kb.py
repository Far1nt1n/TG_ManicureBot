from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder


def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📅 Записаться")],
            [KeyboardButton(text="📋 Мои записи")],
            [KeyboardButton(text="ℹ️ О мастере")],
        ],
        resize_keyboard=True,
    )


def services_kb(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"{s.name} — {s.price}₽ ({s.duration_minutes} мин)", callback_data=f"service_{s.id}")
    builder.button(text="🔙 Назад", callback_data="back_to_main")
    builder.adjust(1)
    return builder.as_markup()


def cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отменить запись", callback_data=f"cancel_booking_{booking_id}")],
        ]
    )


def confirm_booking_kb(service_id: int, slot_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"confirm_{service_id}_{slot_id}"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="back_to_main"),
            ],
        ]
    )


def dates_kb(dates: list[tuple]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for date_str, display in dates:
        builder.button(text=display, callback_data=f"date_{date_str}")
    builder.button(text="🔙 Назад", callback_data="back_to_services")
    builder.adjust(2)
    return builder.as_markup()


def slots_kb(slots: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in slots:
        builder.button(text=f"{s.time_start} — {s.time_end}", callback_data=f"slot_{s.id}")
    builder.button(text="🔙 Назад", callback_data="back_to_dates")
    builder.adjust(2)
    return builder.as_markup()


def contact_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Отправить номер", request_contact=True)],
            [KeyboardButton(text="🔙 Назад")],
        ],
        resize_keyboard=True,
    )


def subscription_check_kb(channel_username: str = None):
    url = f"https://t.me/{channel_username.lstrip('@')}" if channel_username else "https://t.me/your_channel"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📢 Подписаться", url=url)],
            [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_subscription")],
        ],
    )
