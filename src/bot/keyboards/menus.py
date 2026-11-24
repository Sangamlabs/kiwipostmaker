from typing import List, Optional
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

def get_main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Main menu persistent reply keyboard."""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("📝 CREATE POST"), KeyboardButton("👤 PROFILE")],
            [KeyboardButton("📢 MY CHANNELS"), KeyboardButton("⏰ SCHEDULES")],
            [KeyboardButton("📖 HOW IT WORKS")],
        ],
        resize_keyboard=True,
    )

def get_post_format_selection_keyboard() -> InlineKeyboardMarkup:
    """Format selection: Standard Post vs Article Post (Bot API 10.1)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📝 Standard Post", callback_data="create_format_standard"),
            InlineKeyboardButton("📰 Article Post", callback_data="create_format_article"),
        ],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="nav_home")]
    ])

def get_buttons_management_keyboard(post_id: int, has_inline: bool = False, has_row: bool = False) -> InlineKeyboardMarkup:
    """Buttons manager: Allows setting/editing Inline buttons, In-Body Row buttons, or clearing them independently."""
    buttons = [
        [
            InlineKeyboardButton(f"{'✏️ ' if has_inline else '➕ '}🔘 Inline Buttons", callback_data=f"btn_inline_{post_id}"),
            InlineKeyboardButton(f"{'✏️ ' if has_row else '➕ '}📑 Row Buttons", callback_data=f"btn_row_{post_id}"),
        ],
    ]
    clear_row = []
    if has_inline:
        clear_row.append(InlineKeyboardButton("🗑 Clear Inline", callback_data=f"btn_clr_inline_{post_id}"))
    if has_row:
        clear_row.append(InlineKeyboardButton("🗑 Clear Row", callback_data=f"btn_clr_row_{post_id}"))
    if clear_row:
        buttons.append(clear_row)

    if has_inline and has_row:
        buttons.append([InlineKeyboardButton("🗑 Clear All Buttons", callback_data=f"btn_clr_all_{post_id}")])

    buttons.append([InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")])
    return InlineKeyboardMarkup(buttons)

def get_article_button_type_selection_keyboard(post_id: int) -> InlineKeyboardMarkup:
    """Legacy alias for backward compatibility."""
    return get_buttons_management_keyboard(post_id)

def get_media_position_keyboard(post_id: int, current_pos: str = "top") -> InlineKeyboardMarkup:
    """Article mode: Choose media placement (Top, Middle, Bottom)."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(f"{'✅ ' if current_pos == 'top' else ''}⬆️ Top (Above Text)", callback_data=f"set_mpos_{post_id}_top"),
            InlineKeyboardButton(f"{'✅ ' if current_pos == 'middle' else ''}↕️ Middle (Between Text)", callback_data=f"set_mpos_{post_id}_middle"),
        ],
        [
            InlineKeyboardButton(f"{'✅ ' if current_pos == 'bottom' else ''}⬇️ Bottom (Below Text)", callback_data=f"set_mpos_{post_id}_bottom"),
        ],
        [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")],
    ])

def get_post_editor_keyboard(
    post_id: int,
    has_media: bool = False,
    channel_selected: bool = False,
    post_type: str = "standard",
    media_position: str = "top",
) -> InlineKeyboardMarkup:
    """Editor inline dashboard matching Pages 3-5 of DX-Notes with Article mode support."""
    text_btn_title = "📰 Set Article" if post_type == "article" else "✏️ Set Text"
    preview_btn_title = "👀 Preview Article" if post_type == "article" else "👀 Preview"
    pos_icons = {"top": "⬆️ Top", "middle": "↕️ Middle", "bottom": "⬇️ Bottom"}
    pos_label = pos_icons.get(media_position, "⬆️ Top")

    buttons = [
        [
            InlineKeyboardButton(text_btn_title, callback_data=f"edit_text_{post_id}"),
            InlineKeyboardButton("🖼 Attach Media", callback_data=f"edit_media_{post_id}"),
        ],
        [
            InlineKeyboardButton("🔘 Add Buttons", callback_data=f"edit_btns_{post_id}"),
            InlineKeyboardButton("✨ Unicode Style", callback_data=f"edit_style_{post_id}"),
        ],
    ]

    if post_type == "article" and has_media:
        buttons.append([
            InlineKeyboardButton("📊 Table", callback_data=f"table_menu_{post_id}"),
            InlineKeyboardButton(f"📍 Media: {pos_label}", callback_data=f"choose_mpos_{post_id}"),
        ])
        buttons.append([
            InlineKeyboardButton("📢 Destination", callback_data=f"edit_channel_{post_id}"),
        ])
    else:
        buttons.append([
            InlineKeyboardButton("📊 Table", callback_data=f"table_menu_{post_id}"),
            InlineKeyboardButton("📢 Destination", callback_data=f"edit_channel_{post_id}"),
        ])

    buttons.extend([
        [
            InlineKeyboardButton(preview_btn_title, callback_data=f"preview_{post_id}"),
        ],
        [
            InlineKeyboardButton("🚀 Publish Now", callback_data=f"publish_now_{post_id}"),
            InlineKeyboardButton("⏰ Schedule", callback_data=f"schedule_{post_id}"),
        ],
        [
            InlineKeyboardButton("🗑 Clear Post", callback_data=f"clear_{post_id}"),
            InlineKeyboardButton("🔙 Main Menu", callback_data="nav_home"),
        ],
    ])
    return InlineKeyboardMarkup(buttons)
