from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

def admin_panel():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Управление слотами", callback_data="admin_slots")],
            [InlineKeyboardButton(text="📋 Все записи", callback_data="admin_appointments")],
            [InlineKeyboardButton(text="🛠 Услуги", callback_data="admin_services")],
            [InlineKeyboardButton(text="🚫 Заблокировать день", callback_data="admin_block_day")],
            [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        ]
    )

def back_to_admin():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад в админку", callback_data="admin_back")],
        ]
    )

def appointments_filter():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Сегодня", callback_data="appointments_today")],
            [InlineKeyboardButton(text="📅 Завтра", callback_data="appointments_tomorrow")],
            [InlineKeyboardButton(text="📅 Эта неделя", callback_data="appointments_week")],
            [InlineKeyboardButton(text="📋 Все", callback_data="appointments_all")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )

def admin_services_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить услугу", callback_data="admin_add_service")],
            [InlineKeyboardButton(text="🗑 Удалить услугу", callback_data="admin_del_service")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="admin_back")],
        ]
    )

def services_list_kb(services: list) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"{s.name} — {s.price}₽", callback_data=f"delservice_{s.id}")
    builder.button(text="🔙 Назад", callback_data="admin_services")
    builder.adjust(1)
    return builder.as_markup()
