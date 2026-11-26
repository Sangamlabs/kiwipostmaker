import asyncio
import json
import logging
import re
from typing import Any, Dict, Tuple
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
        "• 📰 <b>Article Post:</b>\n"
        "Rich structured post with tables, media, quotes, and buttons inside your post.\n\n"
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
            f"✅ <b>Inline buttons saved!</b>\n\n"
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
            f"✅ <b>Row buttons saved!</b>\n\n"
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
            f"✅ <b>Table attached!</b>\n\n{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )

# In-memory debounce buffer for incoming media groups / rapid attachments
_MEDIA_BATCHES: Dict[Tuple[int, str], Dict[str, Any]] = {}
MEDIA_BATCH_DELAY = 0.8

async def _flush_media_batch(
    batch_key: Tuple[int, str],
    user_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Waits briefly for remaining album items, then saves all media at once and sends a single reply."""
    try:
        await asyncio.sleep(MEDIA_BATCH_DELAY)
        batch = _MEDIA_BATCHES.pop(batch_key, None)
        if not batch or not batch["items"]:
            return

        # Sort by Telegram message_id to preserve exact album order
        items = sorted(batch["items"], key=lambda x: x["message_id"])
        last_message = items[-1]["message"]
        post_repo: PostRepository = context.bot_data["post_repo"]

        pending_post_id = context.user_data.get("pending_post_id")
        if pending_post_id:
            draft = await post_repo.get_by_id(pending_post_id)
        else:
            draft = await post_repo.get_latest_draft(user_id)

        if not draft:
            draft = await post_repo.create_draft(user_id)

        media_items = list(draft.media_list)
        if len(media_items) >= 10:
            await last_message.reply_text("⚠️ Maximum 10 media items reached for this post.")
            return

        added_count = 0
        skipped_count = 0
        first_caption = ""
        for entry in items:
            if len(media_items) < 10:
                media_items.append(entry["media"])
                added_count += 1
            else:
                skipped_count += 1
            if entry["caption"] and not first_caption:
                first_caption = entry["caption"]

        update_kwargs: Dict[str, Any] = {"media_json": json.dumps(media_items)}
        if first_caption and not draft.text:
            update_kwargs["text"] = first_caption

        updated = await post_repo.update_post(draft.id, **update_kwargs)
        status_line = "✅ <b>Media attached!</b>"
        if skipped_count > 0:
            status_line += f" (Max 10 reached, {skipped_count} extra item(s) skipped)"

        await last_message.reply_text(
            f"{status_line}\n\n{get_editor_text(updated)}",
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(
                updated.id,
                bool(updated.media_list),
                bool(updated.channel_id),
                post_type=getattr(updated, "post_type", "standard"),
                media_position=getattr(updated, "media_position", "top"),
            ),
        )
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.error("MongoDB error attaching media batch: %s", exc)
        batch = _MEDIA_BATCHES.pop(batch_key, None)
        if batch and batch["items"]:
            await batch["items"][-1]["message"].reply_text(
                "⚠️ Could not save media: Database is currently unreachable."
            )

async def handle_incoming_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Captures photos, videos, or stickers and batches albums to prevent reply spam."""
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

    caption = extract_formatted_text(message)
    group_key = str(message.media_group_id) if message.media_group_id else f"single_{user.id}"
    batch_key = (user.id, group_key)

    batch = _MEDIA_BATCHES.get(batch_key)
    if batch is None:
        batch = {"items": [], "task": None}
        _MEDIA_BATCHES[batch_key] = batch

    batch["items"].append({
        "message_id": message.message_id,
        "media": {"file_id": file_id, "media_type": media_type},
        "caption": caption,
        "message": message,
    })

    if batch["task"] and not batch["task"].done():
        batch["task"].cancel()

    batch["task"] = asyncio.create_task(_flush_media_batch(batch_key, user.id, context))

def get_post_editor_handlers():
    return [
        MessageHandler(filters.Regex(r"^📝 CREATE POST$"), create_post_command),
        MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE, handle_user_text_input),
        MessageHandler((filters.PHOTO | filters.VIDEO | filters.Sticker.ALL) & filters.ChatType.PRIVATE, handle_incoming_media),
    ]
