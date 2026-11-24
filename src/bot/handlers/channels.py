import html
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from ..database.repositories.channels import ChannelRepository
from ..services.channel_access import check_channel_permissions, verify_user_is_full_admin_or_owner

logger = logging.getLogger(__name__)

async def channels_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    channel_repo: ChannelRepository = context.bot_data["channel_repo"]
    try:
        channels = await channel_repo.get_user_channels(user.id)
    except Exception as exc:
        logger.error("Database error retrieving channels for user %d: %s", user.id, exc)
        await update.message.reply_text(
            "⚠️ <b>Database Connection Error</b>\n\n"
            "Cannot connect to MongoDB to load your channels list. Please verify your database service.",
            parse_mode=ParseMode.HTML,
        )
        return

    if not channels:
        text = (
            "📢 <b>Channel Management</b>\n\n"
            "You have no connected channels yet.\n\n"
            "<b>How to connect a channel:</b>\n"
            "1. Add this bot as an <b>Admin</b> to your channel with <i>'Post Messages'</i> permission.\n"
            "2. Make sure you are the <b>Owner</b> or a <b>Full-Power Admin</b> with <i>'Add New Admins'</i> (can_promote_members) authority.\n"
            "3. Send <code>/connect @your_channel</code> or forward any message from that channel here."
        )
        await update.message.reply_text(text=text, parse_mode=ParseMode.HTML)
    else:
        text = "📢 <b>Your Connected Channels:</b>\n\n"
        buttons = []
        for ch in channels:
            uname = f" (@{ch.username})" if ch.username else ""
            auth_count = len(ch.authorized_users) if ch.authorized_users else 1
            text += f"• <b>{html.escape(ch.title)}</b>{uname}\n"
            text += f"  ID: <code>{ch.channel_id}</code> | Authorized Posters: <b>{auth_count}</b>\n\n"
            buttons.append([InlineKeyboardButton(f"👥 Invite Admin: {ch.title[:20]}", callback_data=f"invite_chan_{ch.channel_id}")])

        text += (
            "💡 <i>Tip: Tap an 'Invite Admin' button below to generate an authorized poster link for that channel, "
            "or use <code>/invite @channel &lt;user_id&gt;</code>.</i>"
        )
        await update.message.reply_text(
            text=text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(buttons) if buttons else None,
        )

async def connect_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Connect a channel via /connect @channel_username or /connect channel_id."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    args = context.args
    if not args:
        await message.reply_text(
            "⚠️ <b>Please specify the channel username or ID:</b>\n\n"
            "• Example: <code>/connect @Sanglabs</code>\n"
            "• Or ID: <code>/connect -1001234567890</code>\n\n"
            "<i>💡 Tip: For private channels, simply forward any message from the channel here!</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    raw = args[0].strip()
    if not raw.startswith("@") and not (raw.startswith("-") and raw[1:].isdigit()):
        channel_target = f"@{raw}"
    else:
        channel_target = raw

    try:
        chat = await context.bot.get_chat(channel_target)
        if chat.type != "channel":
            await message.reply_text(
                f"❌ <b>{html.escape(channel_target)}</b> is not a channel.",
                parse_mode=ParseMode.HTML,
            )
            return

        channel_id = str(chat.id)
        title = chat.title or "Telegram Channel"
        username = chat.username

        # 1. Check Bot permissions (Bot must be admin with can_post_messages)
        perm_ok, perm_err = await check_channel_permissions(context.bot, channel_id)
        if not perm_ok:
            await message.reply_text(
                f"❌ <b>Could not connect channel '{html.escape(title)}':</b>\n\n"
                f"{perm_err}\n\n"
                "<b>Steps to fix:</b>\n"
                "1. Open channel settings $\rightarrow$ Administrators $\rightarrow$ Add Administrator.\n"
                "2. Add this bot and turn ON <b>'Post Messages'</b>.",
                parse_mode=ParseMode.HTML,
            )
            return

        # 2. Verify User Authority: Must be Channel Owner or Full-Power Admin with can_promote_members
        auth_ok, auth_err, is_creator = await verify_user_is_full_admin_or_owner(context.bot, channel_id, user.id)
        if not auth_ok:
            await message.reply_text(
                f"⚠️ <b>Full-Power Admin or Owner Required:</b>\n\n"
                f"{auth_err}\n\n"
                f"<i>Requirement:</i> You must be the Creator/Owner or have 'Add New Admins' (can_promote_members) authority in <b>{html.escape(title)}</b> to connect it.",
                parse_mode=ParseMode.HTML,
            )
            return

        # 3. Save connection in MongoDB
        channel_repo: ChannelRepository = context.bot_data["channel_repo"]
        await channel_repo.add_channel(
            channel_id=channel_id,
            title=title,
            username=username,
            owner_id=user.id,
        )

        await message.reply_text(
            f"🎉 <b>Channel Connected Successfully!</b>\n\n"
            f"• <b>Title:</b> {html.escape(title)}\n"
            f"• <b>Username:</b> @{username if username else 'Private'}\n"
            f"• <b>ID:</b> <code>{channel_id}</code>\n\n"
            f"You can now select this channel when drafting, styling, and publishing posts!",
            parse_mode=ParseMode.HTML,
        )

    except Exception as exc:
        logger.error("Failed to connect channel %s: %s", channel_target, exc)
        await message.reply_text(
            f"❌ <b>Could not find or access channel:</b> <code>{html.escape(channel_target)}</code>\n\n"
            f"<i>Error:</i> {html.escape(str(exc))}\n\n"
            "<b>Please make sure:</b>\n"
            "1. The username or ID is spelled correctly.\n"
            "2. The bot is already added to the channel as an Admin.",
            parse_mode=ParseMode.HTML,
        )

async def handle_channel_forward(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Detect forwarded post from a channel to automatically register it."""
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    forward_chat = getattr(message, "forward_from_chat", None)
    if not forward_chat or forward_chat.type != "channel":
        return

    channel_id = str(forward_chat.id)
    title = forward_chat.title or "Telegram Channel"
    username = forward_chat.username

    # Verify bot permissions
    perm_ok, perm_err = await check_channel_permissions(context.bot, channel_id)
    if not perm_ok:
        await message.reply_text(
            f"❌ <b>Could not connect channel '{html.escape(title)}':</b>\n\n"
            f"{perm_err}\n\n"
            "Please ensure the bot is added as an Administrator with 'Post Messages' permission.",
            parse_mode=ParseMode.HTML,
        )
        return

    # Verify User Authority: Must be Channel Creator/Owner OR Full-Power Admin with can_promote_members
    auth_ok, auth_err, is_creator = await verify_user_is_full_admin_or_owner(context.bot, channel_id, user.id)
    if not auth_ok:
        await message.reply_text(
            f"⚠️ <b>Full-Power Admin or Owner Required:</b>\n\n"
            f"{auth_err}\n\n"
            f"Only the channel Owner or a Full-Power Admin with 'Add New Admins' authority can connect <b>{html.escape(title)}</b>.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        channel_repo: ChannelRepository = context.bot_data["channel_repo"]
        await channel_repo.add_channel(
            channel_id=channel_id,
            title=title,
            username=username,
            owner_id=user.id,
        )

        await message.reply_text(
            f"✅ <b>Channel Connected Successfully!</b>\n\n"
            f"• <b>Title:</b> {html.escape(title)}\n"
            f"• <b>ID:</b> <code>{channel_id}</code>\n\n"
            f"You can now select this channel when creating or scheduling posts.",
            parse_mode=ParseMode.HTML,
        )
    except Exception as exc:
        logger.error("Database error saving forwarded channel: %s", exc)
        await message.reply_text(
            "⚠️ <b>Database Connection Error</b>\n\n"
            "Cannot connect to MongoDB to save the channel. Please check your database service.",
            parse_mode=ParseMode.HTML,
        )

async def invite_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Allows a verified channel Owner or Full-Power Admin to invite/authorize another user to post to their channel.
    Usage:
    /invite @channel <user_id>
    """
    message = update.effective_message
    user = update.effective_user
    if not message or not user:
        return

    args = context.args
    if not args or len(args) < 2:
        await message.reply_text(
            "👥 <b>Invite Post Creator / Admin</b>\n\n"
            "Authorize another user or admin to draft and publish posts to your channel!\n\n"
            "<b>Usage:</b>\n"
            "<code>/invite @channel &lt;user_id&gt;</code>\n\n"
            "<b>Example:</b>\n"
            "<code>/invite @Sanglabs 123456789</code>\n\n"
            "<i>💡 You can also generate a 1-click invite link under <b>📢 MY CHANNELS</b>!</i>",
            parse_mode=ParseMode.HTML,
        )
        return

    raw_chan = args[0].strip()
    target_raw = args[1].strip()

    if not raw_chan.startswith("@") and not (raw_chan.startswith("-") and raw_chan[1:].isdigit()):
        chan_target = f"@{raw_chan}"
    else:
        chan_target = raw_chan

    try:
        chat = await context.bot.get_chat(chan_target)
        channel_id = str(chat.id)
        title = chat.title or "Channel"

        # 1. Verify that caller is verified Owner or Full-Power Admin
        auth_ok, auth_err, is_creator = await verify_user_is_full_admin_or_owner(context.bot, channel_id, user.id)
        if not auth_ok:
            await message.reply_text(
                f"❌ <b>Permission Denied:</b>\n\n"
                f"{auth_err}\n\n"
                f"Only the verified Owner or Full-Power Admin of <b>{html.escape(title)}</b> can authorize other users.",
                parse_mode=ParseMode.HTML,
            )
            return

        channel_repo: ChannelRepository = context.bot_data["channel_repo"]
        target_id = None
        if target_raw.lstrip("-").isdigit():
            target_id = int(target_raw)

        bot_user = await context.bot.get_me()
        clean_code = channel_id.replace("-100", "").replace("-", "")
        invite_link = f"https://t.me/{bot_user.username}?start=invite_{clean_code}"

        if target_id:
            await channel_repo.add_authorized_user(channel_id, target_id)
            await message.reply_text(
                f"🎉 <b>Admin Authorized Successfully!</b>\n\n"
                f"• <b>Channel:</b> {html.escape(title)}\n"
                f"• <b>Authorized User ID:</b> <code>{target_id}</code>\n\n"
                f"That user can now select <b>{html.escape(title)}</b> as destination and publish posts!\n\n"
                f"🔗 <b>Shareable Link:</b>\n<code>{invite_link}</code>",
                parse_mode=ParseMode.HTML,
            )
        else:
            await message.reply_text(
                f"👑 <b>Ownership Verified for {html.escape(title)}!</b>\n\n"
                f"Send this 1-click authorization link to your admin/friend:\n\n"
                f"🔗 <code>{invite_link}</code>\n\n"
                f"<i>When they tap the link, Postbot will automatically authorize them to post to this channel.</i>",
                parse_mode=ParseMode.HTML,
            )
    except Exception as exc:
        logger.error("Invite error: %s", exc)
        await message.reply_text(
            f"❌ <b>Error verifying or authorizing channel:</b> {html.escape(str(exc))}",
            parse_mode=ParseMode.HTML,
        )

def get_channel_handlers():
    return [
        CommandHandler("connect", connect_command),
        CommandHandler("invite", invite_command),
        MessageHandler(filters.Regex(r"^📢 MY CHANNELS$"), channels_menu),
        MessageHandler(filters.FORWARDED & filters.ChatType.PRIVATE, handle_channel_forward),
    ]
