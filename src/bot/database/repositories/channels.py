from datetime import datetime, timezone
from typing import Any, List, Optional
import pymongo
from ...models.channel import Channel

class ChannelRepository:
    """Channel repository backed by MongoDB."""

    def __init__(self, db: Any):
        self.db = db

    async def add_channel(self, channel_id: str, title: str, username: Optional[str], owner_id: int) -> Channel:
        now = datetime.now(timezone.utc).isoformat()
        # Find existing channel to preserve creator and authorized posters
        existing = await self.db.channels.find_one({"channel_id": channel_id})
        existing_authorized = existing.get("authorized_users", []) if existing else []
        authorized_users = list(set(existing_authorized + [owner_id]))
        primary_owner = existing.get("owner_id", owner_id) if existing else owner_id

        doc = {
            "channel_id": channel_id,
            "title": title,
            "username": username,
            "owner_id": primary_owner,
            "authorized_users": authorized_users,
            "added_at": now,
        }
        await self.db.channels.update_one(
            {"channel_id": channel_id},
            {
                "$set": {
                    "title": title,
                    "username": username,
                    "added_at": now,
                    "owner_id": primary_owner,
                },
                "$addToSet": {"authorized_users": owner_id},
            },
            upsert=True,
        )
        return Channel(
            channel_id=channel_id,
            title=title,
            username=username,
            owner_id=primary_owner,
            authorized_users=authorized_users,
            added_at=now,
        )

    async def add_authorized_user(self, channel_id: str, user_id: int) -> bool:
        """Add an authorized posting admin to a channel."""
        res = await self.db.channels.update_one(
            {"channel_id": channel_id},
            {"$addToSet": {"authorized_users": user_id}},
        )
        return res.modified_count > 0 or res.matched_count > 0

    async def remove_authorized_user(self, channel_id: str, user_id: int) -> bool:
        """Revoke an authorized posting admin from a channel."""
        res = await self.db.channels.update_one(
            {"channel_id": channel_id},
            {"$pull": {"authorized_users": user_id}},
        )
        return res.modified_count > 0

    async def get_by_id(self, channel_id: str) -> Optional[Channel]:
        doc = await self.db.channels.find_one({"channel_id": channel_id})
        if not doc:
            return None
        return Channel(
            channel_id=doc["channel_id"],
            title=doc["title"],
            username=doc.get("username"),
            owner_id=doc.get("owner_id", 0),
            authorized_users=doc.get("authorized_users", [doc.get("owner_id", 0)]),
            added_at=doc.get("added_at"),
        )

    async def get_user_channels(self, user_id: int) -> List[Channel]:
        cursor = self.db.channels.find({
            "$or": [
                {"owner_id": user_id},
                {"authorized_users": user_id},
            ]
        }).sort("added_at", pymongo.DESCENDING)
        docs = await cursor.to_list(length=100)
        return [
            Channel(
                channel_id=doc["channel_id"],
                title=doc["title"],
                username=doc.get("username"),
                owner_id=doc.get("owner_id", 0),
                authorized_users=doc.get("authorized_users", [doc.get("owner_id", 0)]),
                added_at=doc.get("added_at"),
            )
            for doc in docs
        ]

    async def remove_channel(self, channel_id: str, user_id: int) -> bool:
        ch = await self.get_by_id(channel_id)
        if not ch:
            return False
        # If user is the primary owner, delete the channel
        if ch.owner_id == user_id:
            res = await self.db.channels.delete_one({"channel_id": channel_id})
            return res.deleted_count > 0
        else:
            # If user is an invited poster, just remove them from authorized_users
            return await self.remove_authorized_user(channel_id, user_id)
