"""
MongoDB async database connection and lifecycle using Motor.
"""
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
import pymongo

logger = logging.getLogger(__name__)

class DatabaseConnection:
    """Manages MongoDB connection and collection initialization."""

    def __init__(self, mongo_uri: str, db_name: str):
        self.mongo_uri = mongo_uri
        self.db_name = db_name
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None

    def get_database(self) -> AsyncIOMotorDatabase:
        """Returns the Motor database instance."""
        if self.client is None:
            self.client = AsyncIOMotorClient(
                self.mongo_uri,
                serverSelectionTimeoutMS=3000,
            )
            self.db = self.client[self.db_name]
        return self.db

    async def init_indexes(self) -> None:
        """Connects to MongoDB and ensures indexes exist."""
        if self.db is None:
            self.get_database()
        try:
            # Test connectivity with ping
            await self.client.admin.command("ping")
            logger.info("Successfully connected to MongoDB database: %s", self.db_name)

            # Posts indexes
            await self.db.posts.create_index([("id", pymongo.ASCENDING)], unique=True)
            await self.db.posts.create_index([("owner_user_id", pymongo.ASCENDING)])
            await self.db.posts.create_index([("status", pymongo.ASCENDING), ("scheduled_at", pymongo.ASCENDING)])

            # Channels indexes
            await self.db.channels.create_index([("channel_id", pymongo.ASCENDING)], unique=True)
            await self.db.channels.create_index([("owner_id", pymongo.ASCENDING)])

            # Media indexes
            await self.db.media.create_index([("post_id", pymongo.ASCENDING)])
            logger.info("MongoDB indexes verified.")
        except Exception as exc:
            logger.warning(
                "MongoDB is currently offline or unreachable at %s (%s). "
                "The bot will continue running, but active database features require a running MongoDB instance.",
                self.mongo_uri,
                exc,
            )

    async def close(self) -> None:
        if self.client:
            self.client.close()
            logger.info("MongoDB client closed.")
