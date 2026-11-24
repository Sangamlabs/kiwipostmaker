import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from telegram import Bot

from ..database.repositories.posts import PostRepository
from .publisher import publish_post
from .channel_access import check_channel_permissions

logger = logging.getLogger(__name__)

class PostScheduler:
    """
    Background worker that continuously queries for due scheduled posts,
    locks them to prevent duplicate publishing, publishes via publisher worker,
    and updates database status (Pages 1-2 & 7 of DX-Notes).
    """

    def __init__(self, bot: Bot, post_repo: PostRepository, interval_seconds: int = 10):
        self.bot = bot
        self.post_repo = post_repo
        self.interval_seconds = interval_seconds
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    def start(self) -> None:
        """Start the background scheduler job."""
        if self._is_running:
            return
        self.scheduler.add_job(
            self.process_due_posts,
            "interval",
            seconds=self.interval_seconds,
            id="publish_due_posts",
            replace_existing=True,
        )
        self.scheduler.start()
        self._is_running = True
        logger.info("PostScheduler started (polling every %ds)", self.interval_seconds)

    def shutdown(self) -> None:
        """Gracefully stop scheduler."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("PostScheduler shutdown.")

    async def process_due_posts(self) -> int:
        """
        Polls database for queued posts whose scheduled_at <= now,
        claims each post atomically, publishes, and updates status.
        """
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            due_posts = await self.post_repo.get_due_posts(now_iso)
        except Exception as exc:
            logger.debug("Scheduler could not fetch due posts (db may be offline): %s", exc)
            return 0

        processed_count = 0

        for post in due_posts:
            # 1. Lock job atomically (prevents duplicate execution across workers/restarts)
            try:
                claimed = await self.post_repo.claim_post_for_publishing(post.id)
            except Exception as lock_err:
                logger.error("Could not claim post %d: %s", post.id, lock_err)
                continue

            if not claimed:
                logger.info("Post %d already claimed by another worker. Skipping.", post.id)
                continue

            logger.info("Publishing due scheduled post %d to channel %s...", post.id, post.channel_id)

            # 2. Check channel permissions
            perm_ok, perm_err = await check_channel_permissions(self.bot, post.channel_id)
            if not perm_ok:
                logger.error("Channel permission check failed for post %d: %s", post.id, perm_err)
                await self.post_repo.mark_failed(post.id, f"Channel permission error: {perm_err}")
                continue

            # 3. Publish content
            success, msg_ids, error_msg = await publish_post(self.bot, post)
            if success:
                logger.info("Post %d published successfully (Message IDs: %s)", post.id, msg_ids)
                await self.post_repo.mark_published(post.id, msg_ids)
                processed_count += 1
            else:
                logger.error("Publishing post %d failed: %s", post.id, error_msg)
                await self.post_repo.mark_failed(post.id, error_msg)

        return processed_count
