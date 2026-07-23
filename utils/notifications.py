import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import Appointment, ScheduleSlot
from database.db import async_session

logger = logging.getLogger(__name__)


async def send_reminder(bot, user_id: int, text: str):
    try:
        await bot.send_message(chat_id=user_id, text=text)
    except Exception as e:
        logger.error(f"Failed to send reminder to {user_id}: {e}")


async def check_and_send_reminders(bot):
    now = datetime.now()
    async with async_session() as session:
        result = await session.execute(
            select(Appointment)
            .options(selectinload(Appointment.service), selectinload(Appointment.slot))
            .where(Appointment.status == "active")
        )
        appointments = result.scalars().all()

        for apt in appointments:
            slot = apt.slot
            slot_dt = datetime.combine(slot.slot_date, datetime.strptime(slot.time_start, "%H:%M").time())

            diff_24h = slot_dt - now
            diff_2h = slot_dt - now

            if timedelta(hours=23) <= diff_24h <= timedelta(hours=25) and not apt.notified_24h:
                await send_reminder(
                    bot, apt.user_id,
                    f"⏰ Напоминание: у вас запись завтра в {slot.time_start}.\n"
                    f"Услуга: {apt.service.name}\n"
                    f"Если нужно отменить — используйте /start и раздел «Мои записи»."
                )
                apt.notified_24h = True

            if timedelta(hours=1.5) <= diff_2h <= timedelta(hours=2.5) and not apt.notified_2h:
                await send_reminder(
                    bot, apt.user_id,
                    f"⏰ Напоминание: у вас запись через 2 часа в {slot.time_start}.\n"
                    f"Услуга: {apt.service.name}"
                )
                apt.notified_2h = True

        await session.commit()
