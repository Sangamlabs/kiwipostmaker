import html
import json
import logging
import re
from datetime import datetime, timezone, timedelta
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.error import BadRequest
from telegram.ext import CallbackQueryHandler, ContextTypes

from ..database.repositories.posts import PostRepository
from ..database.repositories.channels import ChannelRepository
from ..keyboards.menus import (
    get_article_button_type_selection_keyboard,
    get_buttons_management_keyboard,
    get_media_position_keyboard,
    get_post_editor_keyboard,
)
from ..services.post_preview import render_post_preview
from ..services.publisher import publish_post
from ..services.channel_access import check_channel_permissions, verify_user_is_full_admin_or_owner
from ..utils.formatting import apply_unicode_style, render_text_table, sanitize_telegram_html, wrap_text_blockquote, remove_text_blockquote

logger = logging.getLogger(__name__)

def get_editor_text(post) -> str:
    """Helper to render standard post studio text."""
    body_text = sanitize_telegram_html(post.text) if post.text else "<i>(None)</i>"
    t_data = post.table_data
    if t_data:
        rows_cnt = len(t_data.get("rows", []))
        cols_cnt = len(t_data.get("headers", [])) or (len(t_data.get("rows", [[]])[0]) if rows_cnt > 0 else 0)
        table_summary = f"{cols_cnt} cols, {rows_cnt} rows"
    else:
        table_summary = "(None)"

    is_article = getattr(post, "post_type", "standard") == "article"
    title_prefix = "📰 <b>Article Post</b>" if is_article else "📝 <b>Standard Post</b>"
    inline_cnt = len(post.inline_buttons_list)
    row_cnt = len(post.row_buttons_list)
    if inline_cnt > 0 and row_cnt > 0:
        btn_summary = f"Inline: {inline_cnt} | Row: {row_cnt}"
    elif inline_cnt > 0:
        btn_summary = f"Inline: {inline_cnt}"
    elif row_cnt > 0:
        btn_summary = f"Row: {row_cnt}"
    else:
        btn_summary = "(None)"

    media_pos_line = ""
    if is_article and len(post.media_list) > 0:
        pos_icons = {"top": "⬆️ Top", "middle": "↕️ Middle", "bottom": "⬇️ Bottom"}
        cur_pos = getattr(post, "media_position", "top")
        media_pos_line = f"• <b>Position:</b> <code>{pos_icons.get(cur_pos, '⬆️ Top')}</code>\n"

    media_line = f"• <b>Media:</b> {len(post.media_list)}\n" if len(post.media_list) > 0 else "• <b>Media:</b> (None)\n"

    return (
        f"{title_prefix}\n\n"
        f"• <b>Text:</b>\n{body_text}\n\n"
        f"{media_line}"
        f"{media_pos_line}"
        f"• <b>Buttons:</b> <code>{btn_summary}</code>\n"
        f"• <b>Table:</b> <code>{table_summary}</code>\n"
        f"• <b>Channel:</b> <code>{post.channel_id or '(Not selected)'}</code>\n\n"
        f"<i>Use the actions below to build your post:</i>"
    )

async def safe_edit_editor_message(message, post):
    """Safely edit message with fallback if Telegram entity parsing fails."""
    text = get_editor_text(post)
    keyboard = get_post_editor_keyboard(
        post.id,
        bool(post.media_list),
        bool(post.channel_id),
        post_type=getattr(post, "post_type", "standard"),
        media_position=getattr(post, "media_position", "top"),
    )
    try:
        await message.edit_text(text=text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    except BadRequest as be:
        err_msg = str(be).lower()
        if "there is no text" in err_msg or "message can't be edited" in err_msg or "message to edit not found" in err_msg:
            await message.reply_text(text=text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        elif "message is not modified" in err_msg:
            pass
        elif "can't parse entities" in err_msg:
            logger.warning("Entity parsing issue in draft #%d, fallback to clean text: %s", post.id, be)
            clean_text = re.sub(r'</?(?!(?:b|i|u|s|tg-spoiler|a|code|pre|blockquote)\b)[^>]*>', '', post.text or '')
            is_article = getattr(post, "post_type", "standard") == "article"
            title_prefix = "📰 <b>Article Post</b>" if is_article else "📝 <b>Standard Post</b>"
            inline_cnt = len(post.inline_buttons_list)
            row_cnt = len(post.row_buttons_list)
            if inline_cnt > 0 and row_cnt > 0:
                btn_summary = f"Inline: {inline_cnt} | Row: {row_cnt}"
            elif inline_cnt > 0:
                btn_summary = f"Inline: {inline_cnt}"
            elif row_cnt > 0:
                btn_summary = f"Row: {row_cnt}"
            else:
                btn_summary = "(None)"

            media_line = f"• <b>Media:</b> {len(post.media_list)}\n" if len(post.media_list) > 0 else "• <b>Media:</b> (None)\n"

            fallback_text = (
                f"{title_prefix}\n\n"
                f"• <b>Text:</b>\n{clean_text if clean_text else '<i>(None)</i>'}\n\n"
                f"{media_line}"
                f"• <b>Buttons:</b> <code>{btn_summary}</code>\n"
                f"• <b>Channel:</b> <code>{post.channel_id or '(Not selected)'}</code>\n\n"
                f"<i>Use the actions below to build your post:</i>"
            )
            await message.edit_text(text=fallback_text, parse_mode=ParseMode.HTML, reply_markup=keyboard)
        else:
            raise

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    data = query.data
    user = query.from_user
    post_repo: PostRepository = context.bot_data["post_repo"]
    channel_repo: ChannelRepository = context.bot_data["channel_repo"]

    await query.answer()

    # 1. Main Menu Navigation
    if data == "nav_home":
        # Clear any pending action
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        await query.message.edit_text("🏠 <b>Main Menu</b>\n\nUse the reply keyboard buttons below.", parse_mode=ParseMode.HTML)
        return

    # 1b. Format Choice: Standard Post
    if data == "create_format_standard":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        draft = await post_repo.get_latest_draft(user.id, post_type="standard")
        if not draft:
            user_chans = await channel_repo.get_user_channels(user.id)
            def_chan = user_chans[0].channel_id if user_chans else None
            draft = await post_repo.create_draft(user.id, channel_id=def_chan, post_type="standard")
        elif not draft.channel_id:
            user_chans = await channel_repo.get_user_channels(user.id)
            if user_chans:
                draft = await post_repo.update_post(draft.id, channel_id=user_chans[0].channel_id)
        await safe_edit_editor_message(query.message, draft)
        return

    # 1c. Format Choice: Article Post (Bot API 10.1)
    if data == "create_format_article":
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        draft = await post_repo.get_latest_draft(user.id, post_type="article")
        if not draft:
            user_chans = await channel_repo.get_user_channels(user.id)
            def_chan = user_chans[0].channel_id if user_chans else None
            draft = await post_repo.create_draft(user.id, channel_id=def_chan, post_type="article")
        elif not draft.channel_id:
            user_chans = await channel_repo.get_user_channels(user.id)
            if user_chans:
                draft = await post_repo.update_post(draft.id, channel_id=user_chans[0].channel_id)
        await safe_edit_editor_message(query.message, draft)
        return

    # 2. Re-open / refresh editor
    if data.startswith("open_editor_"):
        post_id = int(data.replace("open_editor_", ""))
        context.user_data.pop("pending_action", None)
        context.user_data.pop("pending_post_id", None)
        post = await post_repo.get_by_id(post_id)
        if not post:
            await query.answer("Draft not found.", show_alert=True)
            return
        await safe_edit_editor_message(query.message, post)
        return

    # 3. Set Text Action (Prompt user to send text)
    if data.startswith("edit_text_"):
        post_id = int(data.replace("edit_text_", ""))
        context.user_data["pending_action"] = "set_text"
        context.user_data["pending_post_id"] = post_id
        post = await post_repo.get_by_id(post_id)
        is_article = getattr(post, "post_type", "standard") == "article"
        await query.message.edit_text(
            f"✏️ <b>Send Your {'Article' if is_article else 'Post'} Text (Draft #{post_id})</b>\n\n"
            f"Send your text message below.\n\n"
            f"✨ <b>No HTML Knowledge Needed!</b>\n"
            f"You can simply format your text directly using Telegram's built-in options (select text in Telegram):\n"
            f"• <b>Bold</b> (𝐁), <i>Italic</i> (𝘐), <u>Underline</u>, <s>Strikethrough</s>\n"
            f"• <tg-spoiler>Spoiler</tg-spoiler>, Add Link (URL), <code>Monospace / Code</code>\n"
            f"• 💬 <b>Quote / Blockquote</b>\n"
            f"• 🔽 <b>Expandable Quote (Collapse)</b> (Bot API 10.5)\n\n"
            f"💡 <i>Or use HTML tags:</i> <code>&lt;blockquote&gt;...&lt;/blockquote&gt;</code> or <code>&lt;blockquote expandable&gt;...&lt;/blockquote&gt;</code>\n"
            f"🤖 <b>Auto-Detection:</b> Kiwi post Maker automatically detects all your formatting and saves it into your draft!\n\n"
            f"<i>Type or paste your formatted text below and send it, or tap Cancel:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"open_editor_{post_id}")]
            ]),
        )
        return

    # 4. Attach Media Action (Instructions)
    if data.startswith("edit_media_"):
        post_id = int(data.replace("edit_media_", ""))
        context.user_data["pending_action"] = "set_media"
        context.user_data["pending_post_id"] = post_id
        await query.message.edit_text(
            f"🖼 <b>Attach Photos or Videos (Draft #{post_id})</b>\n\n"
            f"Simply send any photo or video into this chat right now!\n\n"
            f"• A single photo or video will be posted with caption.\n"
            f"• Sending 2 to 10 photos/videos automatically creates an <b>album</b>.\n"
            f"• You can also add caption directly when uploading.\n\n"
            f"<i>Send your media file now, or tap Back:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")]
            ]),
        )
        return

    # 5. Add / Manage Buttons Action
    if data.startswith("edit_btns_"):
        post_id = int(data.replace("edit_btns_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post:
            return

        has_inline = bool(post.inline_buttons_list)
        has_row = bool(post.row_buttons_list)
        inline_cnt = len(post.inline_buttons_list)
        row_cnt = len(post.row_buttons_list)

        await query.message.edit_text(
            f"🔘 <b>Manage Post Buttons (Draft #{post_id})</b>\n\n"
            f"You can add <b>Inline Buttons</b>, <b>In-Body Row Buttons</b>, or <b>BOTH</b>!\n\n"
            f"• <b>🔘 Inline Buttons:</b>\n"
            f"Interactive link buttons attached directly below your post container.\n\n"
            f"• <b>📑 In-Body Row Buttons (Bot API 10.3):</b>\n"
            f"Native colored row buttons embedded inside the post content.\n\n"
            f"<b>Current Configuration:</b>\n"
            f"• 🔘 Inline Buttons: <code>{inline_cnt} configured</code>\n"
            f"• 📑 Row Buttons: <code>{row_cnt} configured</code>\n\n"
            f"<i>Tap an option below to set or clear buttons:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_buttons_management_keyboard(post_id, has_inline=has_inline, has_row=has_row),
        )
        return

    # 5a. Action: Prompt Inline Buttons
    if data.startswith("btn_inline_"):
        post_id = int(data.replace("btn_inline_", ""))
        context.user_data["pending_action"] = "set_inline_buttons"
        context.user_data["pending_post_id"] = post_id
        await query.message.edit_text(
            f"🔘 <b>Add / Update Inline URL Buttons (Draft #{post_id})</b>\n\n"
            f"Send each button in this format:\n"
            f"<code>Button Text - https://link.com [style]</code>\n\n"
            f"<b>Supported Styles:</b> <code>primary</code> (blue), <code>success</code> (green), <code>danger</code> (red)\n\n"
            f"<b>Examples:</b>\n"
            f"<code>Main Channel - https://t.me/example primary</code>\n"
            f"<code>Website - https://example.com | Support - https://t.me/help success</code>\n"
            f"<i>(Use <code>|</code> to put multiple buttons on the same row)</i>\n\n"
            f"<i>Send your inline buttons now, or tap Cancel:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"edit_btns_{post_id}")]
            ]),
        )
        return

    # 5b. Action: Prompt In-Body Row Buttons (Bot API 10.3)
    if data.startswith("btn_row_"):
        post_id = int(data.replace("btn_row_", ""))
        context.user_data["pending_action"] = "set_row_buttons"
        context.user_data["pending_post_id"] = post_id
        await query.message.edit_text(
            f"📑 <b>Add / Update In-Body Row Buttons (Draft #{post_id} - Bot API 10.3)</b>\n\n"
            f"Native buttons placed right inside your post content!\n\n"
            f"Send each button in this format:\n"
            f"<code>Button Text - https://link.com [style]</code>\n\n"
            f"<b>Supported Styles:</b> <code>primary</code> (blue), <code>success</code> (green), <code>danger</code> (red)\n\n"
            f"<b>Examples:</b>\n"
            f"<code>DEV CHANNEL - https://t.me/dev success | MAIN GROUP - https://t.me/group danger</code>\n"
            f"<i>(Use <code>|</code> to put multiple buttons on the same row)</i>\n\n"
            f"<i>Send your row buttons now, or tap Cancel:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"edit_btns_{post_id}")]
            ]),
        )
        return

    # 5c. Action: Clear Inline Buttons
    if data.startswith("btn_clr_inline_"):
        post_id = int(data.replace("btn_clr_inline_", ""))
        post = await post_repo.get_by_id(post_id)
        if post:
            b_json = "[]" if not post.row_buttons_list else post.buttons_json
            await post_repo.update_post(post_id, inline_buttons_json="[]", buttons_json=b_json)
            await query.answer("Cleared inline buttons!", show_alert=True)
            updated = await post_repo.get_by_id(post_id)
            has_inline = bool(updated.inline_buttons_list)
            has_row = bool(updated.row_buttons_list)
            await query.message.edit_text(
                f"🔘 <b>Manage Post Buttons (Draft #{post_id})</b>\n\n"
                f"• 🔘 Inline Buttons: <code>0 configured</code>\n"
                f"• 📑 Row Buttons: <code>{len(updated.row_buttons_list)} configured</code>\n\n"
                f"<i>Tap an option below to set or clear buttons:</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=get_buttons_management_keyboard(post_id, has_inline=has_inline, has_row=has_row),
            )
        return

    # 5d. Action: Clear Row Buttons
    if data.startswith("btn_clr_row_"):
        post_id = int(data.replace("btn_clr_row_", ""))
        post = await post_repo.get_by_id(post_id)
        if post:
            await post_repo.update_post(post_id, row_buttons_json="[]")
            await query.answer("Cleared row buttons!", show_alert=True)
            updated = await post_repo.get_by_id(post_id)
            has_inline = bool(updated.inline_buttons_list)
            has_row = bool(updated.row_buttons_list)
            await query.message.edit_text(
                f"🔘 <b>Manage Post Buttons (Draft #{post_id})</b>\n\n"
                f"• 🔘 Inline Buttons: <code>{len(updated.inline_buttons_list)} configured</code>\n"
                f"• 📑 Row Buttons: <code>0 configured</code>\n\n"
                f"<i>Tap an option below to set or clear buttons:</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=get_buttons_management_keyboard(post_id, has_inline=has_inline, has_row=has_row),
            )
        return

    # 5e. Action: Clear All Buttons
    if data.startswith("btn_clr_all_"):
        post_id = int(data.replace("btn_clr_all_", ""))
        post = await post_repo.get_by_id(post_id)
        if post:
            await post_repo.update_post(post_id, inline_buttons_json="[]", row_buttons_json="[]", buttons_json="[]")
            await query.answer("Cleared all buttons!", show_alert=True)
            updated = await post_repo.get_by_id(post_id)
            await query.message.edit_text(
                f"🔘 <b>Manage Post Buttons (Draft #{post_id})</b>\n\n"
                f"• 🔘 Inline Buttons: <code>0 configured</code>\n"
                f"• 📑 Row Buttons: <code>0 configured</code>\n\n"
                f"<i>Tap an option below to set or clear buttons:</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=get_buttons_management_keyboard(post_id, has_inline=False, has_row=False),
            )
        return

    # 5c. Action: Choose Media Position Menu
    if data.startswith("choose_mpos_"):
        post_id = int(data.replace("choose_mpos_", ""))
        post = await post_repo.get_by_id(post_id)
        cur_pos = getattr(post, "media_position", "top") if post else "top"
        await query.message.edit_text(
            f"📍 <b>Choose Media Position (Draft #{post_id})</b>\n\n"
            f"Select where your media (photo/video/gif) should be placed in the article:\n\n"
            f"• <b>⬆️ Top:</b> Placed right above the article text.\n"
            f"• <b>↕️ Middle:</b> Interleaved inside the article text (between paragraphs).\n"
            f"• <b>⬇️ Bottom:</b> Placed below the article text.\n\n"
            f"<i>Tip: You can also write <code>{{media}}</code> anywhere in your article text to position it at that exact spot!</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_media_position_keyboard(post_id, cur_pos),
        )
        return

    # 5d. Action: Set Media Position
    if data.startswith("set_mpos_"):
        parts = data.split("_")
        # format: set_mpos_{post_id}_{position}
        post_id = int(parts[2])
        position = parts[3]
        if position in {"top", "middle", "bottom"}:
            updated = await post_repo.update_post(post_id, media_position=position)
            await query.answer(f"📍 Media position set to {position.capitalize()}!", show_alert=False)
            await safe_edit_editor_message(query.message, updated)
        return

    # 6. Unicode Style Menu
    if data.startswith("edit_style_"):
        post_id = int(data.replace("edit_style_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post or not post.text:
            await query.answer("Please set post text first before styling.", show_alert=True)
            return

        await query.message.edit_text(
            f"✨ <b>Select Font & Quote Style (Draft #{post_id})</b>\n\n"
            f"Choose a style to transform alphanumeric text or wrap in quotes:\n\n"
            f"• <b>Unicode Fonts:</b> Bold, Italic, Mono, Small Caps\n"
            f"• <b>Quote Blocks (Bot API 10.5):</b> Standard Quote & Expandable Quote\n",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("𝐁 Bold", callback_data=f"applystyle_{post_id}_bold"),
                    InlineKeyboardButton("𝘐 Italic", callback_data=f"applystyle_{post_id}_italic"),
                    InlineKeyboardButton("𝙼 Mono", callback_data=f"applystyle_{post_id}_mono"),
                ],
                [
                    InlineKeyboardButton("ꜱᴍᴀʟʟ ᴄᴀᴘꜱ", callback_data=f"applystyle_{post_id}_smallcaps"),
                ],
                [
                    InlineKeyboardButton("💬 Standard Quote", callback_data=f"applystyle_{post_id}_quote"),
                    InlineKeyboardButton("🔽 Expandable Quote", callback_data=f"applystyle_{post_id}_expandable"),
                ],
                [
                    InlineKeyboardButton("🔄 Remove Quote", callback_data=f"applystyle_{post_id}_removequote"),
                ],
                [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")],
            ]),
        )
        return

    # 6b. Apply Unicode & Quote Style
    if data.startswith("applystyle_"):
        tokens = data.split("_")
        post_id = int(tokens[1])
        style_choice = tokens[2]
        post = await post_repo.get_by_id(post_id)
        if post and post.text:
            if style_choice == "quote":
                styled = wrap_text_blockquote(post.text, expandable=False)
                alert_text = "💬 Wrapped post text in Standard Blockquote!"
            elif style_choice == "expandable":
                styled = wrap_text_blockquote(post.text, expandable=True)
                alert_text = "🔽 Wrapped post text in Expandable Blockquote (Bot API 10.5)!"
            elif style_choice == "removequote":
                styled = remove_text_blockquote(post.text)
                alert_text = "🔄 Removed blockquote wrapper from text!"
            else:
                styled = apply_unicode_style(post.text, style=style_choice)
                alert_text = f"Applied Unicode {style_choice}!"

            await post_repo.update_post(post.id, text=styled)
            await query.answer(alert_text, show_alert=True)
            updated = await post_repo.get_by_id(post_id)
            await safe_edit_editor_message(query.message, updated)
        return

    # 7. Bot API 10.1 Native Table Menu
    if data.startswith("table_menu_"):
        post_id = int(data.replace("table_menu_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post:
            return

        t_data = post.table_data
        has_table = bool(t_data)
        if has_table:
            headers = t_data.get("headers", [])
            rows = t_data.get("rows", [])
            is_bordered = t_data.get("is_bordered", True)
            is_striped = t_data.get("is_striped", True)
            align = t_data.get("align", "left")

            hdr_text = ", ".join(headers) if headers else "(None)"
            status_desc = (
                f"✅ <b>Status: Attached (Telegram Bot API 10.1)</b>\n\n"
                f"• <b>Headers:</b> <code>{hdr_text}</code>\n"
                f"• <b>Data Rows:</b> {len(rows)}\n"
                f"• <b>Borders:</b> {'✅ Enabled' if is_bordered else '❌ Disabled'}\n"
                f"• <b>Striping:</b> {'✅ Enabled' if is_striped else '❌ Disabled'}\n"
                f"• <b>Alignment:</b> <code>{align.title()}</code>"
            )
        else:
            status_desc = (
                "ℹ️ <i>No native table currently attached.</i>\n\n"
                "Telegram Bot API 10.1 Markup Revolution enables native, interactive tables with "
                "custom alignment, borders, and striped rows."
            )

        menu_buttons = [
            [
                InlineKeyboardButton("✏️ Custom Table", callback_data=f"table_input_{post_id}"),
                InlineKeyboardButton("⚡ Insert Sample", callback_data=f"table_sample_{post_id}"),
            ],
        ]
        if has_table:
            menu_buttons.append([
                InlineKeyboardButton(
                    f"🔲 Borders: {'ON' if t_data.get('is_bordered', True) else 'OFF'}",
                    callback_data=f"table_tog_border_{post_id}",
                ),
                InlineKeyboardButton(
                    f"🎨 Striped: {'ON' if t_data.get('is_striped', True) else 'OFF'}",
                    callback_data=f"table_tog_stripe_{post_id}",
                ),
            ])
            menu_buttons.append([
                InlineKeyboardButton(
                    f"↔️ Align: {t_data.get('align', 'left').title()}",
                    callback_data=f"table_tog_align_{post_id}",
                ),
                InlineKeyboardButton("🗑 Remove Table", callback_data=f"table_remove_{post_id}"),
            ])

        menu_buttons.append([
            InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")
        ])

        await query.message.edit_text(
            f"📊 <b>Bot API 10.1 Native Table Studio (Draft #{post_id})</b>\n\n"
            f"{status_desc}\n\n"
            f"<i>Select an option below:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(menu_buttons),
        )
        return

    # 7b. Action: Prompt Custom Table Input
    if data.startswith("table_input_"):
        post_id = int(data.replace("table_input_", ""))
        context.user_data["pending_action"] = "set_table"
        context.user_data["pending_post_id"] = post_id
        await query.message.edit_text(
            f"📊 <b>Create Native Bot API 10.1 Table (Draft #{post_id})</b>\n\n"
            f"Send your table rows separated by <code>|</code> pipe symbols:\n\n"
            f"<b>Example:</b>\n"
            f"<code>Item | Price | Status\n"
            f"Product A | 10 USD | Active\n"
            f"Product B | 25 USD | Ready\n"
            f"Product C | 40 USD | Sold Out</code>\n\n"
            f"<i>(The first row will be formatted as header cells)</i>\n\n"
            f"<i>Send your table message now, or tap Cancel:</i>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"table_menu_{post_id}")]
            ]),
        )
        return

    # 7c. Action: Insert Sample Table
    if data.startswith("table_sample_"):
        post_id = int(data.replace("table_sample_", ""))
        sample_data = {
            "headers": ["Item", "Price", "Status"],
            "rows": [
                ["Product A", "10 USD", "Active"],
                ["Product B", "25 USD", "Ready"],
                ["Product C", "40 USD", "Sold Out"]
            ],
            "is_bordered": True,
            "is_striped": True,
            "align": "center",
        }
        await post_repo.update_post(post_id, table_json=json.dumps(sample_data))
        await query.answer("⚡ Bot API 10.1 Native Table added!", show_alert=True)
        # Refresh table menu to show new status and toggles
        updated = await post_repo.get_by_id(post_id)
        # Simulate table menu refresh
        query.data = f"table_menu_{post_id}"
        await handle_callback_query(update, context)
        return

    # 7d. Action: Toggle Table Borders
    if data.startswith("table_tog_border_"):
        post_id = int(data.replace("table_tog_border_", ""))
        post = await post_repo.get_by_id(post_id)
        if post and post.table_data:
            t_data = post.table_data
            t_data["is_bordered"] = not t_data.get("is_bordered", True)
            await post_repo.update_post(post_id, table_json=json.dumps(t_data))
            await query.answer(f"Borders: {'ON' if t_data['is_bordered'] else 'OFF'}")
            query.data = f"table_menu_{post_id}"
            await handle_callback_query(update, context)
        return

    # 7e. Action: Toggle Table Striping
    if data.startswith("table_tog_stripe_"):
        post_id = int(data.replace("table_tog_stripe_", ""))
        post = await post_repo.get_by_id(post_id)
        if post and post.table_data:
            t_data = post.table_data
            t_data["is_striped"] = not t_data.get("is_striped", True)
            await post_repo.update_post(post_id, table_json=json.dumps(t_data))
            await query.answer(f"Striping: {'ON' if t_data['is_striped'] else 'OFF'}")
            query.data = f"table_menu_{post_id}"
            await handle_callback_query(update, context)
        return

    # 7f. Action: Cycle Table Alignment (left -> center -> right -> left)
    if data.startswith("table_tog_align_"):
        post_id = int(data.replace("table_tog_align_", ""))
        post = await post_repo.get_by_id(post_id)
        if post and post.table_data:
            t_data = post.table_data
            cur_align = t_data.get("align", "left")
            next_align = {"left": "center", "center": "right", "right": "left"}.get(cur_align, "left")
            t_data["align"] = next_align
            await post_repo.update_post(post_id, table_json=json.dumps(t_data))
            await query.answer(f"Alignment: {next_align.title()}")
            query.data = f"table_menu_{post_id}"
            await handle_callback_query(update, context)
        return

    # 7g. Action: Remove Table
    if data.startswith("table_remove_"):
        post_id = int(data.replace("table_remove_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post:
            return

        # Clear table_json and any legacy pre tag in text
        cleaned_text = re.sub(r'<pre>.*?</pre>', '', post.text or '', flags=re.DOTALL).strip()
        await post_repo.update_post(post.id, table_json=None, text=cleaned_text)
        await query.answer("🗑 Table removed from post!", show_alert=True)
        updated = await post_repo.get_by_id(post_id)
        await safe_edit_editor_message(query.message, updated)
        return

    # 8. Destination Channel Picker
    if data.startswith("edit_channel_"):
        post_id = int(data.replace("edit_channel_", ""))
        channels = await channel_repo.get_user_channels(user.id)
        if not channels:
            await query.message.edit_text(
                "📢 <b>No Connected Channels Found</b>\n\n"
                "To connect a channel:\n"
                "1. Add this bot as an <b>Admin</b> in your channel with <i>Post Messages</i> permission.\n"
                "2. Send <code>/connect @your_channel</code> or forward a post from that channel here.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")]
                ]),
            )
            return

        buttons = [
            [InlineKeyboardButton(f"📢 {ch.title} (@{ch.username or 'Private'})", callback_data=f"setchan_{post_id}_{ch.channel_id}")]
            for ch in channels
        ]
        buttons.append([InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")])
        await query.message.edit_text(
            "📢 <b>Select Destination Channel:</b>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons),
        )
        return

    # 8b. Set Chosen Channel
    if data.startswith("setchan_"):
        tokens = data.split("_", 2)
        post_id = int(tokens[1])
        channel_id = tokens[2]
        await post_repo.update_post(post_id, channel_id=channel_id)
        await query.answer("Channel selected!")
        updated = await post_repo.get_by_id(post_id)
        await safe_edit_editor_message(query.message, updated)
        return

    # 9. Live Preview
    if data.startswith("preview_"):
        post_id = int(data.replace("preview_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post:
            return
        await render_post_preview(context.bot, user.id, post)
        await query.answer("Preview sent above! ⬆️")
        return

    # 10. Publish Now
    if data.startswith("publish_now_"):
        post_id = int(data.replace("publish_now_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post:
            await query.answer("Post not found.", show_alert=True)
            return

        if not post.channel_id:
            await query.answer("⚠️ Please select a Destination channel first via 'Destination' button.", show_alert=True)
            return

        if not post.text and not post.media_list:
            await query.answer("⚠️ Cannot publish an empty post! Please Set Text or Attach Media first.", show_alert=True)
            return

        perm_ok, perm_err = await check_channel_permissions(context.bot, post.channel_id)
        if not perm_ok:
            await query.message.edit_text(
                f"❌ <b>Channel Permission Error:</b>\n\n{perm_err}\n\n"
                "Please verify the bot is an Administrator with 'Post Messages' permission in that channel.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Retry", callback_data=f"publish_now_{post.id}")],
                    [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post.id}")],
                ]),
            )
            return

        claimed = await post_repo.claim_post_for_publishing(post.id)
        if not claimed:
            await query.answer("Post is already being published.", show_alert=True)
            return

        success, msg_ids, error_msg = await publish_post(context.bot, post)
        if success:
            await post_repo.mark_published(post.id, msg_ids)
            await query.message.edit_text(
                f"🎉 <b>Post Published Successfully!</b>\n\n"
                f"• <b>Destination:</b> <code>{post.channel_id}</code>\n"
                f"• <b>Message IDs:</b> <code>{msg_ids}</code>\n\n"
                f"<i>Draft saved as published in database.</i>",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("➕ Start New Post", callback_data="start_new_post")],
                    [InlineKeyboardButton("🏠 Main Menu", callback_data="nav_home")],
                ]),
            )
        else:
            await post_repo.mark_failed(post.id, error_msg)
            await query.message.edit_text(
                f"❌ <b>Publishing Failed:</b>\n{error_msg}\n\nDraft retained for retry.",
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Retry", callback_data=f"publish_now_{post.id}")],
                    [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post.id}")],
                ]),
            )
        return

    # 11. Schedule Menu
    if data.startswith("schedule_"):
        post_id = int(data.replace("schedule_", ""))
        post = await post_repo.get_by_id(post_id)
        if not post:
            return

        if not post.channel_id:
            await query.answer("⚠️ Please select a Destination channel before scheduling.", show_alert=True)
            return

        if not post.text and not post.media_list:
            await query.answer("⚠️ Cannot schedule an empty post.", show_alert=True)
            return

        await query.message.edit_text(
            f"⏰ <b>Schedule Post (Draft #{post_id})</b>\n\n"
            f"Destination: <code>{post.channel_id}</code>\n\n"
            f"Choose when this post should be automatically published:\n",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("⏱ In 10 Minutes", callback_data=f"setsched_{post_id}_10m"),
                    InlineKeyboardButton("⏱ In 30 Minutes", callback_data=f"setsched_{post_id}_30m"),
                ],
                [
                    InlineKeyboardButton("⏱ In 1 Hour", callback_data=f"setsched_{post_id}_1h"),
                    InlineKeyboardButton("⏱ In 6 Hours", callback_data=f"setsched_{post_id}_6h"),
                ],
                [
                    InlineKeyboardButton("⏱ Tomorrow (+24h)", callback_data=f"setsched_{post_id}_24h"),
                ],
                [InlineKeyboardButton("🔙 Back to Editor", callback_data=f"open_editor_{post_id}")],
            ]),
        )
        return

    # 11b. Apply Schedule Selection
    if data.startswith("setsched_"):
        tokens = data.split("_")
        post_id = int(tokens[1])
        sched_type = tokens[2]

        now = datetime.now(timezone.utc)
        if sched_type == "10m":
            target_time = now + timedelta(minutes=10)
        elif sched_type == "30m":
            target_time = now + timedelta(minutes=30)
        elif sched_type == "1h":
            target_time = now + timedelta(hours=1)
        elif sched_type == "6h":
            target_time = now + timedelta(hours=6)
        else:
            target_time = now + timedelta(hours=24)

        time_iso = target_time.isoformat()
        time_display = target_time.strftime("%Y-%m-%d %H:%M UTC")

        await post_repo.update_post(post_id, scheduled_at=time_iso, status="queued")
        await query.answer("Post scheduled successfully!", show_alert=True)
        await query.message.edit_text(
            f"⏰ <b>Post Scheduled!</b>\n\n"
            f"• <b>Draft:</b> #{post_id}\n"
            f"• <b>Publish Time:</b> <code>{time_display}</code>\n\n"
            f"Kiwi post Maker will automatically publish this post to your channel at the scheduled time.",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 Main Menu", callback_data="nav_home")],
            ]),
        )
        return

    # 12. Clear Post
    if data.startswith("clear_"):
        post_id = int(data.replace("clear_", ""))
        await query.message.edit_text(
            f"⚠️ <b>Confirm Clear Draft</b>\n\n"
            f"Are you sure you want to permanently delete Draft #{post_id}?",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🗑 Yes, Delete", callback_data=f"confirm_clear_{post_id}"),
                    InlineKeyboardButton("❌ Cancel", callback_data=f"open_editor_{post_id}"),
                ]
            ]),
        )
        return

    if data.startswith("confirm_clear_"):
        post_id = int(data.replace("confirm_clear_", ""))
        await post_repo.delete_post(post_id, user.id)
        await query.message.edit_text("🗑 <b>Draft deleted.</b>", parse_mode=ParseMode.HTML)
        return

    if data == "start_new_post":
        user_chans = await channel_repo.get_user_channels(user.id)
        def_chan = user_chans[0].channel_id if user_chans else None
        new_draft = await post_repo.create_draft(user.id, channel_id=def_chan)
        await query.message.edit_text(
            text=get_editor_text(new_draft),
            parse_mode=ParseMode.HTML,
            reply_markup=get_post_editor_keyboard(new_draft.id, False, bool(def_chan)),
        )
        return

    # 13. Owner Invite Button from MY CHANNELS
    if data.startswith("invite_chan_"):
        chan_id = data.replace("invite_chan_", "")
        auth_ok, auth_err, is_creator = await verify_user_is_full_admin_or_owner(context.bot, chan_id, user.id)
        if not auth_ok:
            await query.answer("❌ Only verified Channel Owner or Full-Power Admin can invite.", show_alert=True)
            return

        ch = await channel_repo.get_by_id(chan_id)
        ch_title = ch.title if ch else "Channel"
        bot_user = await context.bot.get_me()
        clean_code = chan_id.replace("-100", "").replace("-", "")
        invite_link = f"https://t.me/{bot_user.username}?start=invite_{clean_code}"

        await query.message.edit_text(
            f"👑 <b>Channel Ownership Verified!</b>\n\n"
            f"• <b>Channel:</b> {html.escape(ch_title)}\n"
            f"• <b>ID:</b> <code>{chan_id}</code>\n\n"
            f"🔗 <b>Authorized Poster Invite Link:</b>\n"
            f"<code>{invite_link}</code>\n\n"
            f"Send this link to any admin or friend. When they tap it, Kiwi post Maker will authorize them to post to this channel!\n\n"
            f"<i>Or use command:</i>\n<code>/invite {chan_id} &lt;user_id&gt;</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back to Main Menu", callback_data="nav_home")]
            ]),
        )
        return

def get_callback_handlers():
    return [
        CallbackQueryHandler(handle_callback_query),
    ]
