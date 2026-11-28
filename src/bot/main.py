"""
Main entry point for Postbot.
Initializes python-telegram-bot Application, MongoDB (Motor), and APScheduler.
"""
import asyncio
import html
import logging
import sys
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, ApplicationBuilder, ContextTypes

from . import config
from .keep_alive import start_keep_alive, stop_keep_alive
from .database.connection import DatabaseConnection
from .database.repositories.posts import PostRepository
from .database.repositories.channels import ChannelRepository
from .database.repositories.media import MediaRepository
from .services.scheduler import PostScheduler
from .handlers.start import get_start_handlers
from .handlers.channels import get_channel_handlers
from .handlers.post_editor import get_post_editor_handlers
from .handlers.scheduling import get_scheduling_handlers
from .handlers.callbacks import get_callback_handlers

# Configure structured Python logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - [%(levelname)s] - %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("Postbot")

async def post_init(application: Application) -> None:
    """Lifecycle hook called when application event loop is running."""
    # Render aur UptimeRobot ke liye keep-alive web server start karo
    web_runner = await start_keep_alive()
    application.bot_data["web_runner"] = web_runner

    db_conn: DatabaseConnection = application.bot_data["db_conn"]
    await db_conn.init_indexes()

    scheduler: PostScheduler = application.bot_data["scheduler"]
    scheduler.start()
    logger.info("Postbot background scheduler initialized successfully.")

async def post_shutdown(application: Application) -> None:
    """Lifecycle hook called during bot shutdown."""
    scheduler: PostScheduler = application.bot_data.get("scheduler")
    if scheduler:
        scheduler.shutdown()
    db_conn: DatabaseConnection = application.bot_data.get("db_conn")
    if db_conn:
        await db_conn.close()
    web_runner = application.bot_data.get("web_runner")
    if web_runner:
        await stop_keep_alive(web_runner)
    logger.info("Postbot shutdown complete.")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for all uncaught exceptions."""
    logger.error("Exception while handling an update: %s", context.error, exc_info=context.error)
    if isinstance(update, Update) and update.effective_message:
        err_msg = str(context.error)
        if "ServerSelectionTimeoutError" in err_msg or "WinError 10061" in err_msg or "AutoReconnect" in err_msg:
            user_facing = (
                "⚠️ <b>Database Connection Error</b>\n\n"
                "Postbot cannot connect to MongoDB.\n\n"
                "<b>How to resolve:</b>\n"
                "1. If running locally, start your MongoDB server.\n"
                "2. If using MongoDB Atlas, check your <code>MONGO_URI</code> in <code>.env</code>."
            )
        else:
            user_facing = f"⚠️ An error occurred: <code>{html.escape(err_msg[:200])}</code>"

        try:
            await update.effective_message.reply_text(user_facing, parse_mode=ParseMode.HTML)
        except Exception:
            pass

def build_application() -> Application:
    """Configures and builds the Telegram Application with handlers and lifecycle hooks."""
    if not config.BOT_TOKEN:
        logger.warning("BOT_TOKEN is not set in .env! Update .env with your Telegram bot token.")

    # 1. Initialize MongoDB Database Connection & Repositories
    db_conn = DatabaseConnection(config.MONGO_URI, config.DATABASE_NAME)
    db = db_conn.get_database()

    post_repo = PostRepository(db)
    channel_repo = ChannelRepository(db)
    media_repo = MediaRepository(db)

    # 2. Build Telegram Application with post_init and post_shutdown hooks
    token = config.BOT_TOKEN or "0000000000:AAABBBCCCDDDEEEFFFGGGHHHIIIJJJKKKLL"
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # 3. Store shared dependencies in bot_data
    app.bot_data["db_conn"] = db_conn
    app.bot_data["post_repo"] = post_repo
    app.bot_data["channel_repo"] = channel_repo
    app.bot_data["media_repo"] = media_repo

    # 4. Attach Scheduler
    scheduler = PostScheduler(bot=app.bot, post_repo=post_repo, interval_seconds=10)
    app.bot_data["scheduler"] = scheduler

    # 5. Register Handlers
    for handler in get_start_handlers():
        app.add_handler(handler)
    for handler in get_channel_handlers():
        app.add_handler(handler)
    for handler in get_post_editor_handlers():
        app.add_handler(handler)
    for handler in get_scheduling_handlers():
        app.add_handler(handler)
    for handler in get_callback_handlers():
        app.add_handler(handler)

    # 6. Register Global Error Handler
    app.add_error_handler(error_handler)

    return app

def main():
    app = build_application()
    logger.info("Starting Postbot polling (MongoDB: %s)...", config.DATABASE_NAME)
    try:
        app.run_polling()
    except Exception as exc:
        logger.error("Bot runtime error: %s", exc)

if __name__ == "__main__":
    main()
