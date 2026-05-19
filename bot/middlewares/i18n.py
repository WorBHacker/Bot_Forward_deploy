from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.database.models import User
from bot.utils.texts import get_texts


class I18nMiddleware(BaseMiddleware):
    """
    Injects the localized string dict under the key ``_`` into handler data.
    Must be registered AFTER RBACMiddleware so that ``data['db_user']`` is
    already populated when this middleware runs.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        db_user: User | None = data.get("db_user")
        lang = db_user.language_code if db_user else "ru"
        data["_"] = get_texts(lang)
        return await handler(event, data)
