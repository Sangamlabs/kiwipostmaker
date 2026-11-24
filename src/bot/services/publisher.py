import logging
from typing import List, Tuple
from telegram import Bot, InputMediaPhoto, InputMediaVideo
from telegram.constants import ParseMode
from telegram.error import TelegramError

from ..models.post import Post
from ..keyboards.post_buttons import build_post_inline_keyboard, build_post_reply_keyboard
from ..utils.formatting import build_article_html, build_rich_message_payload, render_table_html

logger = logging.getLogger(__name__)

async def publish_post(bot: Bot, post: Post) -> Tuple[bool, List[int], str]:
    """
    Publishes a post (text, single media, or media group) to a Telegram channel.
    Matches Pages 2, 5, 6, 7 of DX-Notes:
    - Text only -> sendMessage
    - One photo/video -> sendPhoto / sendVideo with caption & reply_markup
    - 2-10 items -> sendMediaGroup, then attach keyboard to first message with editMessageReplyMarkup
    """
    if not post.channel_id:
        return False, [], "No destination channel selected."

    channel_id = post.channel_id
    text = post.text or ""
    media_items = post.media_list

    inline_keyboard = build_post_inline_keyboard(post.inline_buttons_list)
    keyboard = inline_keyboard
    has_keyboard = bool(keyboard and keyboard.inline_keyboard)
    row_buttons = post.row_buttons_list
    has_row_buttons = bool(row_buttons)

    try:
        # Mode 1: Article Post or Post with In-Body Row Buttons (Telegram Bot API 10.3 / 10.5 Rich Messages)
        if post.post_type == "article" or has_row_buttons:
            if not text and not post.table_data and not media_items and not has_row_buttons and not has_keyboard:
                return False, [], "Post cannot be empty (add text, table, buttons, or media)."

            rich_payload = build_rich_message_payload(
                text=text,
                table_data=post.table_data,
                media_list=media_items if media_items else None,
                in_body_buttons=row_buttons if has_row_buttons else None,
                media_position=getattr(post, "media_position", "top"),
            )
            payload = {
                "chat_id": channel_id,
                "rich_message": rich_payload,
            }
            if has_keyboard:
                payload["reply_markup"] = inline_keyboard.to_dict()

            try:
                res = await bot._post("sendRichMessage", data=payload)
                msg_id = res.get("message_id") if isinstance(res, dict) else getattr(res, "message_id", 0)
                return True, [msg_id], ""
            except Exception as rich_err:
                logger.error("sendRichMessage failed: %s", rich_err)
                return False, [], f"Publish failed: {rich_err}"

        # Mode 2: Standard Post with Optional Inline Buttons (Single Media, Albums, or Plain Text)
        # Case 1: Album (2 to 10 items)
        if len(media_items) >= 2:
            album_input = []
            for idx, item in enumerate(media_items[:10]):
                file_id = item.get("file_id")
                media_type = item.get("media_type", "photo")
                caption = text if idx == 0 else None

                if media_type == "video":
                    media_obj = InputMediaVideo(
                        media=file_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML if caption else None,
                    )
                else:
                    media_obj = InputMediaPhoto(
                        media=file_id,
                        caption=caption,
                        parse_mode=ParseMode.HTML if caption else None,
                    )
                album_input.append(media_obj)

            messages = await bot.send_media_group(
                chat_id=channel_id,
                media=album_input,
            )
            msg_ids = [msg.message_id for msg in messages]

            # Attach inline keyboard to the first message of the album
            if has_keyboard and msg_ids:
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=channel_id,
                        message_id=msg_ids[0],
                        reply_markup=keyboard,
                    )
                except Exception as k_err:
                    logger.warning("Could not attach keyboard to album message: %s", k_err)

            return True, msg_ids, ""

        # Case 2: Single photo, video, or sticker
        elif len(media_items) == 1:
            item = media_items[0]
            file_id = item.get("file_id")
            media_type = item.get("media_type", "photo")

            if media_type == "sticker":
                msg = await bot.send_sticker(
                    chat_id=channel_id,
                    sticker=file_id,
                    reply_markup=keyboard if has_keyboard else None,
                )
            elif media_type == "video":
                msg = await bot.send_video(
                    chat_id=channel_id,
                    video=file_id,
                    caption=text or None,
                    parse_mode=ParseMode.HTML if text else None,
                    reply_markup=keyboard if has_keyboard else None,
                )
            else:
                msg = await bot.send_photo(
                    chat_id=channel_id,
                    photo=file_id,
                    caption=text or None,
                    parse_mode=ParseMode.HTML if text else None,
                    reply_markup=keyboard if has_keyboard else None,
                )
            return True, [msg.message_id], ""

        # Case 3: Text and/or Rich Table only
        else:
            if not text and not post.table_data:
                return False, [], "Post cannot be empty (no text, no table, and no media)."

            # Use native Telegram Bot API 10.1 Rich Messages if a table is attached
            if post.table_data:
                payload = {
                    "chat_id": channel_id,
                    "rich_message": build_rich_message_payload(text, post.table_data),
                }
                if has_keyboard:
                    payload["reply_markup"] = keyboard.to_dict()

                try:
                    res = await bot._post("sendRichMessage", data=payload)
                    msg_id = res.get("message_id") if isinstance(res, dict) else getattr(res, "message_id", 0)
                    return True, [msg_id], ""
                except Exception as rich_err:
                    logger.warning("sendRichMessage error, falling back to standard message: %s", rich_err)
                    # Fallback to standard message if sendRichMessage fails
                    pass

            msg = await bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard if has_keyboard else None,
                disable_web_page_preview=False,
            )
            return True, [msg.message_id], ""

    except TelegramError as te:
        logger.error("Telegram publish error: %s", te)
        return False, [], te.message
    except Exception as exc:
        logger.exception("Unexpected error during post publishing: %s", exc)
        return False, [], str(exc)
