from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from app.i18n import t


def get_main_menu(lang: str = "uz", role: str = "agent", webapp_url: str = "") -> ReplyKeyboardMarkup:
    # Standard agent menu: adding stores, checking own entries, and language
    keyboard = [
        [KeyboardButton(text=t("btn_new_store", lang))],
        [KeyboardButton(text=t("btn_my_records", lang))],
        [KeyboardButton(text=t("btn_lang", lang))],
    ]

    # Executive management: Only superadmin and admin have access to statistics and management
    if role in ("admin", "superadmin"):
        # Add btn_stats to row 2 alongside btn_my_records
        keyboard[1].append(KeyboardButton(text=t("btn_stats", lang)))
        if webapp_url and "example.com" not in webapp_url and webapp_url.startswith("https://"):
            keyboard.append([
                KeyboardButton(
                    text=t("btn_admin_panel", lang),
                    web_app=WebAppInfo(url=webapp_url),
                )
            ])

    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)


def get_language_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang:uz"),
                InlineKeyboardButton(text="🇺🇿 Ўзбекча", callback_data="set_lang:uz_cyr"),
            ],
            [
                InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang:ru"),
            ],
        ]
    )


def get_contact_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_share_contact", lang), request_contact=True)],
            [KeyboardButton(text=t("btn_cancel", lang))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_admin_approval_keyboard(user_id: int, lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_approve", lang),
                    callback_data=f"approve_agent:{user_id}",
                ),
                InlineKeyboardButton(
                    text=t("btn_reject", lang),
                    callback_data=f"reject_agent:{user_id}",
                ),
            ]
        ]
    )


def get_cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=t("btn_cancel", lang))]],
        resize_keyboard=True,
    )


def get_skip_cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_skip", lang))],
            [KeyboardButton(text=t("btn_cancel", lang))],
        ],
        resize_keyboard=True,
    )


def get_back_cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t("btn_back", lang)),
                KeyboardButton(text=t("btn_cancel", lang)),
            ]
        ],
        resize_keyboard=True,
    )


def get_skip_back_cancel_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_skip", lang))],
            [
                KeyboardButton(text=t("btn_back", lang)),
                KeyboardButton(text=t("btn_cancel", lang)),
            ],
        ],
        resize_keyboard=True,
    )


def get_location_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t("btn_send_location", lang), request_location=True)],
            [
                KeyboardButton(text=t("btn_back", lang)),
                KeyboardButton(text=t("btn_cancel", lang)),
            ],
        ],
        resize_keyboard=True,
    )


def get_photos_control_inline_keyboard(count: int, lang: str = "uz") -> InlineKeyboardMarkup:
    buttons = []
    if count < 3:
        buttons.append(
            InlineKeyboardButton(
                text=t("btn_add_more_photos", lang),
                callback_data="flow:more_photos",
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text=t("btn_continue", lang),
            callback_data="flow:photos_done",
        )
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            buttons,
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="flow:cancel")],
        ]
    )


def get_region_confirm_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_correct_region", lang), callback_data="region:correct"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_edit_mahalla", lang), callback_data="region:edit_mahalla"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_edit_all_region", lang), callback_data="region:edit_all"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_cancel", lang), callback_data="flow:cancel"
                )
            ],
        ]
    )


def get_duplicate_inn_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=t("btn_add_visit", lang), callback_data="dup_inn:add_visit"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_save_anyway", lang), callback_data="dup_inn:save_anyway"
                )
            ],
            [
                InlineKeyboardButton(
                    text=t("btn_cancel", lang), callback_data="flow:cancel"
                )
            ],
        ]
    )


def get_summary_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=t("btn_save", lang), callback_data="summary:save")],
            [InlineKeyboardButton(text=t("btn_edit", lang), callback_data="summary:edit")],
            [InlineKeyboardButton(text=t("btn_cancel", lang), callback_data="flow:cancel")],
        ]
    )
