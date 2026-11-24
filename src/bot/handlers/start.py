import html
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import CommandHandler, ContextTypes, MessageHandler, filters

from ..keyboards.menus import get_main_menu_keyboard
from ..database.repositories.posts import PostRepository
from ..database.repositories.channels import ChannelRepository

logger = logging.getLogger(__name__)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    first_name = html.escape(user.first_name if user else "Creator")
    channel_repo: ChannelRepository = context.bot_data.get("channel_repo")

    # Check for Deep-Linked Invite Code
    if context.args and channel_repo:
        arg = context.args[0].strip()
        if arg.startswith("invite_"):
            clean_code = arg.replace("invite_", "")
            candidates = [f"-100{clean_code}", f"-{clean_code}", clean_code]
            target_chan = None
            for cand in candidates:
                target_chan = await channel_repo.get_by_id(cand)
                if target_chan:
                    break

            if target_chan:
                await channel_repo.add_authorized_user(target_chan.channel_id, user.id)
                await update.message.reply_text(
                    f"🎉 <b>Channel Authorization Successful!</b>\n\n"
                    f"You have been authorized by the owner to post to <b>{html.escape(target_chan.title)}</b>.\n\n"
                    f"Tap <b>📝 CREATE POST</b> below to create and publish posts to this channel!",
                    parse_mode=ParseMode.HTML,
                    reply_markup=get_main_menu_keyboard(),
                )
                return

    welcome_text = (
        f"👋 <b>Welcome, {first_name}!</b>\n\n"
        f"🤖 <b>Postbot</b> is your production-grade Telegram post creator and automated publisher.\n\n"
        f"✨ <b>Features:</b>\n"
        f"• Rich text & Unicode font styling\n"
        f"• Colored inline URL buttons (Blue, Green, Red)\n"
        f"• Multi-image / video album publishing\n"
        f"• Bot API 10.1 Native Table & Article Builder\n"
        f"• Scheduled posts with MongoDB atomic locking\n"
        f"• 100% Free: No ads or subscriptions\n\n"
        f"<i>Select an option below to begin:</i>"
    )

    await update.message.reply_text(
        text=welcome_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard(),
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    post_repo: PostRepository = context.bot_data["post_repo"]
    channel_repo: ChannelRepository = context.bot_data["channel_repo"]

    try:
        channels = await channel_repo.get_user_channels(user.id)
        draft = await post_repo.get_latest_draft(user.id)
        channels_count = len(channels)
        draft_info = f"Post #{draft.id}" if draft else "None"
    except Exception as exc:
        logger.warning("Could not fetch profile stats from database: %s", exc)
        channels_count = 0
        draft_info = "Database Offline"

    profile_text = (
        f"👤 <b>Your Profile</b>\n\n"
        f"• <b>Name:</b> {html.escape(user.first_name or 'N/A')}\n"
        f"• <b>User ID:</b> <code>{user.id}</code>\n"
        f"• <b>Username:</b> @{html.escape(user.username)} " if user.username else f"• <b>Username:</b> None\n"
    )
    profile_text += (
        f"• <b>Connected Channels:</b> {channels_count}\n"
        f"• <b>Active Draft:</b> {draft_info}\n"
    )

    await update.message.reply_text(
        text=profile_text,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard(),
    )

async def how_it_works_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    guide = (
        "📖 <b>How To Use Postbot</b>\n\n"
        "1️⃣ <b>Connect Channels:</b> Tap <i>📢 MY CHANNELS</i>, add the bot as an administrator "
        "to your channel with 'Post Messages' rights, and send the channel ID or forward a post.\n\n"
        "2️⃣ <b>Create a Post:</b> Tap <i>📝 CREATE POST</i> to open the interactive studio.\n\n"
        "3️⃣ <b>Format & Decorate:</b> Set text, choose aesthetic Unicode lettering, build monospace tables, "
        "attach photos/videos (albums up to 10 files), and add styled buttons.\n\n"
        "4️⃣ <b>Publish or Schedule:</b> Review with <i>Preview</i>, then either <i>Publish Now</i> "
        "or pick a future date to schedule."
    )
    await update.message.reply_text(
        text=guide,
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_menu_keyboard(),
    )

def get_start_handlers():
    return [
        CommandHandler("start", start_command),
        MessageHandler(filters.Regex(r"^👤 PROFILE$"), profile_command),
        MessageHandler(filters.Regex(r"^📖 HOW IT WORKS$"), how_it_works_command),
    ]
