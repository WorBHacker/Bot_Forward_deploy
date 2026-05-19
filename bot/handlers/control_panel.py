"""
Control Panel — Approve / Reject pending posts.
Only accessible to Owner and SuperAdmins (enforced via RBAC middleware
+ extra inline check).
"""
import json
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery
from sqlalchemy import select, update

from bot.config import settings
from bot.database.db import async_session
from bot.database.models import (
    AdminAction, BroadcastMessage, MessageStatus, UserRole,
)
from bot.services.broadcaster import BroadcastQueue

logger = logging.getLogger(__name__)

router = Router(name="control-panel")

_broadcaster: BroadcastQueue | None = None


def setup(broadcaster: BroadcastQueue) -> None:
    global _broadcaster
    _broadcaster = broadcaster


# ------------------------------------------------------------------ #
#  Moderation callbacks                                                #
# ------------------------------------------------------------------ #

@router.callback_query(F.data.startswith("moderate:"))
async def handle_moderation(
    callback: CallbackQuery, bot: Bot, user_role: UserRole | None, _: dict
) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin):
        await callback.answer(_["cp_no_rights"], show_alert=True)
        return

    _prefix, action, broadcast_id_str = callback.data.split(":")  # type: ignore[union-attr]
    broadcast_id = int(broadcast_id_str)

    async with async_session() as session:
        result = await session.execute(
            select(BroadcastMessage).where(BroadcastMessage.id == broadcast_id)
        )
        record: BroadcastMessage | None = result.scalar_one_or_none()

    if record is None:
        await callback.answer(_["cp_record_not_found"], show_alert=True)
        return

    if record.status not in (MessageStatus.pending,):
        await callback.answer(
            _["cp_already_processed"].format(status=record.status.value),
            show_alert=True,
        )
        return

    user_id = callback.from_user.id  # type: ignore[union-attr]

    if action == "approve":
        await _do_approve(bot, record, user_id, callback, _)
    elif action == "reject":
        await _do_reject(record, user_id, callback, _)


async def _do_approve(
    bot: Bot,
    record: BroadcastMessage,
    approver_id: int,
    callback: CallbackQuery,
    _: dict,
) -> None:
    async with async_session() as session:
        await session.execute(
            update(BroadcastMessage)
            .where(BroadcastMessage.id == record.id)
            .values(
                status=MessageStatus.approved,
                approved_by=approver_id,
                approved_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            AdminAction(
                user_id=approver_id,
                action_type="approve",
                target_id=record.id,
                details=f"Approved broadcast_id={record.id}",
            )
        )

    try:
        if record.media_group_ids:
            ids = json.loads(record.media_group_ids)
            messages = []
            for msg_id in ids:
                try:
                    fwd = await bot.forward_message(
                        chat_id=settings.control_panel_chat_id,
                        from_chat_id=record.master_chat_id,
                        message_id=msg_id,
                    )
                    messages.append(fwd)
                except Exception as e:
                    logger.warning("Could not forward msg %s: %s", msg_id, e)
            if messages:
                await _broadcaster.broadcast_album(messages, record.id)  # type: ignore
        else:
            fwd = await bot.forward_message(
                chat_id=settings.control_panel_chat_id,
                from_chat_id=record.master_chat_id,
                message_id=record.master_message_id,
            )
            await _broadcaster.broadcast_single(fwd, record.id)  # type: ignore
    except Exception:
        logger.exception("Approval broadcast failed for broadcast_id=%s", record.id)

    await callback.answer(_["cp_approved"])
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            callback.message.html_text + f"\n\n✅ @{callback.from_user.username or approver_id}",  # type: ignore[union-attr]
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        logger.warning("Could not edit control panel message after approval (broadcast_id=%s)", record.id)


async def _do_reject(
    record: BroadcastMessage,
    rejector_id: int,
    callback: CallbackQuery,
    _: dict,
) -> None:
    async with async_session() as session:
        await session.execute(
            update(BroadcastMessage)
            .where(BroadcastMessage.id == record.id)
            .values(
                status=MessageStatus.rejected,
                approved_by=rejector_id,
                approved_at=datetime.now(timezone.utc),
            )
        )
        session.add(
            AdminAction(
                user_id=rejector_id,
                action_type="reject",
                target_id=record.id,
                details=f"Rejected broadcast_id={record.id}",
            )
        )

    await callback.answer(_["cp_rejected"])
    try:
        await callback.message.edit_text(  # type: ignore[union-attr]
            callback.message.html_text + f"\n\n❌ @{callback.from_user.username or rejector_id}",  # type: ignore[union-attr]
            parse_mode="HTML",
            reply_markup=None,
        )
    except Exception:
        logger.warning("Could not edit control panel message after rejection (broadcast_id=%s)", record.id)
