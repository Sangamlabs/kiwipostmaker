import logging
from typing import Any, Dict
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from ..models.post import Post
from ..keyboards.post_buttons import build_post_inline_keyboard, build_post_reply_keyboard
from ..utils.formatting import build_article_html, build_rich_message_payload, render_table_html

logger = logging.getLogger(__name__)

async def render_post_preview(bot: Bot, chat_id: int, post: Post) -> None:
    """Send a live preview of the post to the editor's private chat with a Back to Editor button."""
    text = post.text or "<i>(No text provided)</i>"
    media_items = post.media_list

    row_buttons = post.row_buttons_list
    has_row_buttons = bool(row_buttons)

    # Build preview keyboard: user-defined inline buttons + "🔙 Back to Editor"
    preview_rows = []
    if post.inline_buttons_list:
        ik = build_post_inline_keyboard(post.inline_buttons_list)
        if ik and ik.inline_keyboard:
            for r in ik.inline_keyboard:
                preview_rows.append(r)
    preview_rows.append([
        InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post.id}")
    ])
    preview_keyboard = InlineKeyboardMarkup(preview_rows)

    # Article Mode Preview or Post with In-Body Row Buttons (Bot API 10.3 / 10.5 Rich Document)
    if post.post_type == "article" or has_row_buttons:
        article_header = "<b>👁 --- ARTICLE PREVIEW ---</b>\n\n" if post.post_type == "article" else "<b>👁 --- POST PREVIEW ---</b>\n\n"
        full_text = article_header + (post.text or "")

        rich_payload = build_rich_message_payload(
            text=full_text,
            table_data=post.table_data,
            media_list=media_items if media_items else None,
            in_body_buttons=row_buttons if has_row_buttons else None,
            media_position=getattr(post, "media_position", "top"),
        )
        payload = {
            "chat_id": chat_id,
            "rich_message": rich_payload,
            "reply_markup": preview_keyboard.to_dict(),
        }

        try:
            await bot._post("sendRichMessage", data=payload)
            return
        except Exception as e:
            logger.warning("sendRichMessage preview failed: %s", e)

    header = "👁‍🗨 <b>--- POST PREVIEW ---</b>\n\n"

    if not media_items:
        # Native Bot API 10.1 Rich Table Preview
        if post.table_data:
            payload = {
                "chat_id": chat_id,
                "rich_message": {
                    "blocks": [
                        {"type": "paragraph", "text": "👁‍🗨 <b>--- POST PREVIEW ---</b>"},
                        *build_rich_message_payload(post.text or "", post.table_data)["blocks"]
                    ]
                },
                "reply_markup": preview_keyboard.to_dict(),
            }

            try:
                await bot._post("sendRichMessage", data=payload)
                return
            except Exception as e:
                logger.warning("Failed to render rich table preview, falling back: %s", e)

        await bot.send_message(
            chat_id=chat_id,
            text=header + text,
            parse_mode=ParseMode.HTML,
            reply_markup=preview_keyboard,
        )
    elif len(media_items) == 1:
        item = media_items[0]
        file_id = item.get("file_id")
        media_type = item.get("media_type", "photo")
        caption = header + text

        if media_type == "sticker":
            await bot.send_message(
                chat_id=chat_id,
                text=header + (f"<i>Text:</i> {text}\n\n" if post.text else "") + "<i>[Sticker Preview]</i>",
                parse_mode=ParseMode.HTML,
            )
            await bot.send_sticker(
                chat_id=chat_id,
                sticker=file_id,
                reply_markup=preview_keyboard,
            )
        elif media_type == "video":
            await bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=preview_keyboard,
            )
        else:
            await bot.send_photo(
                chat_id=chat_id,
                photo=file_id,
                caption=caption,
                parse_mode=ParseMode.HTML,
                reply_markup=preview_keyboard,
            )
    else:
        # Album preview notice
        await bot.send_message(
            chat_id=chat_id,
            text=f"{header}<i>[Album with {len(media_items)} media files]</i>\n\n{text}",
            parse_mode=ParseMode.HTML,
            reply_markup=preview_keyboard,
        )
