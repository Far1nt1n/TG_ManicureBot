from typing import Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery, TelegramObject
from aiogram.enums.chat_member_status import ChatMemberStatus

from config import ADMIN_ID, CHANNEL_USERNAME


class SubscriptionCheckMiddleware(BaseMiddleware):
    def __init__(self, bot):
        self.bot = bot
        super().__init__()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict], Awaitable[None]],
        event: TelegramObject,
        data: dict,
    ) -> None:
        user_id = None
        if isinstance(event, Message):
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            user_id = event.from_user.id

        if user_id and user_id == ADMIN_ID:
            return await handler(event, data)

        if isinstance(event, Message) and event.text == "/start":
            return await handler(event, data)

        if isinstance(event, CallbackQuery) and event.data == "check_subscription":
            return await handler(event, data)

        if user_id:
            try:
                member = await self.bot.get_chat_member(chat_id=CHANNEL_USERNAME, user_id=user_id)
                if member.status in (ChatMemberStatus.LEFT, ChatMemberStatus.KICKED):
                    await self._ask_subscribe(event)
                    return
            except Exception:
                await self._ask_subscribe(event)
                return

        await handler(event, data)

    async def _ask_subscribe(self, event: TelegramObject):
        from keyboards.client_kb import subscription_check_kb

        text = (
            f"📢 Для использования бота необходимо подписаться на канал:\n"
            f"{CHANNEL_USERNAME}\n\n"
            f"После подписки нажми «✅ Я подписался»"
        )
        if isinstance(event, Message):
            await event.answer(text, reply_markup=subscription_check_kb(CHANNEL_USERNAME))
        elif isinstance(event, CallbackQuery):
            await event.answer()
            await event.message.answer(text, reply_markup=subscription_check_kb(CHANNEL_USERNAME))
