"""
Handles every post that arrives in the Master Channel.

Flow:
  1. Media group?  → buffer via MediaGroupCollector, then process album.
     Single message? → process immediately.
  2. Run censorship checks (text + media) inside a single try/except block.
       - CensorshipError → check_failed=True, route to manual review.
       - Clean result, is_safe=False → route to manual review.
       - Clean result, is_safe=True → enqueue broadcast.
  3. Post is NEVER auto-approved if any check stage raised CensorshipError.
"""
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from aiogram import Bot, F, Router
from aiogram.types import Message
from sqlalchemy import select, update

from bot.config import settings

from bot.database.db import async_session
from bot.database.models import BroadcastMessage, MessageStatus, User, UserRole
from bot.keyboards.inline import build_moderation_keyboard
from bot.services.broadcaster import BroadcastQueue
from bot.services.censorship import CensorshipError, CensorshipResult, CensorshipService
from bot.services.media_collector import MediaGroupCollector

logger = logging.getLogger(__name__)

router = Router(name="master-channel")

_collector: Optional[MediaGroupCollector] = None
_censor: Optional[CensorshipService] = None
_broadcaster: Optional[BroadcastQueue] = None


def setup(
    collector: MediaGroupCollector,
    censor: CensorshipService,
    broadcaster: BroadcastQueue,
) -> None:
    global _collector, _censor, _broadcaster
    _collector = collector
    _censor = censor
    _broadcaster = broadcaster


# ------------------------------------------------------------------ #
#  Filter: only Master Channel                                         #
# ------------------------------------------------------------------ #

@router.channel_post(F.chat.id == settings.master_channel_id)
async def handle_master_post(message: Message, bot: Bot) -> None:
    if message.media_group_id:
        await _collector.collect(message, _on_album_ready)  # type: ignore[union-attr]
    else:
        await _process_single(message, bot)


@router.edited_channel_post(F.chat.id == settings.master_channel_id)
async def handle_master_edit(message: Message, bot: Bot) -> None:
    """Passive view capture: update channel_views when a post is edited."""
    views = getattr(message, 'views', None)
    if views is None:
        return
    async with async_session() as session:
        await session.execute(
            update(BroadcastMessage)
            .where(
                BroadcastMessage.master_message_id == message.message_id,
                BroadcastMessage.master_chat_id == message.chat.id,
            )
            .values(
                channel_views=views,
                views_synced_at=datetime.now(timezone.utc),
            )
        )


# ------------------------------------------------------------------ #
#  Processing                                                          #
# ------------------------------------------------------------------ #

async def _process_single(message: Message, bot: Bot) -> None:
    text = message.caption or message.text or ""
    content_full = message.html_text or message.html_caption or ""
    censor_result, check_failed = await _run_censorship_single(message, bot, text)

    broadcast_id = await _create_broadcast_record(
        master_message_id=message.message_id,
        master_chat_id=message.chat.id,
        content_preview=text[:200],
        content_full=content_full,
        channel_views=getattr(message, 'views', None) or 0,
        censor_result=censor_result,
    )

    if censor_result.is_safe:
        await _broadcaster.broadcast_single(message, broadcast_id)  # type: ignore[union-attr]
        logger.info("Single message %s auto-approved and queued", message.message_id)
    else:
        await _send_to_control_panel(
            bot, message, broadcast_id, censor_result,
            is_album=False, check_failed=check_failed,
        )


async def _on_album_ready(messages: List[Message]) -> None:
    """Callback from MediaGroupCollector once the album is complete."""
    bot: Bot = messages[0].bot  # type: ignore[assignment]
    first = messages[0]
    text = first.caption or ""

    content_full = first.html_text or first.html_caption or ""
    censor_result, check_failed = await _run_censorship_album(first, bot, text)

    media_ids = [m.message_id for m in messages]
    broadcast_id = await _create_broadcast_record(
        master_message_id=first.message_id,
        master_chat_id=first.chat.id,
        content_preview=text[:200],
        content_full=content_full,
        channel_views=getattr(first, 'views', None) or 0,
        censor_result=censor_result,
        media_group_ids=media_ids,
    )

    if censor_result.is_safe:
        await _broadcaster.broadcast_album(messages, broadcast_id)  # type: ignore[union-attr]
        logger.info("Album %s auto-approved and queued", first.media_group_id)
    else:
        await _send_to_control_panel(
            bot, first, broadcast_id, censor_result,
            is_album=True, album_messages=messages, check_failed=check_failed,
        )


# ------------------------------------------------------------------ #
#  Censorship wrappers (fail-closed)                                  #
# ------------------------------------------------------------------ #

async def _run_censorship_single(
    message: Message, bot: Bot, text: str
) -> tuple[CensorshipResult, bool]:
    """
    Run all censorship checks for a single message.
    Returns (result, check_failed).
    check_failed=True means a CensorshipError was raised — post must go to
    manual review regardless of is_safe.
    """
    try:
        result = await _censor.check_text(text)  # type: ignore[union-attr]

        if result.is_safe and message.photo:
            file = await bot.get_file(message.photo[-1].file_id)
            file_url = (
                f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
            )
            result = await _censor.check_image_url(file_url)  # type: ignore[union-attr]

        elif result.is_safe and message.video:
            file = await bot.get_file(message.video.file_id)
            file_url = (
                f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
            )
            result = await _censor.check_video_url(file_url)  # type: ignore[union-attr]

        return result, False

    except CensorshipError as exc:
        logger.error(
            "Censorship check FAILED for message %s: %s — routing to manual review",
            message.message_id, exc,
        )
        return CensorshipResult(
            is_safe=False,
            reason=f"Ошибка проверки: {exc}",
        ), True


async def _run_censorship_album(
    first: Message, bot: Bot, text: str
) -> tuple[CensorshipResult, bool]:
    """Same as _run_censorship_single but operates on the first album frame."""
    try:
        result = await _censor.check_text(text)  # type: ignore[union-attr]

        if result.is_safe and first.photo:
            file = await bot.get_file(first.photo[-1].file_id)
            file_url = (
                f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
            )
            result = await _censor.check_image_url(file_url)  # type: ignore[union-attr]

        elif result.is_safe and first.video:
            file = await bot.get_file(first.video.file_id)
            file_url = (
                f"https://api.telegram.org/file/bot{settings.bot_token}/{file.file_path}"
            )
            result = await _censor.check_video_url(file_url)  # type: ignore[union-attr]

        return result, False

    except CensorshipError as exc:
        logger.error(
            "Censorship check FAILED for album (first_msg=%s): %s — routing to manual review",
            first.message_id, exc,
        )
        return CensorshipResult(
            is_safe=False,
            reason=f"Ошибка проверки: {exc}",
        ), True


# ------------------------------------------------------------------ #
#  Private staff notifications                                         #
# ------------------------------------------------------------------ #

async def _notify_staff_privately(
    bot: Bot,
    notice: str,
    broadcast_id: int,
    message: Message,
    is_album: bool,
    album_messages: Optional[List[Message]] = None,
) -> None:
    """Send censorship alert to owner/superadmin/admin in their private chats."""
    async with async_session() as session:
        result = await session.execute(
            select(User).where(
                User.is_active == True,
                User.role.in_([UserRole.owner, UserRole.superadmin, UserRole.admin]),
            )
        )
        staff = list(result.scalars().all())

    for user in staff:
        try:
            if is_album and album_messages:
                await bot.forward_messages(
                    chat_id=user.user_id,
                    from_chat_id=message.chat.id,
                    message_ids=[m.message_id for m in album_messages],
                )
            else:
                await bot.forward_message(
                    chat_id=user.user_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
            kb = (
                build_moderation_keyboard(broadcast_id)
                if user.role in (UserRole.owner, UserRole.superadmin)
                else None
            )
            await bot.send_message(
                chat_id=user.user_id,
                text=notice,
                parse_mode="HTML",
                reply_markup=kb,
            )
        except Exception:
            logger.warning(
                "Could not send private censorship alert to user_id=%s", user.user_id
            )


# ------------------------------------------------------------------ #
#  DB helpers                                                          #
# ------------------------------------------------------------------ #

async def _create_broadcast_record(
    master_message_id: int,
    master_chat_id: int,
    content_preview: str,
    censor_result: CensorshipResult,
    content_full: str = "",
    channel_views: int = 0,
    media_group_ids: Optional[List[int]] = None,
) -> int:
    status = MessageStatus.approved if censor_result.is_safe else MessageStatus.pending
    async with async_session() as session:
        record = BroadcastMessage(
            master_message_id=master_message_id,
            master_chat_id=master_chat_id,
            media_group_ids=json.dumps(media_group_ids) if media_group_ids else None,
            content_preview=content_preview,
            content_full=content_full or None,
            channel_views=channel_views,
            status=status,
            censorship_triggered=not censor_result.is_safe,
            censorship_reason=censor_result.reason,
            created_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        broadcast_id = record.id
    return broadcast_id


# ------------------------------------------------------------------ #
#  Control panel notification                                          #
# ------------------------------------------------------------------ #

async def _send_to_control_panel(
    bot: Bot,
    message: Message,
    broadcast_id: int,
    censor_result: CensorshipResult,
    is_album: bool,
    check_failed: bool = False,
    album_messages: Optional[List[Message]] = None,
) -> None:
    label = "Альбом" if is_album else "Пост"
    preview = message.caption or message.text or "(медиа без текста)"

    if check_failed:
        header = (
            "🚫 <b>Ошибка автоматической проверки</b>\n"
            "⚠️ Пост задержан для ручного решения."
        )
    else:
        header = "⚠️ <b>Пост заблокирован цензурой</b>"

    notice = (
        f"{header}\n\n"
        f"📌 Тип: {label}\n"
        f"🔍 Причина: <code>{censor_result.reason}</code>\n\n"
        f"📝 Превью:\n<blockquote>{preview[:300]}</blockquote>\n\n"
        f"ID записи: <code>{broadcast_id}</code>"
    )

    kb = build_moderation_keyboard(broadcast_id)

    try:
        if is_album and album_messages:
            await bot.forward_messages(
                chat_id=settings.control_panel_chat_id,
                from_chat_id=message.chat.id,
                message_ids=[m.message_id for m in album_messages],
            )
        else:
            await bot.forward_message(
                chat_id=settings.control_panel_chat_id,
                from_chat_id=message.chat.id,
                message_id=message.message_id,
            )

        ctrl_msg = await bot.send_message(
            chat_id=settings.control_panel_chat_id,
            text=notice,
            parse_mode="HTML",
            reply_markup=kb,
        )

        async with async_session() as session:
            await session.execute(
                update(BroadcastMessage)
                .where(BroadcastMessage.id == broadcast_id)
                .values(control_panel_message_id=ctrl_msg.message_id)
            )

    except Exception:
        logger.exception(
            "Failed to send post to control panel (broadcast_id=%s)", broadcast_id
        )

    await _notify_staff_privately(
        bot, notice, broadcast_id, message, is_album, album_messages
    )
