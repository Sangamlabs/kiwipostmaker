from typing import Any, Dict, List, Optional
import pymongo

class MediaRepository:
    """Media repository backed by MongoDB."""

    def __init__(self, db: Any):
        self.db = db

    async def add_media(
        self, post_id: int, file_id: str, media_type: str, caption: Optional[str] = None, position: int = 0
    ) -> int:
        counter = await self.db.counters.find_one_and_update(
            {"_id": "media_id"},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        media_id = counter["seq"]
        doc = {
            "_id": media_id,
            "id": media_id,
            "post_id": post_id,
            "file_id": file_id,
            "media_type": media_type,
            "caption": caption,
            "position": position,
        }
        await self.db.media.insert_one(doc)
        return media_id

    async def get_post_media(self, post_id: int) -> List[Dict[str, Any]]:
        cursor = self.db.media.find({"post_id": post_id}).sort([("position", pymongo.ASCENDING), ("id", pymongo.ASCENDING)])
        return await cursor.to_list(length=100)

    async def clear_post_media(self, post_id: int) -> None:
        await self.db.media.delete_many({"post_id": post_id})
