import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import pymongo
from ...models.post import Post

logger = logging.getLogger(__name__)

class PostRepository:
    """Post repository backed by MongoDB."""

    def __init__(self, db: Any):
        self.db = db

    def _doc_to_post(self, doc: Optional[Dict[str, Any]]) -> Optional[Post]:
        if not doc:
            return None
        return Post(
            id=doc.get("id"),
            owner_user_id=doc.get("owner_user_id", 0),
            channel_id=doc.get("channel_id"),
            text=doc.get("text"),
            media_json=doc.get("media_json") if isinstance(doc.get("media_json"), str) else json.dumps(doc.get("media_json", [])),
            buttons_json=doc.get("buttons_json") if isinstance(doc.get("buttons_json"), str) else json.dumps(doc.get("buttons_json", [])),
            inline_buttons_json=doc.get("inline_buttons_json") if isinstance(doc.get("inline_buttons_json"), str) else json.dumps(doc.get("inline_buttons_json", [])),
            row_buttons_json=doc.get("row_buttons_json") if isinstance(doc.get("row_buttons_json"), str) else json.dumps(doc.get("row_buttons_json", [])),
            table_json=doc.get("table_json") if isinstance(doc.get("table_json"), str) or doc.get("table_json") is None else json.dumps(doc.get("table_json")),
            post_type=doc.get("post_type", "standard"),
            button_type=doc.get("button_type", "inline"),
            media_position=doc.get("media_position", "top"),
            scheduled_at=doc.get("scheduled_at"),
            status=doc.get("status", "draft"),
            telegram_message_ids=doc.get("telegram_message_ids") if isinstance(doc.get("telegram_message_ids"), str) else json.dumps(doc.get("telegram_message_ids", [])),
            last_error=doc.get("last_error"),
            created_at=str(doc.get("created_at", "")),
            updated_at=str(doc.get("updated_at", "")),
        )

    async def _get_next_id(self) -> int:
        counter = await self.db.counters.find_one_and_update(
            {"_id": "post_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return counter["seq"]

    async def create_draft(self, owner_user_id: int, channel_id: Optional[str] = None, post_type: str = "standard") -> Post:
        post_id = await self._get_next_id()
        now = datetime.now(timezone.utc).isoformat()
        doc = {
            "_id": post_id,
            "id": post_id,
            "owner_user_id": owner_user_id,
            "channel_id": channel_id,
            "text": "",
            "media_json": "[]",
            "buttons_json": "[]",
            "inline_buttons_json": "[]",
            "row_buttons_json": "[]",
            "table_json": None,
            "post_type": post_type,
            "button_type": "inline",
            "media_position": "top",
            "scheduled_at": None,
            "status": "draft",
            "telegram_message_ids": "[]",
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        }
        await self.db.posts.insert_one(doc)
        return self._doc_to_post(doc)

    async def get_by_id(self, post_id: int) -> Optional[Post]:
        doc = await self.db.posts.find_one({"id": post_id})
        return self._doc_to_post(doc)

    async def get_latest_draft(self, owner_user_id: int, post_type: Optional[str] = None) -> Optional[Post]:
        query: Dict[str, Any] = {"owner_user_id": owner_user_id, "status": "draft"}
        if post_type:
            query["post_type"] = post_type
        doc = await self.db.posts.find_one(
            query,
            sort=[("id", pymongo.DESCENDING)],
        )
        return self._doc_to_post(doc)

    async def update_post(self, post_id: int, **kwargs) -> Optional[Post]:
        if not kwargs:
            return await self.get_by_id(post_id)

        update_fields = {}
        for key, value in kwargs.items():
            if key in {"channel_id", "text", "media_json", "buttons_json", "inline_buttons_json", "row_buttons_json", "table_json", "post_type", "button_type", "media_position", "scheduled_at", "status", "telegram_message_ids", "last_error"}:
                update_fields[key] = value

        update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()

        doc = await self.db.posts.find_one_and_update(
            {"id": post_id},
            {"$set": update_fields},
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return self._doc_to_post(doc)

    async def claim_post_for_publishing(self, post_id: int) -> bool:
        """
        Atomically lock and claim a post for publishing to prevent duplicate sends.
        Uses MongoDB atomic find_one_and_update to guarantee isolation.
        """
        now = datetime.now(timezone.utc).isoformat()
        result = await self.db.posts.find_one_and_update(
            {"id": post_id, "status": {"$in": ["queued", "draft"]}},
            {"$set": {"status": "publishing", "updated_at": now}},
        )
        return result is not None

    async def mark_published(self, post_id: int, message_ids: List[int]) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.posts.update_one(
            {"id": post_id},
            {
                "$set": {
                    "status": "published",
                    "telegram_message_ids": json.dumps(message_ids),
                    "last_error": None,
                    "updated_at": now,
                }
            },
        )

    async def mark_failed(self, post_id: int, error_message: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        await self.db.posts.update_one(
            {"id": post_id},
            {
                "$set": {
                    "status": "failed",
                    "last_error": error_message,
                    "updated_at": now,
                }
            },
        )

    async def get_due_posts(self, current_iso_time: str) -> List[Post]:
        cursor = self.db.posts.find(
            {
                "status": "queued",
                "scheduled_at": {"$ne": None, "$lte": current_iso_time},
            }
        ).sort("scheduled_at", pymongo.ASCENDING)
        docs = await cursor.to_list(length=100)
        return [self._doc_to_post(doc) for doc in docs]

    async def delete_post(self, post_id: int, owner_user_id: int) -> bool:
        result = await self.db.posts.delete_one({"id": post_id, "owner_user_id": owner_user_id})
        return result.deleted_count > 0
