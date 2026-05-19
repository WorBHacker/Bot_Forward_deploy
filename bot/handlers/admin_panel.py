"""
Admin Panel — commands for Owner / SuperAdmin / Admin / Guest roles.

Command table:
  /start             — everyone in hierarchy (show menu)
  /status            — Owner only (GPU / VRAM health check)
  /add_superadmin    — Owner only
  /add_admin         — Owner, SuperAdmin
  /add_guest         — Owner, SuperAdmin, Admin
  /remove_user       — Owner (delete), SuperAdmin (deactivate non-owners)
  /delete_group      — Owner only (hard delete from DB)
  /list_groups       — SuperAdmin, Admin, Owner
  /list_users        — SuperAdmin, Admin, Owner
  /broadcast         — Admin, SuperAdmin, Owner (manual text broadcast)
  /stats             — Guest+ (daily text summary on demand)
  /report            — Admin+ (trigger Excel report)
  /backup            — Owner only
  /lang              — everyone in hierarchy (change language)
"""
import logging
from datetime import datetime, timezone

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import delete, select

from bot.config import settings
from bot.database.db import async_session
from bot.database.models import (
    AdminAction, BroadcastMessage, Group, MessageStatus, User, UserRole,
)
from bot.keyboards.inline import (
    build_admin_keyboard, build_confirm_delete_keyboard, build_lang_keyboard,
)
from bot.services.analytics import AnalyticsService
from bot.services.broadcaster import BroadcastQueue
from bot.utils.backup import run_backup
from bot.utils.gpu_monitor import format_gpu_status, get_gpu_status
from bot.utils.texts import get_texts

logger = logging.getLogger(__name__)

router = Router(name="admin-panel")

_broadcaster: BroadcastQueue | None = None
_analytics: AnalyticsService | None = None


def setup(broadcaster: BroadcastQueue, analytics: AnalyticsService) -> None:
    global _broadcaster, _analytics
    _broadcaster = broadcaster
    _analytics = analytics


# ------------------------------------------------------------------ #
#  /start                                                              #
# ------------------------------------------------------------------ #

@router.message(Command("start"))
async def cmd_start(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role is None:
        return
    role_label = {
        UserRole.owner:      _["role_owner"],
        UserRole.superadmin: _["role_superadmin"],
        UserRole.admin:      _["role_admin"],
        UserRole.guest:      _["role_guest"],
    }.get(user_role, "?")

    await message.answer(
        _["start_msg"].format(role_label=role_label),
        parse_mode="HTML",
        reply_markup=build_admin_keyboard(_) if user_role != UserRole.guest else None,
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role is None:
        return
    lines = [_["help_header"], ""]
    if user_role == UserRole.guest:
        lines.append(_["help_stats_guest"])
    if user_role in (UserRole.admin, UserRole.superadmin, UserRole.owner):
        lines += [
            _["help_stats"],
            _["help_report"],
            _["help_list_groups"],
            _["help_list_users"],
            _["help_broadcast"],
            _["help_add_guest"],
        ]
    if user_role in (UserRole.superadmin, UserRole.owner):
        lines += [
            _["help_add_admin"],
            _["help_remove_user_cmd"],
        ]
    if user_role == UserRole.owner:
        lines += [
            _["help_add_superadmin"],
            _["help_delete_group"],
            _["help_status"],
            _["help_backup"],
        ]
    lines.append(_["help_lang"])
    await message.answer("\n".join(lines), parse_mode="HTML")


# ------------------------------------------------------------------ #
#  /status (Owner only)                                               #
# ------------------------------------------------------------------ #

@router.message(Command("status"))
async def cmd_status(message: Message, user_role: UserRole | None, _: dict, bot: Bot) -> None:
    if user_role != UserRole.owner:
        return
    gpus = await get_gpu_status()
    text = format_gpu_status(gpus)

    if _broadcaster:
        qsize = _broadcaster._queue.qsize()
        text += "\n\n" + _["broadcast_queue"].format(qsize=qsize)

    await message.answer(text, parse_mode="HTML")


# ------------------------------------------------------------------ #
#  User management                                                     #
# ------------------------------------------------------------------ #

@router.message(Command("add_superadmin"))
async def cmd_add_superadmin(message: Message, user_role: UserRole | None, bot: Bot, _: dict) -> None:
    if user_role != UserRole.owner:
        return
    await _add_user(message, UserRole.superadmin, bot, _)


@router.message(Command("add_admin"))
async def cmd_add_admin(message: Message, user_role: UserRole | None, bot: Bot, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin):
        return
    await _add_user(message, UserRole.admin, bot, _)


@router.message(Command("add_guest"))
async def cmd_add_guest(message: Message, user_role: UserRole | None, bot: Bot, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin, UserRole.admin):
        return
    await _add_user(message, UserRole.guest, bot, _)


async def _add_user(message: Message, target_role: UserRole, bot: Bot, _: dict) -> None:
    args = (message.text or "").split()
    if len(args) < 2:
        await message.answer(
            _["usage_add_user"].format(cmd=args[0]),
            parse_mode="HTML",
        )
        return

    arg = args[1]
    caller_id = message.from_user.id  # type: ignore[union-attr]
    target_id: int | None = None

    if arg.lstrip("-").isdigit():
        target_id = int(arg)
    else:
        username = arg.lstrip("@")
        async with async_session() as session:
            result = await session.execute(
                select(User).where(User.username == username)
            )
            found: User | None = result.scalar_one_or_none()
        if found:
            target_id = found.user_id
        else:
            try:
                chat = await bot.get_chat(f"@{username}")
                target_id = chat.id
            except Exception:
                await message.answer(
                    _["err_user_not_found_api"].format(arg=arg),
                    parse_mode="HTML",
                )
                return

    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == target_id))
        existing: User | None = result.scalar_one_or_none()

        if existing:
            if existing.role == UserRole.owner:
                await message.answer(_["err_change_owner_role"])
                return
            if existing.role == target_role and existing.is_active:
                role_label = target_role.value.capitalize()
                await message.answer(
                    _["err_already_has_role"].format(
                        target_id=target_id, role_label=role_label
                    ),
                    parse_mode="HTML",
                )
                return
            existing.role = target_role
            existing.is_active = True
            action = "updated"
        else:
            session.add(User(
                user_id=target_id,
                role=target_role,
                added_by=caller_id,
                is_active=True,
            ))
            action = "created"

        session.add(
            AdminAction(
                user_id=caller_id,
                action_type=f"add_{target_role.value}",
                target_id=target_id,
                details=f"{action} user with role={target_role.value}",
            )
        )

    role_label = target_role.value.capitalize()
    await message.answer(
        _["ok_user_assigned"].format(target_id=target_id, role_label=role_label),
        parse_mode="HTML",
    )


@router.message(Command("remove_user"))
async def cmd_remove_user(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin):
        return

    args = (message.text or "").split()
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        await message.answer(_["usage_remove_user"], parse_mode="HTML")
        return

    target_id = int(args[1])
    caller_id = message.from_user.id  # type: ignore[union-attr]

    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == target_id))
        target: User | None = result.scalar_one_or_none()

        if target is None:
            await message.answer(_["err_user_not_found"])
            return
        if target.role == UserRole.owner:
            await message.answer(_["err_delete_owner"])
            return
        if user_role == UserRole.superadmin and target.role in (UserRole.superadmin, UserRole.owner):
            await message.answer(_["err_superadmin_delete_restricted"])
            return

        if user_role == UserRole.owner:
            await session.execute(delete(User).where(User.user_id == target_id))
        else:
            target.is_active = False

        session.add(
            AdminAction(
                user_id=caller_id,
                action_type="remove_user",
                target_id=target_id,
            )
        )

    await message.answer(
        _["ok_user_removed"].format(target_id=target_id),
        parse_mode="HTML",
    )


# ------------------------------------------------------------------ #
#  Group management                                                    #
# ------------------------------------------------------------------ #

@router.message(Command("list_groups"))
async def cmd_list_groups(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin, UserRole.admin):
        return

    async with async_session() as session:
        result = await session.execute(select(Group).order_by(Group.is_active.desc(), Group.title))
        groups = list(result.scalars().all())

    if not groups:
        await message.answer(_["no_groups"])
        return

    lines = [_["groups_header"].format(count=len(groups))]
    for g in groups[:50]:
        status = "✅" if g.is_active else "❌"
        lines.append(f"{status} {g.title} — <code>{g.chat_id}</code>")

    if len(groups) > 50:
        lines.append(_["groups_overflow"].format(n=len(groups) - 50))

    await message.answer("\n".join(lines), parse_mode="HTML")


@router.message(Command("delete_group"))
async def cmd_delete_group(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role != UserRole.owner:
        return

    args = (message.text or "").split()
    if len(args) < 2 or not args[1].lstrip("-").isdigit():
        await message.answer(_["usage_delete_group"], parse_mode="HTML")
        return

    chat_id = int(args[1])
    async with async_session() as session:
        result = await session.execute(select(Group).where(Group.chat_id == chat_id))
        group: Group | None = result.scalar_one_or_none()

    if group is None:
        await message.answer(_["err_group_not_found"])
        return

    await message.answer(
        _["confirm_delete_group"].format(title=group.title, chat_id=group.chat_id),
        parse_mode="HTML",
        reply_markup=build_confirm_delete_keyboard(chat_id, _),
    )


@router.callback_query(F.data.startswith("owner:delete_group:"))
async def cb_confirm_delete_group(callback: CallbackQuery, user_role: UserRole | None, _: dict) -> None:
    if user_role != UserRole.owner:
        await callback.answer(_["cb_owner_only"], show_alert=True)
        return

    chat_id = int(callback.data.split(":")[2])  # type: ignore[union-attr]
    async with async_session() as session:
        await session.execute(delete(Group).where(Group.chat_id == chat_id))

    await callback.answer(_["cb_group_deleted_toast"])
    await callback.message.edit_text(  # type: ignore[union-attr]
        _["ok_group_deleted"].format(chat_id=chat_id),
        parse_mode="HTML",
        reply_markup=None,
    )


@router.callback_query(F.data == "owner:cancel")
async def cb_cancel(callback: CallbackQuery, _: dict) -> None:
    await callback.answer(_["cb_cancelled"])
    await callback.message.delete()  # type: ignore[union-attr]


# ------------------------------------------------------------------ #
#  Listing users                                                       #
# ------------------------------------------------------------------ #

@router.message(Command("list_users"))
async def cmd_list_users(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin, UserRole.admin):
        return

    async with async_session() as session:
        result = await session.execute(select(User).order_by(User.role, User.user_id))
        users = list(result.scalars().all())

    if not users:
        await message.answer(_["no_users"])
        return

    lines = [_["users_header"].format(count=len(users))]
    for u in users:
        status = "✅" if u.is_active else "❌"
        name = u.full_name or u.username or f"id:{u.user_id}"
        lines.append(f"{status} [{u.role.value}] {name} — <code>{u.user_id}</code>")

    await message.answer("\n".join(lines), parse_mode="HTML")


# ------------------------------------------------------------------ #
#  Manual broadcast                                                    #
# ------------------------------------------------------------------ #

@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin, UserRole.admin):
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(_["usage_broadcast"], parse_mode="HTML")
        return

    text = parts[1]
    caller_id = message.from_user.id  # type: ignore[union-attr]

    async with async_session() as session:
        record = BroadcastMessage(
            master_message_id=0,
            master_chat_id=caller_id,
            content_preview=text[:200],
            status=MessageStatus.approved,
            approved_by=caller_id,
            approved_at=datetime.now(timezone.utc),
        )
        session.add(record)
        await session.flush()
        broadcast_id = record.id
        session.add(
            AdminAction(
                user_id=caller_id,
                action_type="manual_broadcast",
                target_id=broadcast_id,
                details=text[:200],
            )
        )

    await _broadcaster.broadcast_text(text, broadcast_id)  # type: ignore[union-attr]
    await message.answer(_["ok_broadcast_queued"])


# ------------------------------------------------------------------ #
#  Stats / Report                                                      #
# ------------------------------------------------------------------ #

@router.message(Command("stats"))
async def cmd_stats(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role is None:
        return
    await _analytics.send_daily_summary()  # type: ignore[union-attr]
    await message.answer(_["ok_stats_sent"])


@router.message(Command("report"))
async def cmd_report(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role not in (UserRole.owner, UserRole.superadmin, UserRole.admin):
        return
    await message.answer(_["ok_report_generating"])
    await _analytics.send_excel_report()  # type: ignore[union-attr]


# ------------------------------------------------------------------ #
#  Backup                                                              #
# ------------------------------------------------------------------ #

@router.message(Command("backup"))
async def cmd_backup(message: Message, user_role: UserRole | None, _: dict, bot: Bot) -> None:
    if user_role != UserRole.owner:
        return
    await message.answer(_["ok_backup_start"])
    await run_backup(bot)


# ------------------------------------------------------------------ #
#  Language selection                                                  #
# ------------------------------------------------------------------ #

@router.message(Command("lang"))
async def cmd_lang(message: Message, user_role: UserRole | None, _: dict) -> None:
    if user_role is None:
        return
    await message.answer(_["lang_select"], reply_markup=build_lang_keyboard())


@router.callback_query(F.data.startswith("lang:"))
async def cb_set_lang(callback: CallbackQuery, user_role: UserRole | None) -> None:
    if user_role is None:
        await callback.answer()
        return

    lang = callback.data.split(":")[1]  # type: ignore[union-attr]
    user_id = callback.from_user.id  # type: ignore[union-attr]

    async with async_session() as session:
        result = await session.execute(select(User).where(User.user_id == user_id))
        db_user: User | None = result.scalar_one_or_none()
        if db_user:
            db_user.language_code = lang

    new_texts = get_texts(lang)
    key = "lang_set_ru" if lang == "ru" else "lang_set_uz"
    await callback.answer()
    await callback.message.edit_text(new_texts[key], parse_mode="HTML")  # type: ignore[union-attr]


# ------------------------------------------------------------------ #
#  Inline button callbacks (from build_admin_keyboard)                 #
# ------------------------------------------------------------------ #

@router.callback_query(F.data == "admin:list_groups")
async def cb_list_groups(callback: CallbackQuery, user_role: UserRole | None, _: dict) -> None:
    await callback.answer()
    await cmd_list_groups(callback.message, user_role, _)  # type: ignore[arg-type]


@router.callback_query(F.data == "admin:list_users")
async def cb_list_users(callback: CallbackQuery, user_role: UserRole | None, _: dict) -> None:
    await callback.answer()
    await cmd_list_users(callback.message, user_role, _)  # type: ignore[arg-type]


@router.callback_query(F.data == "admin:excel_report")
async def cb_excel_report(callback: CallbackQuery, user_role: UserRole | None, _: dict) -> None:
    await callback.answer(_["cb_generating"])
    await _analytics.send_excel_report()  # type: ignore[union-attr]


@router.callback_query(F.data == "admin:status")
async def cb_status(callback: CallbackQuery, user_role: UserRole | None, _: dict, bot: Bot) -> None:
    if user_role != UserRole.owner:
        await callback.answer(_["cb_owner_only"], show_alert=True)
        return
    await callback.answer()
    gpus = await get_gpu_status()
    await callback.message.answer(format_gpu_status(gpus), parse_mode="HTML")  # type: ignore[union-attr]
