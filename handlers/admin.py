import logging
from datetime import date, datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from config import ADMIN_ID, BREAK_BETWEEN_SLOTS
from database.models import Service, ScheduleSlot, Appointment, BlockedDay
from database.db import async_session
from keyboards.admin_kb import (
    admin_panel, back_to_admin, appointments_filter,
    admin_services_menu, services_list_kb,
)
from keyboards.client_kb import main_menu

logger = logging.getLogger(__name__)
router = Router()

class AdminStates(StatesGroup):
    add_service_name = State()
    add_service_price = State()
    add_service_duration = State()
    add_slots_date = State()
    add_slots_start = State()
    add_slots_end = State()
    add_slots_interval = State()
    block_day_date = State()
    block_day_reason = State()
    broadcast_text = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

@router.message(Command("admin"))
async def admin_cmd(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Доступ запрещён.")
        return
    await message.answer("👑 Панель администратора:", reply_markup=admin_panel())

@router.callback_query(F.data == "admin_back")
async def admin_back(callback: CallbackQuery):
    await callback.message.edit_text("👑 Панель администратора:", reply_markup=admin_panel())

# ─── SLOTS ───────────────────────────────────

@router.callback_query(F.data == "admin_slots")
async def admin_slots_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📅 Управление слотами\n\nЯ создам слоты для указанной даты.\nВведите дату (ДД.ММ.ГГГГ):",
        reply_markup=back_to_admin(),
    )
    await state.set_state(AdminStates.add_slots_date)

@router.message(StateFilter(AdminStates.add_slots_date), F.text)
async def admin_slots_date(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
        if dt < date.today():
            await message.answer("Дата не может быть в прошлом. Попробуйте ещё раз:")
            return
    except ValueError:
        await message.answer("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    await state.update_data(slot_date=dt.isoformat())
    await state.set_state(AdminStates.add_slots_start)
    await message.answer(f"Дата: {dt.strftime('%d.%m.%Y')}\nВведите время начала (например, 09:00):")

@router.message(StateFilter(AdminStates.add_slots_start), F.text)
async def admin_slots_start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    time_str = message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время в формате ЧЧ:ММ (например, 09:00):")
        return
    await state.update_data(slot_start=time_str)
    await state.set_state(AdminStates.add_slots_end)
    await message.answer(f"Время начала: {time_str}\nВведите время окончания (например, 18:00):")

@router.message(StateFilter(AdminStates.add_slots_end), F.text)
async def admin_slots_end(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    time_str = message.text.strip()
    try:
        datetime.strptime(time_str, "%H:%M")
    except ValueError:
        await message.answer("Неверный формат. Введите время в формате ЧЧ:ММ (например, 18:00):")
        return
    data = await state.get_data()
    if time_str <= data["slot_start"]:
        await message.answer("Время окончания должно быть позже времени начала. Попробуйте ещё раз:")
        return
    await state.update_data(slot_end=time_str)
    await state.set_state(AdminStates.add_slots_interval)
    await message.answer(f"Диапазон: {data['slot_start']} — {time_str}\nВведите длительность слота в минутах (например, 60):")

@router.message(StateFilter(AdminStates.add_slots_interval), F.text)
async def admin_slots_interval(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        interval = int(message.text.strip())
        if interval < 15 or interval > 180:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 15 до 180 (минуты):")
        return
    data = await state.get_data()
    slot_date = date.fromisoformat(data["slot_date"])
    start_h, start_m = map(int, data["slot_start"].split(":"))
    end_h, end_m = map(int, data["slot_end"].split(":"))
    current = datetime.combine(slot_date, datetime.min.time().replace(hour=start_h, minute=start_m))
    end_time = datetime.combine(slot_date, datetime.min.time().replace(hour=end_h, minute=end_m))
    break_minutes = BREAK_BETWEEN_SLOTS
    slots_created = 0
    async with async_session() as session:
        existing = await session.execute(select(ScheduleSlot).where(ScheduleSlot.slot_date == slot_date))
        if existing.scalars().all():
            await message.answer(f"На {slot_date.strftime('%d.%m.%Y')} уже есть слоты. Сначала удалите их.")
            await state.clear()
            return
        while current + timedelta(minutes=interval) <= end_time:
            slot_end = current + timedelta(minutes=interval)
            slot = ScheduleSlot(slot_date=slot_date, time_start=current.strftime("%H:%M"), time_end=slot_end.strftime("%H:%M"))
            session.add(slot)
            slots_created += 1
            current = slot_end + timedelta(minutes=break_minutes)
        await session.commit()
    await message.answer(
        f"✅ Создано {slots_created} слотов на {slot_date.strftime('%d.%m.%Y')} "
        f"(с {data['slot_start']} до {data['slot_end']}, длительность {interval} мин, перерыв {break_minutes} мин).",
        reply_markup=admin_panel(),
    )
    await state.clear()

# ─── BLOCK DAY ────────────────────────────────

@router.callback_query(F.data == "admin_block_day")
async def admin_block_day(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("🚫 Введите дату для блокировки (ДД.ММ.ГГГГ):", reply_markup=back_to_admin())
    await state.set_state(AdminStates.block_day_date)

@router.message(StateFilter(AdminStates.block_day_date), F.text)
async def admin_block_day_date(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        dt = datetime.strptime(message.text.strip(), "%d.%m.%Y").date()
    except ValueError:
        await message.answer("Неверный формат. Введите дату в формате ДД.ММ.ГГГГ:")
        return
    await state.update_data(block_date=dt.isoformat())
    await state.set_state(AdminStates.block_day_reason)
    await message.answer(f"Дата: {dt.strftime('%d.%m.%Y')}\nВведите причину блокировки (или «Пропустить»):")

@router.message(StateFilter(AdminStates.block_day_reason), F.text)
async def admin_block_day_reason(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    reason = None if message.text.strip().lower() in ("пропустить", "-", "") else message.text.strip()
    data = await state.get_data()
    dt = date.fromisoformat(data["block_date"])
    async with async_session() as session:
        existing = await session.execute(select(BlockedDay).where(BlockedDay.block_date == dt))
        if existing.scalar_one_or_none():
            await message.answer(f"Дата {dt.strftime('%d.%m.%Y')} уже заблокирована.")
            await state.clear()
            return
        blocked = BlockedDay(block_date=dt, reason=reason)
        session.add(blocked)
        await session.commit()
    await message.answer(f"✅ Дата {dt.strftime('%d.%m.%Y')} заблокирована ({reason or 'без причины'}).", reply_markup=admin_panel())
    await state.clear()

# ─── VIEW APPOINTMENTS ────────────────────────

@router.callback_query(F.data == "admin_appointments")
async def admin_appointments_menu(callback: CallbackQuery):
    await callback.message.edit_text("Выберите период для просмотра записей:", reply_markup=appointments_filter())

@router.callback_query(F.data.startswith("appointments_"))
async def admin_appointments_list(callback: CallbackQuery):
    period = callback.data.split("_")[1]
    today = date.today()
    if period == "today":
        date_from, date_to = today, today
    elif period == "tomorrow":
        date_from = date_to = today + timedelta(days=1)
    elif period == "week":
        date_from = today
        date_to = today + timedelta(days=7)
    else:
        date_from = date(2000, 1, 1)
        date_to = date(2100, 1, 1)
    async with async_session() as session:
        result = await session.execute(
            select(Appointment)
            .options(selectinload(Appointment.service), selectinload(Appointment.slot))
            .where(Appointment.status == "active")
            .order_by(Appointment.created_at.desc())
        )
        all_apts = result.scalars().all()
        filtered = [apt for apt in all_apts if date_from <= apt.slot.slot_date <= date_to]
        if not filtered:
            await callback.message.edit_text("📋 Нет записей за выбранный период.", reply_markup=appointments_filter())
            return
        builder = InlineKeyboardBuilder()
        for apt in filtered:
            slot = apt.slot
            service = apt.service
            short = f"#{apt.id} {apt.user_name} | {service.name} {slot.slot_date.strftime('%d.%m')} {slot.time_start}"
            builder.button(text=f"❌ {short}", callback_data=f"admin_cancel_appt_{apt.id}")
        builder.button(text="🔙 Назад", callback_data="admin_appointments")
        builder.adjust(1)
        text = f"📋 Записи (найдено: {len(filtered)}):\n\nНажмите ❌ чтобы отменить запись:"
        await callback.message.edit_text(text, reply_markup=builder.as_markup())

@router.callback_query(F.data.startswith("admin_cancel_appt_"))
async def admin_cancel_appt_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    apt_id = int(callback.data.split("_")[3])
    async with async_session() as session:
        appointment = await session.get(
            Appointment, apt_id,
            options=[selectinload(Appointment.service), selectinload(Appointment.slot)],
        )
        if not appointment or appointment.status != "active":
            await callback.answer("Запись уже отменена или не найдена.", show_alert=True)
            return
        slot = appointment.slot
        service = appointment.service
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"admin_confirm_cancel_{apt_id}")],
            [InlineKeyboardButton(text="🔙 Отмена", callback_data="admin_back_to_appointments")],
        ])
        await callback.message.edit_text(
            f"❓ Подтвердите отмену записи:\n\n"
            f"#{appointment.id} | {appointment.user_name} | {appointment.user_phone}\n"
            f"Услуга: {service.name}\n"
            f"Дата: {slot.slot_date.strftime('%d.%m.%Y')}\n"
            f"Время: {slot.time_start} — {slot.time_end}\n"
            f"Комментарий: {appointment.comment or '—'}",
            reply_markup=kb,
        )
    await callback.answer()

@router.callback_query(F.data.startswith("admin_confirm_cancel_"))
async def admin_cancel_appt_execute(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён.", show_alert=True)
        return
    apt_id = int(callback.data.split("_")[3])
    async with async_session() as session:
        appointment = await session.get(
            Appointment, apt_id,
            options=[selectinload(Appointment.service), selectinload(Appointment.slot)],
        )
        if not appointment or appointment.status != "active":
            await callback.answer("Запись уже отменена или не найдена.", show_alert=True)
            return
        slot = appointment.slot
        service = appointment.service
        appointment.status = "cancelled"
        slot.is_booked = False
        await session.commit()
        try:
            await callback.bot.send_message(
                appointment.user_id,
                f"❌ Ваша запись #{apt_id} отменена мастером.\n"
                f"Услуга: {service.name}\nДата: {slot.slot_date.strftime('%d.%m.%Y')} в {slot.time_start}\n\n"
                f"Для новой записи используйте /start",
            )
        except Exception:
            pass
    await callback.message.edit_text(f"✅ Запись #{apt_id} отменена. Клиент уведомлён.", reply_markup=admin_panel())
    await callback.answer()

@router.callback_query(F.data == "admin_back_to_appointments")
async def admin_back_to_appointments(callback: CallbackQuery):
    await callback.message.edit_text("Выберите период для просмотра записей:", reply_markup=appointments_filter())

# ─── SERVICES ─────────────────────────────────

@router.callback_query(F.data == "admin_services")
async def admin_services_menu_handler(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(Service).order_by(Service.name))
        services = result.scalars().all()
    lines = ["🛠 Услуги:\n"]
    for s in services:
        lines.append(f"• {s.name} — {s.price}₽ ({s.duration_minutes} мин)")
    if not services:
        lines.append("(нет услуг)")
    await callback.message.edit_text("\n".join(lines), reply_markup=admin_services_menu())

@router.callback_query(F.data == "admin_add_service")
async def admin_add_service(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Введите название услуги:")
    await state.set_state(AdminStates.add_service_name)

@router.message(StateFilter(AdminStates.add_service_name), F.text)
async def admin_add_service_name(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    name = message.text.strip()
    if len(name) < 2 or len(name) > 100:
        await message.answer("Название должно быть от 2 до 100 символов. Попробуйте ещё раз:")
        return
    await state.update_data(svc_name=name)
    await state.set_state(AdminStates.add_service_price)
    await message.answer(f"Название: {name}\nВведите цену (в рублях):")

@router.message(StateFilter(AdminStates.add_service_price), F.text)
async def admin_add_service_price(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        price = float(message.text.strip().replace(",", "."))
        if price <= 0 or price > 100000:
            raise ValueError
    except ValueError:
        await message.answer("Введите корректную цену (число от 1 до 100000):")
        return
    await state.update_data(svc_price=price)
    await state.set_state(AdminStates.add_service_duration)
    await message.answer(f"Цена: {price}₽\nВведите длительность в минутах:")

@router.message(StateFilter(AdminStates.add_service_duration), F.text)
async def admin_add_service_duration(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    try:
        duration = int(message.text.strip())
        if duration < 15 or duration > 480:
            raise ValueError
    except ValueError:
        await message.answer("Введите число от 15 до 480 (минуты):")
        return
    data = await state.get_data()
    async with async_session() as session:
        service = Service(name=data["svc_name"], price=data["svc_price"], duration_minutes=duration)
        session.add(service)
        await session.commit()
    await message.answer(f"✅ Услуга «{data['svc_name']}» добавлена!", reply_markup=admin_panel())
    await state.clear()

@router.callback_query(F.data == "admin_del_service")
async def admin_del_service_list(callback: CallbackQuery):
    async with async_session() as session:
        result = await session.execute(select(Service).order_by(Service.name))
        services = result.scalars().all()
    if not services:
        await callback.message.edit_text("Нет услуг для удаления.", reply_markup=admin_services_menu())
        return
    await callback.message.edit_text("Выберите услугу для удаления:", reply_markup=services_list_kb(services))

@router.callback_query(F.data.startswith("delservice_"))
async def admin_del_service_confirm(callback: CallbackQuery):
    svc_id = int(callback.data.split("_")[1])
    async with async_session() as session:
        service = await session.get(Service, svc_id)
        if service:
            name = service.name
            await session.delete(service)
            await session.commit()
            await callback.message.edit_text(f"✅ Услуга «{name}» удалена.", reply_markup=admin_panel())
        else:
            await callback.message.edit_text("Услуга не найдена.", reply_markup=admin_panel())

# ─── BROADCAST ────────────────────────────────

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "📢 Введите текст для рассылки всем клиентам, которые когда-либо записывались:",
        reply_markup=back_to_admin(),
    )
    await state.set_state(AdminStates.broadcast_text)

@router.message(StateFilter(AdminStates.broadcast_text), F.text)
async def admin_broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = message.text.strip()
    if len(text) < 1 or len(text) > 4000:
        await message.answer("Текст должен быть от 1 до 4000 символов.")
        return
    async with async_session() as session:
        result = await session.execute(select(Appointment.user_id).distinct())
        user_ids = list(set(row[0] for row in result.all()))
    sent = 0
    failed = 0
    for uid in user_ids:
        try:
            await message.bot.send_message(chat_id=uid, text=text)
            sent += 1
        except Exception as e:
            logger.warning(f"Broadcast failed to {uid}: {e}")
            failed += 1
    await message.answer(
        f"📢 Рассылка завершена!\n✅ Отправлено: {sent}\n❌ Ошибок: {failed}\nВсего получателей: {len(user_ids)}",
        reply_markup=admin_panel(),
    )
    await state.clear()

# ─── LOGGING ──────────────────────────────────

class AdminLogger:
    def __init__(self):
        self.logger = logging.getLogger("admin_actions")
        handler = logging.FileHandler("admin.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s - %(message)s"))
        self.logger.addHandler(handler)
        self.logger.setLevel(logging.INFO)

    def log(self, action: str):
        self.logger.info(action)

admin_logger = AdminLogger()
