"""
Tracks all bot status changes in groups via my_chat_member.

Three scenarios handled by a single handler (no transition filter):
  1. Bot added (any initial status)        — UPSERT, is_active depends on status
  2. Bot promoted to administrator         — UPSERT, is_active=True
  3. Bot removed / kicked / demoted        — UPSERT, is_active=False

Using one broad handler instead of JOIN_TRANSITION / LEAVE_TRANSITION ensures
that mid-membership promotions (member → administrator) are never missed.
"""
import logging
from datetime import datetime, timezone

from aiogram import Bot, Router
from aiogram.types import ChatMemberUpdated
from sqlalchemy.dialects.postgresql import insert as pg_insert

from bot.config import settings
from bot.database.db import async_session
from bot.database.models import Group

logger = logging.getLogger(__name__)

router = Router(name="chat-member")

# Bot can broadcast only when it has admin rights
_ACTIVE_STATUSES = frozenset({"administrator", "creator"})
# Bot is fully gone from the chat
_GONE_STATUSES = frozenset({"kicked", "left", "banned"})


@router.my_chat_member()
async def on_bot_status_changed(event: ChatMemberUpdated, bot: Bot) -> None:
    chat = event.chat
    if chat.type not in ("group", "supergroup"):
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    if old_status == new_status:
        return  # nothing actually changed

    now = datetime.now(timezone.utc)
    is_active = new_status in _ACTIVE_STATUSES
    removed_at = now if new_status in _GONE_STATUSES else None

    # --- UPSERT -----------------------------------------------------------
    # INSERT the row on first encounter; UPDATE all mutable fields on conflict.
    # This is atomic and works regardless of whether the row already exists.
    stmt = (
        pg_insert(Group)
        .values(
            chat_id=chat.id,
            title=chat.title or "Unknown",
            username=getattr(chat, "username", None),
            status=new_status,
            is_active=is_active,
            added_at=now,
            removed_at=removed_at,
        )
        .on_conflict_do_update(
            index_elements=["chat_id"],
            set_={
                "title": chat.title or "Unknown",
                "username": getattr(chat, "username", None),
                "status": new_status,
                "is_active": is_active,
                "removed_at": removed_at,
            },
        )
    )

    async with async_session() as session:
        await session.execute(stmt)

    logger.info(
        "Group %r (%s): %s → %s | is_active=%s",
        chat.title, chat.id, old_status, new_status, is_active,
    )

    # --- Owner notifications ----------------------------------------------
    await _notify_owner(bot, _build_notice(chat, old_status, new_status, now))


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _build_notice(chat, old_status: str, new_status: str, now: datetime) -> str | None:
    title = chat.title or str(chat.id)

    if new_status in _ACTIVE_STATUSES and old_status not in _ACTIVE_STATUSES:
        # Added fresh OR promoted from plain member / restricted
        if old_status in _GONE_STATUSES:
            verb = "добавлен в группу"
            emoji = "✅"
        else:
            verb = "повышен до администратора"
            emoji = "⬆️"
        return (
            f"{emoji} <b>Бот {verb}</b>\n"
            f"📛 Название: {title}\n"
            f"🆔 ID: <code>{chat.id}</code>\n"
            f"📊 Статус: <code>{new_status}</code>"
        )

    if new_status in _GONE_STATUSES:
        return (
            f"⚠️ <b>Бот удалён из группы</b>\n"
            f"📛 Название: {title}\n"
            f"🆔 ID: <code>{chat.id}</code>\n"
            f"🕒 Время: {now.strftime('%Y-%m-%d %H:%M:%S')} UTC"
        )

    if old_status in _ACTIVE_STATUSES and new_status not in _ACTIVE_STATUSES:
        # Demoted but still in the chat (admin → member)
        return (
            f"⬇️ <b>Бот понижен</b>\n"
            f"📛 Название: {title}\n"
            f"🆔 ID: <code>{chat.id}</code>\n"
            f"📊 Новый статус: <code>{new_status}</code>"
        )

    return None  # minor status change, no notification needed


async def _notify_owner(bot: Bot, text: str | None) -> None:
    if not text:
        return
    try:
        await bot.send_message(
            chat_id=settings.owner_id,
            text=text,
            parse_mode="HTML",
        )
    except Exception:
        logger.warning("Could not notify owner")
