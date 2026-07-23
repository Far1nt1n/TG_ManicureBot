from datetime import date, datetime
from sqlalchemy import String, Integer, Float, Boolean, Date, DateTime, Text, ForeignKey, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    pass


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)

    appointments: Mapped[list["Appointment"]] = relationship(back_populates="service")


class BlockedDay(Base):
    __tablename__ = "blocked_days"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    block_date: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(200), nullable=True)


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot_date: Mapped[date] = mapped_column(Date, nullable=False)
    time_start: Mapped[str] = mapped_column(String(5), nullable=False)
    time_end: Mapped[str] = mapped_column(String(5), nullable=False)
    is_booked: Mapped[bool] = mapped_column(Boolean, default=False)
    is_blocked: Mapped[bool] = mapped_column(Boolean, default=False)

    appointment: Mapped["Appointment"] = relationship(back_populates="slot", uselist=False)


class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)
    user_name: Mapped[str] = mapped_column(String(100), nullable=False)
    user_phone: Mapped[str] = mapped_column(String(20), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    notified_24h: Mapped[bool] = mapped_column(Boolean, default=False)
    notified_2h: Mapped[bool] = mapped_column(Boolean, default=False)

    service_id: Mapped[int] = mapped_column(Integer, ForeignKey("services.id"), nullable=False)
    slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_slots.id"), unique=True, nullable=False)

    service: Mapped["Service"] = relationship(back_populates="appointments")
    slot: Mapped["ScheduleSlot"] = relationship(back_populates="appointment")
