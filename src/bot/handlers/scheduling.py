import html
import logging
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, MessageHandler, filters

from ..database.repositories.posts import PostRepository

logger = logging.getLogger(__name__)

async def schedules_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return

    post_repo: PostRepository = context.bot_data["post_repo"]
    # List queued posts
    async with post_repo.__class__(post_repo.db_path) as repo:
        pass

    text = (
        "⏰ <b>Scheduled Posts Queue</b>\n\n"
        "Here you can view all posts queued for automatic publishing.\n\n"
        "To schedule a post, open <b>CREATE POST</b>, design your message, and tap <b>Schedule</b>."
    )
    await update.message.reply_text(text=text, parse_mode=ParseMode.HTML)

def get_scheduling_handlers():
    return [
        MessageHandler(filters.Regex(r"^⏰ SCHEDULES$"), schedules_command),
    ]
