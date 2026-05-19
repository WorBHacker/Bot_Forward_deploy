import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import List, Optional

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter
from aiogram.types import (
    InputMediaPhoto, InputMediaVideo, InputMediaDocument,
    InputMediaAudio, InputMediaAnimation, Message,
)
from sqlalchemy import select, update

from bot.config import settings
from bot.database.db import async_session
from bot.database.models import Group, BroadcastMessage, MessageStat, MessageStatus, AnalyticsSource

logger = logging.getLogger(__name__)

# Map content_type → InputMedia class
_MEDIA_MAP = {
    "photo": InputMediaPhoto,
    "video": InputMediaVideo,
    "document": InputMediaDocument,
    "audio": InputMediaAudio,
    "animation": InputMediaAnimation,
}


def _build_input_media(msg: Message, caption: Optional[str] = None, is_first: bool = False):
    """Convert a Message into an InputMedia* object for send_media_group."""
    content_type = msg.content_type
    cls = _MEDIA_MAP.get(content_type)
    if cls is None:
        return None

    media_id: str
    if content_type == "photo":
        media_id = msg.photo[-1].file_id  # type: ignore[index]
    elif content_type == "video":
        media_id = msg.video.file_id  # type: ignore[union-attr]
    elif content_type == "document":
        media_id = msg.document.file_id  # type: ignore[union-attr]
    elif content_type == "audio":
        media_id = msg.audio.file_id  # type: ignore[union-attr]
    elif content_type == "animation":
        media_id = msg.animation.file_id  # type: ignore[union-attr]
    else:
        return None

    kwargs = {"media": media_id, "parse_mode": "HTML"}
    if is_first and caption is not None:
        kwargs["caption"] = caption
    return cls(**kwargs)  # type: ignore[arg-type]


class BroadcastQueue:
    """
    Token-bucket based broadcaster that respects Telegram's 30 msg/s global
    and 1 msg/s per-chat limits, with automatic retry on flood-wait errors.
    """

    def __init__(self, bot: Bot, rate_limit: int = 25) -> None:
        self._bot = bot
        self._rate_limit = rate_limit  # msgs/second (global)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._worker_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------ #
    #  Lifecycle                                                           #
    # ------------------------------------------------------------------ #

    async def start(self) -> None:
        self._running = True
        self._worker_task = asyncio.create_task(self._worker(), name="broadcaster-worker")
        logger.info("BroadcastQueue started (rate=%d msg/s)", self._rate_limit)

    async def stop(self) -> None:
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    async def broadcast_single(
        self,
        message: Message,
        broadcast_id: int,
    ) -> None:
        """Queue a single (non-album) message for broadcasting."""
        async with async_session() as session:
            result = await session.execute(
                select(Group).where(Group.is_active == True)
            )
            groups: List[Group] = list(result.scalars().all())

        for group in groups:
            await self._queue.put(
                ("single", message, group.chat_id, broadcast_id)
            )

        await self._finalize_broadcast(broadcast_id)
        logger.info("Queued single message for %d groups", len(groups))

    async def broadcast_album(
        self,
        messages: List[Message],
        broadcast_id: int,
    ) -> None:
        """Queue a media group (album) for broadcasting."""
        async with async_session() as session:
            result = await session.execute(
                select(Group).where(Group.is_active == True)
            )
            groups: List[Group] = list(result.scalars().all())

        for group in groups:
            await self._queue.put(
                ("album", messages, group.chat_id, broadcast_id)
            )

        await self._finalize_broadcast(broadcast_id)
        logger.info("Queued album (%d parts) for %d groups", len(messages), len(groups))

    async def broadcast_text(
        self,
        text: str,
        broadcast_id: int,
        parse_mode: str = "HTML",
    ) -> None:
        """Queue a plain-text admin message for all groups."""
        async with async_session() as session:
            result = await session.execute(
                select(Group).where(Group.is_active == True)
            )
            groups: List[Group] = list(result.scalars().all())

        for group in groups:
            await self._queue.put(
                ("text", text, group.chat_id, broadcast_id, parse_mode)
            )

        logger.info("Queued text broadcast for %d groups", len(groups))

    # ------------------------------------------------------------------ #
    #  Worker                                                              #
    # ------------------------------------------------------------------ #

    async def _worker(self) -> None:
        interval = 1.0 / self._rate_limit  # seconds between sends
        while self._running:
            try:
                task = await asyncio.wait_for(self._queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            await self._dispatch(task)
            self._queue.task_done()
            await asyncio.sleep(interval)

    async def _dispatch(self, task: tuple) -> None:
        kind = task[0]
        try:
            if kind == "single":
                _, message, chat_id, broadcast_id = task
                await self._send_single(message, chat_id, broadcast_id)
            elif kind == "album":
                _, messages, chat_id, broadcast_id = task
                await self._send_album(messages, chat_id, broadcast_id)
            elif kind == "text":
                _, text, chat_id, broadcast_id, parse_mode = task
                await self._send_text(text, chat_id, broadcast_id, parse_mode)
        except Exception:
            logger.exception("Unhandled error dispatching task kind=%s", kind)

    # ------------------------------------------------------------------ #
    #  Per-type senders                                                    #
    # ------------------------------------------------------------------ #

    async def _send_single(self, message: Message, chat_id: int, broadcast_id: int) -> None:
        hub_id = settings.analytics_hub_channel_id
        sent = None
        hub_msg_id: Optional[int] = None

        # Step 1: copy to hub channel (errors here must NOT mark the group inactive)
        if hub_id:
            try:
                hub = await self._bot.copy_message(
                    chat_id=hub_id,
                    from_chat_id=message.chat.id,
                    message_id=message.message_id,
                )
                hub_msg_id = hub.message_id
            except Exception as e:
                logger.warning("Hub channel copy failed (hub=%s): %s — falling back to direct send", hub_id, e)
                hub_id = None  # fall back to direct copy_to

        # Step 2: send to group
        try:
            if hub_id and hub_msg_id:
                sent = await self._bot.forward_message(
                    chat_id=chat_id,
                    from_chat_id=hub_id,
                    message_id=hub_msg_id,
                )
            else:
                sent = await message.copy_to(chat_id)
        except TelegramForbiddenError:
            await self._mark_group_inactive(chat_id)
        except TelegramRetryAfter as e:
            logger.warning("Flood wait %ss for chat %s", e.retry_after, chat_id)
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                if hub_id and hub_msg_id:
                    sent = await self._bot.forward_message(
                        chat_id=chat_id, from_chat_id=hub_id, message_id=hub_msg_id
                    )
                else:
                    sent = await message.copy_to(chat_id)
            except Exception:
                logger.exception("Retry failed for chat %s", chat_id)
        except TelegramBadRequest as e:
            logger.warning("BadRequest for chat %s: %s", chat_id, e)
        except Exception:
            logger.exception("Error sending single to chat %s", chat_id)

        if sent:
            await self._record_stat(broadcast_id, chat_id, sent.message_id)
            if hub_msg_id:
                await self._record_analytics_source(broadcast_id, chat_id, hub_msg_id)

    async def _send_album(self, messages: List[Message], chat_id: int, broadcast_id: int) -> None:
        caption = (messages[0].caption or messages[0].text) if messages else None
        media = []
        for i, msg in enumerate(messages):
            item = _build_input_media(msg, caption=caption, is_first=(i == 0))
            if item:
                media.append(item)

        if not media:
            return

        sent_msgs = None
        try:
            sent_msgs = await self._bot.send_media_group(chat_id=chat_id, media=media)
        except TelegramForbiddenError:
            await self._mark_group_inactive(chat_id)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                sent_msgs = await self._bot.send_media_group(chat_id=chat_id, media=media)
            except Exception:
                logger.exception("Retry album failed for chat %s", chat_id)
        except TelegramBadRequest as e:
            logger.warning("BadRequest album for chat %s: %s", chat_id, e)
        except Exception:
            logger.exception("Error sending album to chat %s", chat_id)

        if sent_msgs:
            await self._record_stat(broadcast_id, chat_id, sent_msgs[0].message_id)

    async def _send_text(self, text: str, chat_id: int, broadcast_id: int, parse_mode: str) -> None:
        sent = None
        try:
            sent = await self._bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
        except TelegramForbiddenError:
            await self._mark_group_inactive(chat_id)
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 0.5)
            try:
                sent = await self._bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
            except Exception:
                logger.exception("Retry text failed for chat %s", chat_id)
        except Exception:
            logger.exception("Error sending text to chat %s", chat_id)

        if sent:
            await self._record_stat(broadcast_id, chat_id, sent.message_id)

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    async def _record_analytics_source(
        self, broadcast_id: int, group_id: int, hub_message_id: int
    ) -> None:
        username = settings.analytics_hub_channel_username
        url = f"https://t.me/{username}/{hub_message_id}" if username else None
        async with async_session() as session:
            session.add(
                AnalyticsSource(
                    broadcast_id=broadcast_id,
                    group_id=group_id,
                    hub_message_id=hub_message_id,
                    hub_message_url=url,
                )
            )

    async def _record_stat(self, broadcast_id: int, group_id: int, message_id: int) -> None:
        try:
            members = await self._bot.get_chat_member_count(group_id)
        except Exception:
            members = 0
        async with async_session() as session:
            stat = MessageStat(
                broadcast_id=broadcast_id,
                group_id=group_id,
                telegram_message_id=message_id,
                views=0,
                member_count=members,
                last_updated=datetime.now(timezone.utc),
            )
            session.add(stat)

    async def _finalize_broadcast(self, broadcast_id: int) -> None:
        async with async_session() as session:
            await session.execute(
                update(BroadcastMessage)
                .where(BroadcastMessage.id == broadcast_id)
                .values(status=MessageStatus.sent)
            )

    async def _mark_group_inactive(self, chat_id: int) -> None:
        from bot.config import settings as cfg
        logger.warning("Bot was removed from chat %s — marking inactive", chat_id)
        async with async_session() as session:
            result = await session.execute(
                select(Group).where(Group.chat_id == chat_id)
            )
            group = result.scalar_one_or_none()
            if group and group.is_active:
                group.is_active = False
                group.removed_at = datetime.now(timezone.utc)
