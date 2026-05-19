from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.utils.texts import get_texts


def build_lang_keyboard() -> InlineKeyboardMarkup:
    """Language selector — labels shown in both languages regardless of current locale."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang:uz"),
    )
    return builder.as_markup()


def build_moderation_keyboard(broadcast_id: int, _: dict | None = None) -> InlineKeyboardMarkup:
    """Approve / Reject buttons for the control panel.

    ``_`` is optional: when called from master_channel (no user context) it
    defaults to Russian; when called with a user's ``_`` dict it localises.
    """
    t = _ or get_texts("ru")
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=t["btn_approve"],
            callback_data=f"moderate:approve:{broadcast_id}",
        ),
        InlineKeyboardButton(
            text=t["btn_reject"],
            callback_data=f"moderate:reject:{broadcast_id}",
        ),
    )
    return builder.as_markup()


def build_admin_keyboard(_: dict) -> InlineKeyboardMarkup:
    """Quick-action keyboard for superadmins / admins."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=_["btn_list_groups"], callback_data="admin:list_groups"),
        InlineKeyboardButton(text=_["btn_list_users"],  callback_data="admin:list_users"),
    )
    builder.row(
        InlineKeyboardButton(text=_["btn_excel_report"], callback_data="admin:excel_report"),
        InlineKeyboardButton(text=_["btn_bot_status"],   callback_data="admin:status"),
    )
    return builder.as_markup()


def build_confirm_delete_keyboard(group_id: int, _: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=_["btn_confirm_delete"],
            callback_data=f"owner:delete_group:{group_id}",
        ),
        InlineKeyboardButton(text=_["btn_cancel"], callback_data="owner:cancel"),
    )
    return builder.as_markup()
