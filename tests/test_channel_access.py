import pytest
from unittest.mock import AsyncMock, MagicMock
from copy import deepcopy

from src.bot.services.channel_access import verify_user_is_full_admin_or_owner
from src.bot.database.repositories.channels import ChannelRepository

@pytest.mark.asyncio
async def test_verify_user_is_creator():
    """Verify channel creator passes authorization with is_creator=True."""
    bot = MagicMock()
    member = MagicMock()
    member.status = "creator"
    bot.get_chat_member = AsyncMock(return_value=member)

    authorized, reason, is_creator = await verify_user_is_full_admin_or_owner(bot, "-1001234567890", 111)
    assert authorized is True
    assert is_creator is True
    assert reason == "OK"

@pytest.mark.asyncio
async def test_verify_user_is_full_power_admin():
    """Verify administrator with can_promote_members passes authorization."""
    bot = MagicMock()
    member = MagicMock()
    member.status = "administrator"
    member.can_promote_members = True
    bot.get_chat_member = AsyncMock(return_value=member)

    authorized, reason, is_creator = await verify_user_is_full_admin_or_owner(bot, "-1001234567890", 222)
    assert authorized is True
    assert is_creator is False
    assert reason == "OK"

@pytest.mark.asyncio
async def test_verify_user_admin_without_promote_power_rejected():
    """Verify administrator without can_promote_members is rejected."""
    bot = MagicMock()
    member = MagicMock()
    member.status = "administrator"
    member.can_promote_members = False
    bot.get_chat_member = AsyncMock(return_value=member)

    authorized, reason, is_creator = await verify_user_is_full_admin_or_owner(bot, "-1001234567890", 333)
    assert authorized is False
    assert is_creator is False
    assert "Add New Admins" in reason

@pytest.mark.asyncio
async def test_verify_regular_member_rejected():
    """Verify non-admin member is rejected."""
    bot = MagicMock()
    member = MagicMock()
    member.status = "member"
    bot.get_chat_member = AsyncMock(return_value=member)

    authorized, reason, is_creator = await verify_user_is_full_admin_or_owner(bot, "-1001234567890", 444)
    assert authorized is False
    assert is_creator is False

class MockChannelCollection:
    def __init__(self):
        self.channels = {}

    async def update_one(self, filter_doc, update_doc, upsert=False):
        c_id = filter_doc.get("channel_id")
        doc = self.channels.setdefault(c_id, {"channel_id": c_id, "authorized_users": []})
        if "$set" in update_doc:
            doc.update(update_doc["$set"])
        if "$addToSet" in update_doc:
            for k, v in update_doc["$addToSet"].items():
                lst = doc.setdefault(k, [])
                if v not in lst:
                    lst.append(v)
        return MagicMock(modified_count=1, matched_count=1)

    async def find_one(self, filter_doc):
        c_id = filter_doc.get("channel_id")
        return deepcopy(self.channels.get(c_id))

    def find(self, filter_doc):
        # Handle $or query for owner_id or authorized_users
        matched = []
        user_id = None
        if "$or" in filter_doc:
            for condition in filter_doc["$or"]:
                if "owner_id" in condition:
                    user_id = condition["owner_id"]
                elif "authorized_users" in condition:
                    user_id = condition["authorized_users"]

        for d in self.channels.values():
            if user_id:
                if d.get("owner_id") == user_id or user_id in d.get("authorized_users", []):
                    matched.append(deepcopy(d))

        cursor = MagicMock()
        cursor.sort.return_value = cursor
        cursor.to_list = AsyncMock(return_value=matched)
        return cursor

@pytest.mark.asyncio
async def test_channel_repository_multi_admin_persistence():
    """Verify that multiple admins can be authorized and channel does not disappear."""
    mock_db = MagicMock()
    mock_db.channels = MockChannelCollection()
    repo = ChannelRepository(mock_db)

    # Owner (User 100) adds channel
    ch = await repo.add_channel("-1009999", "Tech News", "technews", owner_id=100)
    assert ch.owner_id == 100
    assert 100 in ch.authorized_users

    # Verify Owner sees the channel
    owner_channels = await repo.get_user_channels(100)
    assert len(owner_channels) == 1
    assert owner_channels[0].channel_id == "-1009999"

    # Owner invites Admin (User 200)
    await repo.add_authorized_user("-1009999", 200)

    # Verify BOTH Owner and Invited Admin see the channel
    owner_channels = await repo.get_user_channels(100)
    assert len(owner_channels) == 1

    admin_channels = await repo.get_user_channels(200)
    assert len(admin_channels) == 1
    assert admin_channels[0].title == "Tech News"

    # Unrelated User 300 should NOT see the channel
    unrelated_channels = await repo.get_user_channels(300)
    assert len(unrelated_channels) == 0
