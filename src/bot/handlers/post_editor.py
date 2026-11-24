import json
import logging
import re
from telegram import Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import ContextTypes, MessageHandler, filters

from ..database.repositories.posts import PostRepository
from ..keyboards.menus import get_post_editor_keyboard, get_post_format_selection_keyboard
from ..services.post_preview import render_post_preview
from ..utils.formatting import extract_formatted_text, parse_button_input, parse_keyboard_input, parse_table_input, sanitize_telegram_html
from .callbacks import get_editor_text, safe_edit_editor_message

logger = logging.getLogger(__name__)

async def create_post_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Prompts user to select between Standard Post and Article Post."""
    user = update.effective_user
    if not user:
        return

    await update.message.reply_text(
        "✨ <b>Choose Post Format:</b>\n\n"
        "• 📝 <b>Standard Post:</b>\n"
        "Standard Telegram post with single media, photo/video album (up to 10 files), text/caption, and styled buttons.\n\n"
        "• 📰 <b>Article Post (Telegram Bot API 10.5):</b>\n"
        "Rich structured document! Easily attach native tables, media, headings, and expandable quote blocks together in one seamless post.\n\n"
        "<i>Select a format to begin:</i>",
        parse_mode=ParseMode.HTML,
        reply_markup=get_post_format_selection_keyboard(),
    )

async def handle_user_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handles text input with full automatic Telegram entity format detection.
    Preserves bold, italic, underline, strikethrough, spoiler, links, and code automatically.
    """
    message = update.effective_message
    user = update.effective_user
    if not message or not user or not message.text:
        return

    raw_text = message.text.strip()
    # Ignore commands or main reply buttons
    if raw_text.startswith("/") or raw_text in {
        "📝 CREATE POST", "👤 PROFILE", "📢 MY CHANNELS", "⏰ SCHEDULES", "📖 HOW IT WORKS"
    }:
        return

    pending_action = context.user_data.get("pending_action")
    post_id = context.user_data.get("pending_post_id")
    if not pending_action or not post_id:
        return

    post_repo: PostRepository = context.bot_data["post_repo"]

    if pending_action == "set_text":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)

        # Automatically extract native Telegram formatting (bold, italic, links, spoilers, etc.)
        formatted_text = extract_formatted_text(message)

        updated = await post_repo.update_post(post_id, text=formatted_text)
        await message.reply_text(
            f"✅ <b>Text and formatting auto-detected and saved!</b>\n\n{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )

    elif pending_action in {"set_inline_buttons", "set_buttons"}:
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        parsed_buttons = parse_button_input(message.text)
        if not parsed_buttons:
            await message.reply_text(
                "⚠️ <b>No valid buttons recognized.</b>\n\n"
                "Expected format:\n"
                "<code>Button Text - https://link.com [primary/success/danger]</code>\n\n"
                "Tap <i>Add Buttons</i> in the editor to try again.",
                parse_mode=ParseMode.HTML,
            )
            return

        btns_json = json.dumps(parsed_buttons)
        updated = await post_repo.update_post(
            post_id,
            inline_buttons_json=btns_json,
            buttons_json=btns_json,
            button_type="inline",
        )
        await message.reply_text(
            f"✅ <b>{len(parsed_buttons)} Inline URL button(s) saved!</b>\n\n"
            f"💡 <i>Tip: You can also add In-Body Row Buttons or preview your post below.</i>\n\n"
            f"{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )

    elif pending_action == "set_row_buttons":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        parsed_buttons = parse_button_input(message.text)
        if not parsed_buttons:
            await message.reply_text(
                "⚠️ <b>No valid buttons recognized.</b>\n\n"
                "Expected format:\n"
                "<code>Button Text - https://link.com [primary/success/danger]</code>\n\n"
                "Tap <i>Add Buttons</i> in the editor to try again.",
                parse_mode=ParseMode.HTML,
            )
            return

        existing_post = await post_repo.get_by_id(post_id)
        btns_json = json.dumps(parsed_buttons)
        # If no inline buttons, keep buttons_json synced for backward compatibility
        b_json = btns_json if not getattr(existing_post, "inline_buttons_list", None) else existing_post.buttons_json

        updated = await post_repo.update_post(
            post_id,
            row_buttons_json=btns_json,
            buttons_json=b_json,
            button_type="row",
        )
        await message.reply_text(
            f"✅ <b>{len(parsed_buttons)} In-body row button(s) saved!</b>\n\n"
            f"💡 <i>Tip: You can also add Inline URL Buttons or preview your post below.</i>\n\n"
            f"{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )

    elif pending_action == "set_table":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        parsed_table = parse_table_input(message.text)
        if not parsed_table:
            await message.reply_text(
                "⚠️ <b>Could not parse table data.</b>\n\n"
                "Please separate columns with <code>|</code> pipe characters:\n\n"
                "<code>Col 1 | Col 2\nVal 1 | Val 2</code>\n\n"
                "Tap <i>Table -> Custom Table</i> to try again.",
                parse_mode=ParseMode.HTML,
            )
            return

        updated = await post_repo.update_post(post_id, table_json=json.dumps(parsed_table))
        await message.reply_text(
            f"✅ <b>Bot API 10.1 Native Table attached!</b>\n\n{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )

async def handle_incoming_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captures photos or videos with auto-detected formatted captions."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    file_id = None
    media_type = None

    if message.photo:
        file_id = message.photo[-1].file_id
        media_type = "photo"
    elif message.video:
        file_id = message.video.file_id
        media_type = "video"
    elif message.sticker:
        file_id = message.sticker.file_id
        media_type = "sticker"
    else:
        return

    # Automatically extract native Telegram formatted caption
    caption = extract_formatted_text(message)

    post_repo: PostRepository = context.bot_data["post_repo"]
    try:
        pending_post_id = context.user_data.get("pending_post_id")
        if pending_post_id:
            draft = await post_repo.get_by_id(pending_post_id)
        else:
            draft = await post_repo.get_latest_draft(user.id)

        if not draft:
            draft = await post_repo.create_draft(user.id)

        media_items = draft.media_list
        if len(media_items) >= 10:
            await message.reply_text("⚠️ Maximum 10 media items reached for this post.")
            return

        media_items.append({"file_id": file_id, "media_type": media_type})
        update_kwargs = {"media_json": json.dumps(media_items)}
        if caption and not draft.text:
            update_kwargs["text"] = caption

        updated = await post_repo.update_post(draft.id, **update_kwargs)
        await message.reply_text(
            f"✅ <b>Media attached!</b> ({len(media_items)} item(s) in draft #{updated.id})\n\n"
            f"{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )
    except Exception as exc:
        logger.error("MongoDB error attaching media: %s", exc)
        await message.reply_text("⚠️ Could not save media: Database is currently unreachable.")

def get_post_editor_handlers():
    return [
        MessageHandler(filters.Regex(r"^📝 CREATE POST$"), create_post_command),
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_user_text_input),
        MessageHandler((filters.PHOTO | filters.VIDEO | filters.Sticker.ALL) & filters.ChatType.PRIVATE, handle_incoming_media),
    ]
