MESSAGES: dict[str, dict[str, str]] = {
    "ru": {
        # --- Roles ---
        "role_owner":      "Владелец 👑",
        "role_superadmin": "Суперадмин 🛡",
        "role_admin":      "Администратор ⚙️",
        "role_guest":      "Гость 👁",
        # --- /start ---
        "start_msg": "Привет! Ваша роль: <b>{role_label}</b>\n\nИспользуйте /help для списка команд.",
        # --- /help ---
        "help_header":              "<b>Доступные команды:</b>",
        "help_stats_guest":         "/stats — ежедневная статистика",
        "help_stats":               "/stats — текущая статистика",
        "help_report":              "/report — Excel-отчёт",
        "help_list_groups":         "/list_groups — список групп",
        "help_list_users":          "/list_users — список пользователей",
        "help_broadcast":           "/broadcast &lt;текст&gt; — ручная рассылка",
        "help_add_guest":           "/add_guest &lt;id&gt; — добавить гостя",
        "help_add_admin":           "/add_admin &lt;id&gt; — добавить администратора",
        "help_remove_user_cmd":     "/remove_user &lt;id&gt; — деактивировать пользователя",
        "help_add_superadmin":      "/add_superadmin &lt;id&gt; — добавить суперадмина",
        "help_delete_group":        "/delete_group &lt;chat_id&gt; — удалить группу из БД",
        "help_status":              "/status — состояние GPU",
        "help_backup":              "/backup — создать резервную копию БД",
        "help_lang":                "/lang — сменить язык",
        # --- /status ---
        "broadcast_queue": "📬 Очередь рассылки: <b>{qsize}</b> задач",
        # --- add user ---
        "usage_add_user":         "Использование: {cmd} &lt;telegram_id или @username&gt;",
        "err_change_owner_role":  "❌ Нельзя изменить роль Владельца.",
        "err_already_has_role":   "ℹ️ Пользователь <code>{target_id}</code> уже имеет роль <b>{role_label}</b>.",
        "err_user_not_found_api": "❌ Пользователь <code>{arg}</code> не найден или недоступен боту.",
        "ok_user_assigned":       "✅ Пользователь <code>{target_id}</code> назначен как <b>{role_label}</b>.",
        # --- /remove_user ---
        "usage_remove_user":                  "Использование: /remove_user &lt;telegram_id&gt;",
        "err_user_not_found":                 "❌ Пользователь не найден.",
        "err_delete_owner":                   "❌ Нельзя удалить Владельца.",
        "err_superadmin_delete_restricted":   "❌ СуперАдмин не может удалить другого СуперАдмина или Владельца.",
        "ok_user_removed":                    "✅ Пользователь <code>{target_id}</code> удалён.",
        # --- /list_groups ---
        "no_groups":       "Групп не зарегистрировано.",
        "groups_header":   "<b>Группы ({count}):</b>\n",
        "groups_overflow": "\n... и ещё {n} групп. Скачайте Excel-отчёт /report.",
        # --- /delete_group ---
        "usage_delete_group":    "Использование: /delete_group &lt;chat_id&gt;",
        "err_group_not_found":   "❌ Группа не найдена в БД.",
        "confirm_delete_group":  (
            "⚠️ Вы собираетесь <b>удалить</b> группу:\n"
            "📛 {title}\n🆔 <code>{chat_id}</code>\n\nПодтвердите:"
        ),
        "ok_group_deleted": "🗑 Группа <code>{chat_id}</code> удалена из базы данных.",
        # --- /list_users ---
        "no_users":     "Нет пользователей в БД.",
        "users_header": "<b>Пользователи ({count}):</b>\n",
        # --- /broadcast ---
        "usage_broadcast":    "Использование: /broadcast &lt;текст сообщения&gt;",
        "ok_broadcast_queued": "📡 Рассылка поставлена в очередь.",
        # --- /stats / /report / /backup ---
        "ok_stats_sent":        "📊 Сводка отправлена в панель управления.",
        "ok_report_generating": "⏳ Генерирую Excel-отчёт...",
        "ok_backup_start":      "💾 Запускаю резервное копирование БД...",
        # --- callbacks ---
        "cb_cancelled":   "Отменено.",
        "cb_group_deleted_toast": "🗑 Группа удалена из БД.",
        "cb_owner_only":  "Только для Владельца.",
        # --- /lang ---
        "lang_select":  "Выберите язык / Tilni tanlang:",
        "lang_set_ru":  "✅ Язык изменён на <b>Русский</b>.",
        "lang_set_uz":  "✅ Til <b>O'zbekcha</b>ga o'zgartirildi.",
        # --- keyboard buttons ---
        "btn_list_groups":    "📋 Список групп",
        "btn_list_users":     "👥 Список пользователей",
        "btn_excel_report":   "📊 Отчёт Excel",
        "btn_bot_status":     "📡 Статус бота",
        "btn_approve":        "✅ Одобрить и отправить",
        "btn_reject":         "❌ Отклонить",
        "btn_confirm_delete": "🗑 Подтвердить удаление",
        "btn_cancel":         "Отмена",
        "cb_generating":      "Генерирую...",
        # --- control panel ---
        "cp_no_rights":         "⛔ Нет прав.",
        "cp_record_not_found":  "Запись не найдена.",
        "cp_already_processed": "Пост уже обработан: {status}",
        "cp_approved":          "✅ Пост одобрен и поставлен в очередь рассылки.",
        "cp_rejected":          "❌ Пост отклонён.",
    },
    "uz": {
        # --- Roles ---
        "role_owner":      "Egasi 👑",
        "role_superadmin": "Superadmin 🛡",
        "role_admin":      "Administrator ⚙️",
        "role_guest":      "Mehmon 👁",
        # --- /start ---
        "start_msg": "Salom! Sizning rolingiz: <b>{role_label}</b>\n\n/help — buyruqlar ro'yxati.",
        # --- /help ---
        "help_header":              "<b>Mavjud buyruqlar:</b>",
        "help_stats_guest":         "/stats — kunlik statistika",
        "help_stats":               "/stats — joriy statistika",
        "help_report":              "/report — Excel hisobot",
        "help_list_groups":         "/list_groups — guruhlar ro'yxati",
        "help_list_users":          "/list_users — foydalanuvchilar ro'yxati",
        "help_broadcast":           "/broadcast &lt;matn&gt; — qo'lda yuborish",
        "help_add_guest":           "/add_guest &lt;id&gt; — mehmon qo'shish",
        "help_add_admin":           "/add_admin &lt;id&gt; — administrator qo'shish",
        "help_remove_user_cmd":     "/remove_user &lt;id&gt; — foydalanuvchini o'chirish",
        "help_add_superadmin":      "/add_superadmin &lt;id&gt; — superadmin qo'shish",
        "help_delete_group":        "/delete_group &lt;chat_id&gt; — guruhni bazadan o'chirish",
        "help_status":              "/status — GPU holati",
        "help_backup":              "/backup — zaxira nusxa yaratish",
        "help_lang":                "/lang — tilni o'zgartirish",
        # --- /status ---
        "broadcast_queue": "📬 Yuborish navbati: <b>{qsize}</b> ta vazifa",
        # --- add user ---
        "usage_add_user":         "Foydalanish: {cmd} &lt;telegram_id yoki @username&gt;",
        "err_change_owner_role":  "❌ Egasining rolini o'zgartirib bo'lmaydi.",
        "err_already_has_role":   "ℹ️ Foydalanuvchi <code>{target_id}</code> allaqachon <b>{role_label}</b> roliga ega.",
        "err_user_not_found_api": "❌ Foydalanuvchi <code>{arg}</code> topilmadi yoki botga ko'rinmaydi.",
        "ok_user_assigned":       "✅ Foydalanuvchi <code>{target_id}</code> <b>{role_label}</b> sifatida tayinlandi.",
        # --- /remove_user ---
        "usage_remove_user":                "Foydalanish: /remove_user &lt;telegram_id&gt;",
        "err_user_not_found":               "❌ Foydalanuvchi topilmadi.",
        "err_delete_owner":                 "❌ Egani o'chirib bo'lmaydi.",
        "err_superadmin_delete_restricted": "❌ Superadmin boshqa superadmin yoki egani o'chira olmaydi.",
        "ok_user_removed":                  "✅ Foydalanuvchi <code>{target_id}</code> o'chirildi.",
        # --- /list_groups ---
        "no_groups":       "Guruhlar ro'yxatga olinmagan.",
        "groups_header":   "<b>Guruhlar ({count}):</b>\n",
        "groups_overflow": "\n... va yana {n} ta guruh. Excel hisobotni yuklab oling /report.",
        # --- /delete_group ---
        "usage_delete_group":   "Foydalanish: /delete_group &lt;chat_id&gt;",
        "err_group_not_found":  "❌ Guruh bazada topilmadi.",
        "confirm_delete_group": (
            "⚠️ Siz <b>o'chirmoqchi</b> bo'lgan guruh:\n"
            "📛 {title}\n🆔 <code>{chat_id}</code>\n\nTasdiqlang:"
        ),
        "ok_group_deleted": "🗑 Guruh <code>{chat_id}</code> bazadan o'chirildi.",
        # --- /list_users ---
        "no_users":     "Bazada foydalanuvchilar yo'q.",
        "users_header": "<b>Foydalanuvchilar ({count}):</b>\n",
        # --- /broadcast ---
        "usage_broadcast":     "Foydalanish: /broadcast &lt;xabar matni&gt;",
        "ok_broadcast_queued": "📡 Yuborish navbatga qo'shildi.",
        # --- /stats / /report / /backup ---
        "ok_stats_sent":        "📊 Xulosa boshqaruv paneliga yuborildi.",
        "ok_report_generating": "⏳ Excel hisobot yaratilmoqda...",
        "ok_backup_start":      "💾 Zaxira nusxa yaratish boshlandi...",
        # --- callbacks ---
        "cb_cancelled":         "Bekor qilindi.",
        "cb_group_deleted_toast": "🗑 Guruh bazadan o'chirildi.",
        "cb_owner_only":        "Faqat Egasi uchun.",
        # --- /lang ---
        "lang_select": "Выберите язык / Tilni tanlang:",
        "lang_set_ru": "✅ Язык изменён на <b>Русский</b>.",
        "lang_set_uz": "✅ Til <b>O'zbekcha</b>ga o'zgartirildi.",
        # --- keyboard buttons ---
        "btn_list_groups":    "📋 Guruhlar ro'yxati",
        "btn_list_users":     "👥 Foydalanuvchilar ro'yxati",
        "btn_excel_report":   "📊 Excel hisobot",
        "btn_bot_status":     "📡 Bot holati",
        "btn_approve":        "✅ Tasdiqlash va yuborish",
        "btn_reject":         "❌ Rad etish",
        "btn_confirm_delete": "🗑 O'chirishni tasdiqlash",
        "btn_cancel":         "Bekor qilish",
        "cb_generating":      "Yaratilmoqda...",
        # --- control panel ---
        "cp_no_rights":         "⛔ Huquq yo'q.",
        "cp_record_not_found":  "Yozuv topilmadi.",
        "cp_already_processed": "Post allaqachon qayta ishlangan: {status}",
        "cp_approved":          "✅ Post tasdiqlandi va navbatga qo'shildi.",
        "cp_rejected":          "❌ Post rad etildi.",
    },
}

DEFAULT_LANG = "ru"


def get_texts(lang_code: str) -> dict[str, str]:
    return MESSAGES.get(lang_code, MESSAGES[DEFAULT_LANG])
