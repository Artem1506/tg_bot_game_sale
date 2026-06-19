import logging
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message

logger = logging.getLogger("bot.requests")

class RequestLoggingMiddleware(BaseMiddleware):
    """Middleware для логирования входящих сообщений (запросов) к боту."""

    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            user = event.from_user
            if user:
                user_info = f"ID: {user.id}"
                if user.username:
                    user_info += f" (@{user.username})"
                if user.first_name:
                    user_info += f" {user.first_name}"
                if user.last_name:
                    user_info += f" {user.last_name}"
            else:
                user_info = "Неизвестный пользователь"

            chat_info = f"Chat ID: {event.chat.id}"
            if event.chat.title:
                chat_info += f" ({event.chat.title})"
            elif event.chat.type == "private":
                chat_info += " (private)"

            logger.info(
                "Получен запрос от пользователя [%s] в чате [%s]: %s",
                user_info,
                chat_info,
                event.text or "[без текста]"
            )
        return await handler(event, data)
