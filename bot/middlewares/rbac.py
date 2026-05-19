import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy import select

from bot.config import settings
from bot.database.db import async_session
from bot.database.models import User, UserRole

logger = logging.getLogger(__name__)

# Commands that are accessible to everyone (e.g. /start for initial owner setup)
PUBLIC_COMMANDS = {"/start"}


class RBACMiddleware(BaseMiddleware):
    """
    Attaches the resolved User (or None) and their UserRole to handler data.
    Drops updates from users not in the hierarchy, except for PUBLIC_COMMANDS.
    The owner is always injected even if absent from the DB (bootstrapping).
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        # Resolve sender for Message and CallbackQuery
        from_user = None
        if isinstance(event, Message):
            from_user = event.from_user
        elif isinstance(event, CallbackQuery):
            from_user = event.from_user

        if from_user is None:
            # Channel posts, etc. — let pass (handled by separate filter)
            return await handler(event, data)

        user_id = from_user.id

        # Owner is always allowed — may not exist in DB yet
        if user_id == settings.owner_id:
            db_user = await self._get_or_create_owner(from_user)
            data["db_user"] = db_user
            data["user_role"] = UserRole.owner
            return await handler(event, data)

        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.user_id == user_id, User.is_active == True)
            )
            db_user: User | None = result.scalar_one_or_none()

        if db_user is None:
            # Unknown user — ignore silently (per spec)
            text = None
            if isinstance(event, Message):
                text = event.text or ""
                if (text.split()[0] if text.split() else "") in PUBLIC_COMMANDS:
                    data["db_user"] = None
                    data["user_role"] = None
                    return await handler(event, data)
            logger.debug("Ignored update from unknown user %s", user_id)
            return None

        data["db_user"] = db_user
        data["user_role"] = db_user.role
        return await handler(event, data)

    async def _get_or_create_owner(self, from_user) -> User:
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.user_id == settings.owner_id)
            )
            owner = result.scalar_one_or_none()
            if owner is None:
                owner = User(
                    user_id=settings.owner_id,
                    username=from_user.username,
                    full_name=from_user.full_name,
                    role=UserRole.owner,
                    is_active=True,
                )
                session.add(owner)
                await session.commit()
                logger.info("Owner record auto-created for user_id=%s", settings.owner_id)
            return owner
