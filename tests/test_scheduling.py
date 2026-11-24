"""
Tests for scheduling engine, persistent queue, and atomic lock duplicate prevention with MongoDB.
Matches Pages 1-2 & 7 of DX-Notes with MongoDB as main database.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock
from copy import deepcopy

from src.bot.database.repositories.posts import PostRepository
from src.bot.models.post import Post
from src.bot.services.scheduler import PostScheduler

class MockCursor:
    def __init__(self, items):
        self.items = items

    def sort(self, *args, **kwargs):
        return self

    async def to_list(self, length=None):
        return list(self.items)

class MockAsyncMongoCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(deepcopy(doc))
        return MagicMock(inserted_id=doc.get("_id"))

    async def find_one(self, filter_doc, sort=None):
        candidates = list(reversed(self.docs)) if sort else self.docs
        for d in candidates:
            match = True
            for k, v in filter_doc.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                return deepcopy(d)
        return None

    async def find_one_and_update(self, filter_doc, update_doc, upsert=False, return_document=None):
        for d in self.docs:
            match = True
            for k, v in filter_doc.items():
                if isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        match = False
                        break
                elif d.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update_doc:
                    d.update(update_doc["$set"])
                if "$inc" in update_doc:
                    for ik, iv in update_doc["$inc"].items():
                        d[ik] = d.get(ik, 0) + iv
                return deepcopy(d)

        if upsert:
            new_doc = deepcopy(filter_doc)
            if "$set" in update_doc:
                new_doc.update(update_doc["$set"])
            if "$inc" in update_doc:
                for ik, iv in update_doc["$inc"].items():
                    new_doc[ik] = new_doc.get(ik, 0) + iv
            self.docs.append(new_doc)
            return deepcopy(new_doc)
        return None

    async def update_one(self, filter_doc, update_doc, upsert=False):
        for d in self.docs:
            match = True
            for k, v in filter_doc.items():
                if d.get(k) != v:
                    match = False
                    break
            if match:
                if "$set" in update_doc:
                    d.update(update_doc["$set"])
                return MagicMock(matched_count=1, modified_count=1)
        if upsert:
            new_doc = deepcopy(filter_doc)
            if "$set" in update_doc:
                new_doc.update(update_doc["$set"])
            self.docs.append(new_doc)
            return MagicMock(matched_count=0, upserted_id=1)
        return MagicMock(matched_count=0, modified_count=0)

    def find(self, filter_doc):
        results = []
        for d in self.docs:
            match = True
            for k, v in filter_doc.items():
                if isinstance(v, dict):
                    if "$ne" in v and d.get(k) == v["$ne"]:
                        match = False
                        break
                    if "$lte" in v and not (d.get(k) and d.get(k) <= v["$lte"]):
                        match = False
                        break
                elif d.get(k) != v:
                    match = False
                    break
            if match:
                results.append(deepcopy(d))
        return MockCursor(results)

class MockMongoDB:
    def __init__(self):
        self.posts = MockAsyncMongoCollection()
        self.channels = MockAsyncMongoCollection()
        self.counters = MockAsyncMongoCollection()
        self.media = MockAsyncMongoCollection()

@pytest.fixture
def mongo_post_repo():
    """Fixture providing a MongoDB post repository with in-memory collection mock."""
    mock_db = MockMongoDB()
    return PostRepository(mock_db)

@pytest.mark.asyncio
async def test_atomic_lock_duplicate_prevention(mongo_post_repo):
    """
    Verify that claiming a queued post in MongoDB is atomic.
    Only one worker can claim it; subsequent claims return False.
    (Prevents duplicate posting upon restart or across workers).
    """
    post = await mongo_post_repo.create_draft(owner_user_id=456, channel_id="-100111")
    # Queue the post
    future_time = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    await mongo_post_repo.update_post(post.id, status="queued", scheduled_at=future_time)

    # Worker 1 claims post
    claimed_1 = await mongo_post_repo.claim_post_for_publishing(post.id)
    assert claimed_1 is True

    # Worker 2 attempts to claim same post concurrently
    claimed_2 = await mongo_post_repo.claim_post_for_publishing(post.id)
    assert claimed_2 is False  # Rejected, duplicate publish prevented!

@pytest.mark.asyncio
async def test_scheduler_due_posts_processing(mongo_post_repo):
    """Verify scheduler claims and publishes due posts in MongoDB, then marks them published."""
    # 1. Create a due post
    post = await mongo_post_repo.create_draft(owner_user_id=456, channel_id="-100111")
    past_time = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
    await mongo_post_repo.update_post(
        post.id,
        text="Scheduled post content",
        status="queued",
        scheduled_at=past_time,
    )

    # 2. Mock Bot and channel permissions
    mock_bot = MagicMock()
    mock_msg = MagicMock()
    mock_msg.message_id = 999
    mock_bot.send_message = AsyncMock(return_value=mock_msg)

    # Mock get_chat and get_chat_member for channel permission check
    mock_chat = MagicMock()
    mock_chat.title = "Target Channel"
    mock_bot.get_chat = AsyncMock(return_value=mock_chat)

    mock_bot_user = MagicMock()
    mock_bot_user.id = 12345
    mock_bot.get_me = AsyncMock(return_value=mock_bot_user)

    mock_member = MagicMock()
    mock_member.status = "administrator"
    mock_member.can_post_messages = True
    mock_bot.get_chat_member = AsyncMock(return_value=mock_member)

    # 3. Process due posts
    scheduler = PostScheduler(bot=mock_bot, post_repo=mongo_post_repo)
    processed = await scheduler.process_due_posts()
    assert processed == 1

    # 4. Verify post status in database is now 'published'
    updated_post = await mongo_post_repo.get_by_id(post.id)
    assert updated_post.status == "published"
    assert updated_post.message_ids_list == [999]
    assert updated_post.last_error is None
