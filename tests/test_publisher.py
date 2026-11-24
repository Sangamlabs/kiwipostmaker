"""
Tests for Telegram post publisher worker.
Verifies single message, single photo, and multi-media albums with attached reply markup.
Matches Pages 2, 5, 6, 7 of DX-Notes.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from telegram.error import TelegramError

from src.bot.models.post import Post
from src.bot.services.publisher import publish_post

@pytest.mark.asyncio
async def test_publish_text_only():
    """Verify text message publishing with HTML parse mode and markup."""
    bot = MagicMock()
    mock_sent_msg = MagicMock()
    mock_sent_msg.message_id = 101
    bot.send_message = AsyncMock(return_value=mock_sent_msg)

    post = Post(
        id=1,
        owner_user_id=123,
        channel_id="-1001234567890",
        text="<b>Breaking News:</b> Telegram Postbot deployed!",
        media_json="[]",
        buttons_json='[{"text": "Read More", "url": "https://t.me/news", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [101]
    assert error == ""

    bot.send_message.assert_awaited_once()
    _, kwargs = bot.send_message.call_args
    assert kwargs["chat_id"] == "-1001234567890"
    assert "Breaking News" in kwargs["text"]
    assert kwargs["reply_markup"] is not None

@pytest.mark.asyncio
async def test_publish_single_photo():
    """Verify single photo publishing with caption and keyboard."""
    bot = MagicMock()
    mock_photo_msg = MagicMock()
    mock_photo_msg.message_id = 202
    bot.send_photo = AsyncMock(return_value=mock_photo_msg)

    post = Post(
        id=2,
        owner_user_id=123,
        channel_id="-1001234567890",
        text="Photo caption",
        media_json='[{"file_id": "file_photo_123", "media_type": "photo"}]',
        buttons_json='[{"text": "Visit", "url": "https://t.me/channel", "style": "primary", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [202]

    bot.send_photo.assert_awaited_once()
    _, kwargs = bot.send_photo.call_args
    assert kwargs["photo"] == "file_photo_123"
    assert kwargs["caption"] == "Photo caption"

@pytest.mark.asyncio
async def test_publish_album_with_attached_markup():
    """
    Verify album publishing:
    1. send_media_group called with 2-10 items
    2. edit_message_reply_markup called on the first message ID to attach keyboard
    Matches Pages 6-7 of DX-Notes.
    """
    bot = MagicMock()
    msg1 = MagicMock()
    msg1.message_id = 301
    msg2 = MagicMock()
    msg2.message_id = 302

    bot.send_media_group = AsyncMock(return_value=[msg1, msg2])
    bot.edit_message_reply_markup = AsyncMock()

    post = Post(
        id=3,
        owner_user_id=123,
        channel_id="-1001234567890",
        text="Album caption",
        media_json='[{"file_id": "photo_1", "media_type": "photo"}, {"file_id": "photo_2", "media_type": "photo"}]',
        buttons_json='[{"text": "Open Link", "url": "https://t.me/channel", "style": "success", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [301, 302]

    # Verify send_media_group called
    bot.send_media_group.assert_awaited_once()

    # Verify edit_message_reply_markup called on msg1
    bot.edit_message_reply_markup.assert_awaited_once()
    _, edit_kwargs = bot.edit_message_reply_markup.call_args
    assert edit_kwargs["chat_id"] == "-1001234567890"
    assert edit_kwargs["message_id"] == 301
    assert edit_kwargs["reply_markup"] is not None

@pytest.mark.asyncio
async def test_publish_sticker():
    """Verify single sticker publishing."""
    bot = MagicMock()
    mock_sticker_msg = MagicMock()
    mock_sticker_msg.message_id = 707
    bot.send_sticker = AsyncMock(return_value=mock_sticker_msg)

    post = Post(
        id=5,
        owner_user_id=123,
        channel_id="-1001234567890",
        media_json='[{"file_id": "sticker_file_id_xyz", "media_type": "sticker"}]',
        buttons_json='[{"text": "Channel", "url": "https://t.me/example", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [707]
    bot.send_sticker.assert_awaited_once()
    _, kwargs = bot.send_sticker.call_args
    assert kwargs["sticker"] == "sticker_file_id_xyz"

@pytest.mark.asyncio
async def test_publish_failure_handling():
    """Verify error catching when Telegram API returns an error."""
    bot = MagicMock()
    bot.send_message = AsyncMock(side_effect=TelegramError("Chat not found"))

    post = Post(
        id=4,
        owner_user_id=123,
        channel_id="-1009999999999",
        text="Sample post",
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is False
    assert msg_ids == []
    assert "Chat not found" in error

@pytest.mark.asyncio
async def test_publish_rich_table_via_send_rich_message():
    """Verify publishing post with native Bot API 10.1 rich table."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 999})

    post = Post(
        id=6,
        owner_user_id=123,
        channel_id="-1001234567890",
        text="Here is the table:",
        table_json='{"headers": ["Item", "Price"], "rows": [["Widget", "$10"]], "is_bordered": true, "is_striped": true, "align": "center"}',
        buttons_json='[{"text": "Visit", "url": "https://example.com", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [999]
    bot._post.assert_awaited_once()
    endpoint, call_kwargs = bot._post.call_args
    assert endpoint == "sendRichMessage" or call_kwargs.get("endpoint") == "sendRichMessage" or bot._post.call_args[0][0] == "sendRichMessage"
    data = call_kwargs.get("data", {})
    assert data["chat_id"] == "-1001234567890"
    assert "rich_message" in data
    assert data["rich_message"]["blocks"][1]["type"] == "table"
    assert "reply_markup" in data

@pytest.mark.asyncio
async def test_publish_article_post_with_media_and_inline_keyboard():
    """Verify publishing an Article post with photo, rich table, and inline buttons."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 1002})

    post = Post(
        id=7,
        owner_user_id=123,
        channel_id="-1001234567890",
        post_type="article",
        button_type="inline",
        media_position="top",
        text="<b>Market Overview 2026</b>\n\n<blockquote>Growth reported.</blockquote>",
        media_json='[{"file_id": "photo_asset_123", "media_type": "photo"}]',
        table_json='{"headers": ["Metric", "Value"], "rows": [["Growth", "+15%"]], "is_bordered": true, "is_striped": true, "align": "center"}',
        buttons_json='[{"text": "Refresh", "url": "https://t.me", "row": 0}, {"text": "Details", "url": "https://t.me", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [1002]
    bot._post.assert_awaited_once()

    endpoint = bot._post.call_args[0][0]
    assert endpoint == "sendRichMessage"
    call_data = bot._post.call_args[1].get("data") or bot._post.call_args[0][1]
    assert call_data["chat_id"] == "-1001234567890"

    blocks = call_data["rich_message"]["blocks"]
    assert blocks[0]["type"] == "photo"
    assert blocks[0]["photo"]["media"] == "photo_asset_123"
    assert blocks[1]["type"] == "paragraph"
    assert "Market Overview" in blocks[1]["text"]
    assert any(b["type"] == "blockquote" and "Growth reported." in b["blocks"][0]["text"] for b in blocks)
    assert any(b["type"] == "table" for b in blocks)

    assert "reply_markup" in call_data
    assert "inline_keyboard" in call_data["reply_markup"]

@pytest.mark.asyncio
async def test_publish_article_post_with_middle_media_position():
    """Verify publishing an Article post with media interleaved in the middle of text."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 1004})

    post = Post(
        id=9,
        owner_user_id=123,
        channel_id="-1001234567890",
        post_type="article",
        button_type="inline",
        media_position="middle",
        text="Paragraph One\n\nParagraph Two",
        media_json='[{"file_id": "photo_mid_123", "media_type": "photo"}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [1004]

    call_data = bot._post.call_args[1].get("data") or bot._post.call_args[0][1]
    blocks = call_data["rich_message"]["blocks"]
    assert len(blocks) == 3
    assert blocks[0]["type"] == "paragraph"
    assert blocks[0]["text"] == "Paragraph One"
    assert blocks[1]["type"] == "photo"
    assert blocks[1]["photo"]["media"] == "photo_mid_123"
    assert blocks[2]["type"] == "paragraph"
    assert blocks[2]["text"] == "Paragraph Two"

@pytest.mark.asyncio
async def test_publish_article_post_with_inbody_row_buttons():
    """Verify publishing an Article post with native Bot API 10.3 in-body row buttons."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 1003})

    post = Post(
        id=8,
        owner_user_id=123,
        channel_id="-1001234567890",
        post_type="article",
        button_type="row",
        text="<b>Headline</b>\n\n<blockquote>Notice content</blockquote>",
        buttons_json='[{"text": "Read More", "url": "https://example.com", "style": "primary", "row": 0}, {"text": "Support", "url": "https://t.me/support", "style": "success", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [1003]
    bot._post.assert_awaited_once()

    call_data = bot._post.call_args[1].get("data") or bot._post.call_args[0][1]
    blocks = call_data["rich_message"]["blocks"]
    assert blocks[0]["type"] == "paragraph"
    assert "Headline" in blocks[0]["text"]
    assert any(e["type"] == "bold" for e in blocks[0].get("entities", []))
    assert blocks[1]["type"] == "blockquote"
    assert "Notice content" in blocks[1]["blocks"][0]["text"]
    assert blocks[2]["type"] == "buttons"
    assert blocks[2]["buttons"][0]["text"] == "Read More"
    assert blocks[2]["buttons"][0]["style"] == "primary"
    assert blocks[2]["buttons"][1]["text"] == "Support"
    assert blocks[2]["buttons"][1]["style"] == "success"

@pytest.mark.asyncio
async def test_publish_article_post_with_nested_expandable_blockquote():
    """Verify publishing article with Bot API 10.5 expandable quote containing nested photo."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 1005})

    post = Post(
        id=10,
        owner_user_id=123,
        channel_id="-1001234567890",
        post_type="article",
        button_type="row",
        text="Top intro\n<blockquote expandable cite='Team'>\nDetails:\n{media}\n</blockquote>",
        media_json='[{"file_id": "nested_file_1", "media_type": "photo"}]',
        buttons_json='[{"text": "Visit", "url": "https://example.com", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [1005]

    call_data = bot._post.call_args[1].get("data") or bot._post.call_args[0][1]
    blocks = call_data["rich_message"]["blocks"]

    # Block 0: Top intro
    assert blocks[0]["type"] == "paragraph"
    assert "Top intro" in blocks[0]["text"]

    # Block 1: Expandable blockquote
    assert blocks[1]["type"] == "expandable_blockquote"
    assert blocks[1]["credit"] == "Team"
    assert any(b["type"] == "photo" and b["photo"]["media"] == "nested_file_1" for b in blocks[1]["blocks"])

    # Block 2: In-body buttons
    assert blocks[2]["type"] == "buttons"
    assert blocks[2]["buttons"][0]["text"] == "Visit"

@pytest.mark.asyncio
async def test_publish_post_with_both_inline_and_row_buttons():
    """Verify that a post can have BOTH in-body row buttons AND traditional inline buttons."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 1006})

    post = Post(
        id=11,
        owner_user_id=123,
        channel_id="-1001234567890",
        post_type="standard",
        text="Post with both button types",
        inline_buttons_json='[{"text": "Inline Link", "url": "https://example.com/inline", "row": 0}]',
        row_buttons_json='[{"text": "Row Button", "url": "https://example.com/row", "style": "primary", "row": 0}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [1006]

    call_data = bot._post.call_args[1].get("data") or bot._post.call_args[0][1]
    # Check in-body row buttons inside rich message blocks
    blocks = call_data["rich_message"]["blocks"]
    assert any(b["type"] == "buttons" and b["buttons"][0]["text"] == "Row Button" for b in blocks)

    # Check inline keyboard inside reply_markup
    assert "reply_markup" in call_data
    assert "inline_keyboard" in call_data["reply_markup"]
    assert call_data["reply_markup"]["inline_keyboard"][0][0]["text"] == "Inline Link"

@pytest.mark.asyncio
async def test_publish_article_post_with_slideshow():
    """Verify that multiple photos in an article post render as a native slideshow block (carousel)."""
    bot = MagicMock()
    bot._post = AsyncMock(return_value={"message_id": 1007})

    post = Post(
        id=12,
        owner_user_id=123,
        channel_id="-1001234567890",
        post_type="article",
        text="Article with multi-image carousel",
        media_json='[{"file_id": "photo_1", "media_type": "photo"}, {"file_id": "photo_2", "media_type": "photo"}]',
    )

    success, msg_ids, error = await publish_post(bot, post)
    assert success is True
    assert msg_ids == [1007]

    call_data = bot._post.call_args[1].get("data") or bot._post.call_args[0][1]
    blocks = call_data["rich_message"]["blocks"]
    assert blocks[0]["type"] == "slideshow"
    assert len(blocks[0]["blocks"]) == 2
    assert blocks[0]["blocks"][0]["photo"]["media"] == "photo_1"
    assert blocks[0]["blocks"][1]["photo"]["media"] == "photo_2"
