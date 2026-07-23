import re
from datetime import date, datetime, timedelta, time
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from database.models import Service, ScheduleSlot, Appointment, BlockedDay
from database.db import get_session, async_session
from keyboards.client_kb import (
    main_menu, services_kb, dates_kb, slots_kb,
    confirm_booking_kb, contact_kb, cancel_booking_kb,
)

router = Router()

WEEKDAYS_RU = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]

def fmt_date(d: date) -> str:
    return f"{WEEKDAYS_RU[d.weekday()]} {d.strftime('%d.%m')}"

class BookingStates(StatesGroup):
    choosing_service = State()
    choosing_date = State()
    choosing_slot = State()
    entering_name = State()
    entering_phone = State()
    entering_comment = State()
    confirming = State()

@router.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        f"👋 Здравствуйте, {message.from_user.first_name}!\n"
        f"Добро пожаловать в бот записи к мастеру маникюра.\n\n"
        f"Выберите действие:",
        reply_markup=main_menu(),
    )

@router.message(F.text == "📅 Записаться")
async def show_services(message: Message, state: FSMContext):
    await state.clear()
    async with async_session() as session:
        result = await session.execute(select(Service).order_by(Service.name))
        services = result.scalars().all()
    if not services:
        await message.answer("😕 Услуги временно недоступны. Попробуйте позже.")
        return
    await state.set_state(BookingStates.choosing_service)
    await state.update_data(services=services)
    await message.answer("Выберите услугу:", reply_markup=services_kb(services))

@router.callback_query(F.data.startswith("service_"))
async def service_chosen(callback: CallbackQuery, state: FSMContext):
    service_id = int(callback.data.split("_")[1])
    await state.update_data(service_id=service_id)
    await callback.answer()
    today = date.today()
    dates_list = []
    for i in range(14):
        d = today + timedelta(days=i)
        async with async_session() as session:
            blocked = await session.execute(select(BlockedDay).where(BlockedDay.block_date == d))
            if blocked.scalar_one_or_none():
                continue
            slots_count = await session.execute(
                select(ScheduleSlot).where(
                    and_(ScheduleSlot.slot_date == d, ScheduleSlot.is_booked == False, ScheduleSlot.is_blocked == False)
                )
            )
            if len(slots_count.scalars().all()) == 0:
                continue
        display = fmt_date(d)
        dates_list.append((d.isoformat(), display))
    if not dates_list:
        await callback.message.edit_text("😕 Нет свободных дат. Попробуйте позже.")
        return
    await state.set_state(BookingStates.choosing_date)
    await callback.message.edit_text("Выберите дату:", reply_markup=dates_kb(dates_list))

@router.callback_query(F.data == "back_to_services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.choosing_service)
    data = await state.get_data()
    await callback.message.edit_text("Выберите услугу:", reply_markup=services_kb(data["services"]))

@router.callback_query(F.data.startswith("date_"))
async def date_chosen(callback: CallbackQuery, state: FSMContext):
    chosen_date = callback.data.split("_")[1]
    await state.update_data(selected_date=chosen_date)
    await callback.answer()
    dt = date.fromisoformat(chosen_date)
    async with async_session() as session:
        result = await session.execute(
            select(ScheduleSlot).where(
                and_(ScheduleSlot.slot_date == dt, ScheduleSlot.is_booked == False, ScheduleSlot.is_blocked == False)
            ).order_by(ScheduleSlot.time_start)
        )
        slots = result.scalars().all()
    if not slots:
        await callback.message.edit_text("😕 Нет свободных слотов на эту дату. Выберите другую.")
        return
    await state.set_state(BookingStates.choosing_slot)
    await callback.message.edit_text(f"Дата: {dt.strftime('%d.%m.%Y')}\nВыберите время:", reply_markup=slots_kb(slots))

@router.callback_query(F.data == "back_to_dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookingStates.choosing_date)
    data = await state.get_data()
    today = date.today()
    dates_list = []
    for i in range(14):
        d = today + timedelta(days=i)
        async with async_session() as session:
            blocked = await session.execute(select(BlockedDay).where(BlockedDay.block_date == d))
            if blocked.scalar_one_or_none():
                continue
        display = fmt_date(d)
        dates_list.append((d.isoformat(), display))
    await callback.message.edit_text("Выберите дату:", reply_markup=dates_kb(dates_list))

@router.callback_query(F.data.startswith("slot_"))
async def slot_chosen(callback: CallbackQuery, state: FSMContext):
    slot_id = int(callback.data.split("_")[1])
    await state.update_data(slot_id=slot_id)
    await callback.answer()
    await state.set_state(BookingStates.entering_name)
    await callback.message.edit_text("Введите ваше имя:", reply_markup=None)
    await callback.message.answer("Напишите ваше имя:", reply_markup=ReplyKeyboardRemove())

@router.message(StateFilter(BookingStates.entering_name))
async def name_entered(message: Message, state: FSMContext):
    name = message.text.strip()
    if len(name) < 2 or len(name) > 50:
        await message.answer("Имя должно быть от 2 до 50 символов. Попробуйте ещё раз:")
        return
    await state.update_data(user_name=name)
    await state.set_state(BookingStates.entering_phone)
    await message.answer("Отправьте ваш номер телефона (нажмите кнопку ниже):", reply_markup=contact_kb())

@router.message(StateFilter(BookingStates.entering_phone), F.contact)
async def phone_contact(message: Message, state: FSMContext):
    phone = message.contact.phone_number
    await state.update_data(user_phone=phone)
    await state.set_state(BookingStates.entering_comment)
    async with async_session() as session:
        data = await state.get_data()
        svc = await session.get(Service, data["service_id"])
        slot = await session.get(ScheduleSlot, data["slot_id"])
        await message.answer(
            f"📌 Проверьте данные:\n"
            f"Услуга: {svc.name} ({svc.duration_minutes} мин) — {svc.price}₽\n"
            f"Дата: {slot.slot_date.strftime('%d.%m.%Y')}\n"
            f"Время: {slot.time_start} — {slot.time_end}\n"
            f"Имя: {data['user_name']}\n"
            f"Телефон: {phone}\n\n"
            f"Добавьте комментарий (или отправьте «Пропустить»):",
            reply_markup=ReplyKeyboardRemove(),
        )

@router.message(StateFilter(BookingStates.entering_phone), F.text)
async def phone_text_entered(message: Message, state: FSMContext):
    phone = message.text.strip()
    phone_clean = re.sub(r"[^\d+]", "", phone)
    if len(phone_clean) < 10:
        await message.answer("Введите корректный номер телефона (не менее 10 цифр):")
        return
    await state.update_data(user_phone=phone_clean)
    await state.set_state(BookingStates.entering_comment)
    async with async_session() as session:
        data = await state.get_data()
        svc = await session.get(Service, data["service_id"])
        slot = await session.get(ScheduleSlot, data["slot_id"])
        await message.answer(
            f"📌 Проверьте данные:\n"
            f"Услуга: {svc.name} ({svc.duration_minutes} мин) — {svc.price}₽\n"
            f"Дата: {slot.slot_date.strftime('%d.%m.%Y')}\n"
            f"Время: {slot.time_start} — {slot.time_end}\n"
            f"Имя: {data['user_name']}\n"
            f"Телефон: {phone_clean}\n\n"
            f"Добавьте комментарий (или отправьте «Пропустить»):",
            reply_markup=ReplyKeyboardRemove(),
        )

@router.message(StateFilter(BookingStates.entering_comment))
async def comment_entered(message: Message, state: FSMContext):
    text = message.text.strip()
    comment = None if text.lower() in ("пропустить", "-", "нет") else text
    await state.update_data(comment=comment)
    data = await state.get_data()
    async with async_session() as session:
        svc = await session.get(Service, data["service_id"])
        slot = await session.get(ScheduleSlot, data["slot_id"])
        await state.set_state(BookingStates.confirming)
        await message.answer(
            f"📌 Подтверждение записи:\n\n"
            f"Услуга: {svc.name}\n"
            f"Дата: {slot.slot_date.strftime('%d.%m.%Y')}\n"
            f"Время: {slot.time_start} — {slot.time_end}\n"
            f"Имя: {data['user_name']}\n"
            f"Телефон: {data['user_phone']}\n"
            f"Комментарий: {comment or '—'}\n\n"
            f"Всё верно?",
            reply_markup=confirm_booking_kb(data["service_id"], data["slot_id"]),
        )

@router.callback_query(F.data.startswith("confirm_"))
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    slot_id = data["slot_id"]
    service_id = data["service_id"]
    user_id = callback.from_user.id
    user_name = data["user_name"]
    user_phone = data["user_phone"]
    comment = data.get("comment")
    async with async_session() as session:
        slot = await session.get(ScheduleSlot, slot_id)
        if not slot or slot.is_booked or slot.is_blocked:
            await callback.message.edit_text("😕 Этот слот уже занят или недоступен. Выберите другой.")
            await state.clear()
            return
        service = await session.get(Service, service_id)
        if not service:
            await callback.message.edit_text("😕 Услуга недоступна.")
            await state.clear()
            return
        appointment = Appointment(
            user_id=user_id, user_name=user_name, user_phone=user_phone,
            comment=comment, service_id=service_id, slot_id=slot_id, status="active",
        )
        slot.is_booked = True
        session.add(appointment)
        await session.commit()
        await callback.message.edit_text(
            f"✅ Запись подтверждена!\n\n"
            f"Услуга: {service.name}\n"
            f"Дата: {slot.slot_date.strftime('%d.%m.%Y')}\n"
            f"Время: {slot.time_start} — {slot.time_end}\n\n"
            f"Вы получите напоминание перед записью.",
        )
        await callback.message.answer("Выберите действие:", reply_markup=main_menu())
        from config import ADMIN_ID
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                f"🔔 Новая запись!\n\nКлиент: {user_name}\nТелефон: {user_phone}\n"
                f"Услуга: {service.name}\nДата: {slot.slot_date.strftime('%d.%m.%Y')}\n"
                f"Время: {slot.time_start}\nКомментарий: {comment or '—'}",
            )
        except Exception:
            pass
    await state.clear()

@router.message(F.text == "📋 Мои записи")
async def my_bookings(message: Message):
    user_id = message.from_user.id
    async with async_session() as session:
        result = await session.execute(
            select(Appointment)
            .options(selectinload(Appointment.service), selectinload(Appointment.slot))
            .where(and_(Appointment.user_id == user_id, Appointment.status == "active"))
            .order_by(Appointment.created_at.desc())
        )
        appointments = result.scalars().all()
        if not appointments:
            await message.answer("У вас нет активных записей.")
            return
        for apt in appointments:
            service = apt.service
            slot = apt.slot
            text = (
                f"📋 Запись #{apt.id}\n"
                f"Услуга: {service.name}\n"
                f"Дата: {slot.slot_date.strftime('%d.%m.%Y')} в {slot.time_start}\n"
                f"Статус: ✅ Активна"
            )
            await message.answer(text, reply_markup=cancel_booking_kb(apt.id))

@router.callback_query(F.data.startswith("cancel_booking_"))
async def cancel_booking(callback: CallbackQuery):
    apt_id = int(callback.data.split("_")[2])
    async with async_session() as session:
        appointment = await session.get(
            Appointment, apt_id,
            options=[selectinload(Appointment.service), selectinload(Appointment.slot)],
        )
        if not appointment or appointment.user_id != callback.from_user.id:
            await callback.answer("Запись не найдена или это не ваша запись.", show_alert=True)
            return
        if appointment.status != "active":
            await callback.answer("Запись уже отменена.", show_alert=True)
            return
        slot = appointment.slot
        slot_dt = datetime.combine(slot.slot_date, datetime.strptime(slot.time_start, "%H:%M").time())
        from config import CANCEL_HOURS_BEFORE
        if datetime.now() + timedelta(hours=CANCEL_HOURS_BEFORE) > slot_dt:
            await callback.answer(
                f"Нельзя отменить запись менее чем за {CANCEL_HOURS_BEFORE} часа до начала. Свяжитесь с мастером.",
                show_alert=True,
            )
            return
        appointment.status = "cancelled"
        slot.is_booked = False
        await session.commit()
        await callback.message.edit_text("✅ Запись отменена.")
        await callback.answer()
        from config import ADMIN_ID
        try:
            await callback.bot.send_message(
                ADMIN_ID,
                f"❌ Клиент {appointment.user_name} отменил запись #{apt_id} "
                f"на {slot.slot_date.strftime('%d.%m.%Y')} в {slot.time_start}.",
            )
        except Exception:
            pass

@router.message(F.text == "ℹ️ О мастере")
async def about_master(message: Message):
    await message.answer(
        "💅 Мастер маникюра с опытом работы более 5 лет.\n"
        "📍 Работаю в центре города\n📞 Связь: @master_username\n\n"
        "Использую только профессиональные материалы.",
        reply_markup=main_menu(),
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Главное меню:", reply_markup=None)
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())

@router.callback_query(F.data == "check_subscription")
async def check_sub_after(callback: CallbackQuery):
    from config import CHANNEL_USERNAME, ADMIN_ID
    try:
        member = await callback.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=callback.from_user.id)
        from aiogram.enums.chat_member_status import ChatMemberStatus
        if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED, ChatMemberStatus.RESTRICTED):
            await callback.answer("Вы ещё не подписались! Подпишитесь и попробуйте снова.", show_alert=True)
            return
    except Exception:
        await callback.answer("Ошибка проверки. Попробуйте позже.", show_alert=True)
        return
    await callback.message.edit_text("✅ Спасибо за подписку! Теперь вы можете пользоваться ботом.")
    await callback.message.answer("Выберите действие:", reply_markup=main_menu())
