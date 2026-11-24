"""
Tests for styled inline buttons, URL validation, and Unicode transformations.
Matches Pages 4-5 of DX-Notes.
"""
import pytest
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from src.bot.keyboards.post_buttons import build_post_inline_keyboard, build_post_reply_keyboard
from src.bot.utils.validation import is_valid_url
from src.bot.utils.formatting import (
    apply_unicode_style,
    render_text_table,
    parse_button_input,
    parse_keyboard_input,
    extract_formatted_text,
    sanitize_telegram_html,
    build_rich_table_block,
    build_rich_message_payload,
    parse_table_input,
)
from datetime import datetime, timezone
from telegram import Message, MessageEntity

def test_url_validation():
    """Verify safe and valid URL detection."""
    assert is_valid_url("https://t.me/example_channel") is True
    assert is_valid_url("http://example.com/posts") is True
    assert is_valid_url("tg://resolve?domain=mychannel") is True

    # Invalid / dangerous URLs
    assert is_valid_url("javascript:alert(1)") is False
    assert is_valid_url("") is False
    assert is_valid_url("not a url") is False
    assert is_valid_url(None) is False

def test_styled_inline_buttons_generation():
    """
    Verify creation of styled colored buttons (primary, success, danger)
    matching the code snippet from Page 5 of DX-Notes.
    """
    buttons_data = [
        {
            "text": "Main group ❤️",
            "url": "https://t.me/example_group",
            "style": "danger",
            "row": 0,
        },
        {
            "text": "Developer channel",
            "url": "https://t.me/example_channel",
            "style": "success",
            "row": 1,
        },
        {
            "text": "More posts",
            "url": "https://t.me/example_channel",
            "style": "primary",
            "row": 1,
        },
    ]

    markup = build_post_inline_keyboard(buttons_data)
    assert isinstance(markup, InlineKeyboardMarkup)
    assert len(markup.inline_keyboard) == 2  # 2 rows

    # Row 0: 1 button with danger style
    row_0 = markup.inline_keyboard[0]
    assert len(row_0) == 1
    assert row_0[0].text == "Main group ❤️"
    assert row_0[0].url == "https://t.me/example_group"
    assert getattr(row_0[0], "style", None) == "danger"

    # Row 1: 2 buttons with success and primary styles
    row_1 = markup.inline_keyboard[1]
    assert len(row_1) == 2
    assert row_1[0].text == "Developer channel"
    assert getattr(row_1[0], "style", None) == "success"
    assert row_1[1].text == "More posts"
    assert getattr(row_1[1], "style", None) == "primary"

def test_parse_button_input():
    """Test parsing user text into button models with rows and styles."""
    user_input = (
        "Join Group - https://t.me/group danger\n"
        "Official Site - https://example.com primary | Docs - https://docs.example.com success"
    )
    parsed = parse_button_input(user_input)
    assert len(parsed) == 3

    assert parsed[0]["text"] == "Join Group"
    assert parsed[0]["url"] == "https://t.me/group"
    assert parsed[0]["style"] == "danger"
    assert parsed[0]["row"] == 0

    assert parsed[1]["text"] == "Official Site"
    assert parsed[1]["row"] == 1
    assert parsed[1]["style"] == "primary"

    assert parsed[2]["text"] == "Docs"
    assert parsed[2]["row"] == 1
    assert parsed[2]["style"] == "success"

def test_unicode_text_transformation():
    """Verify decorative Unicode bold and italic styling."""
    plain = "Hello World"
    styled_bold = apply_unicode_style(plain, style="bold")
    assert styled_bold != plain
    assert len(styled_bold) == len(plain)

    styled_italic = apply_unicode_style(plain, style="italic")
    assert styled_italic != plain

def test_text_table_rendering():
    """Verify monospace aligned table construction."""
    headers = ["Item", "Price"]
    rows = [["Apple", "$1.00"], ["Banana", "$0.50"]]
    table_str = render_text_table(headers, rows)

    assert "<pre>" in table_str
    assert "</pre>" in table_str
    assert "Apple" in table_str
    assert "Banana" in table_str
    assert "Price" in table_str

def test_extract_formatted_text_auto_detection():
    """Verify automatic detection and conversion of Telegram visual formatting."""
    # 1. Message with Bold entity from Telegram mobile/desktop formatting popup
    e_bold = MessageEntity(type=MessageEntity.BOLD, offset=6, length=5)
    msg = Message(
        message_id=1,
        date=datetime.now(timezone.utc),
        chat=None,
        text="Hello world",
        entities=[e_bold],
    )
    result = extract_formatted_text(msg)
    assert result == "Hello <b>world</b>"

    # 2. Caption with Italic entity on photo
    e_italic = MessageEntity(type=MessageEntity.ITALIC, offset=0, length=5)
    caption_msg = Message(
        message_id=2,
        date=datetime.now(timezone.utc),
        chat=None,
        caption="Photo caption",
        caption_entities=[e_italic],
    )
    caption_result = extract_formatted_text(caption_msg)
    assert "<i>Photo</i>" in caption_result

    # 3. Visual Expandable Blockquote entity
    e_exp = MessageEntity(type=MessageEntity.EXPANDABLE_BLOCKQUOTE, offset=0, length=9)
    exp_msg = Message(
        message_id=3,
        date=datetime.now(timezone.utc),
        chat=None,
        text="Quote txt",
        entities=[e_exp],
    )
    assert "<blockquote expandable>Quote txt</blockquote>" in extract_formatted_text(exp_msg)

    # 4. Raw Typed HTML Blockquote (without entities)
    raw_msg = Message(
        message_id=4,
        date=datetime.now(timezone.utc),
        chat=None,
        text="<blockquote expandable>Raw Typed</blockquote>",
        entities=[],
    )
    assert "<blockquote expandable>Raw Typed</blockquote>" in extract_formatted_text(raw_msg)

def test_unicode_small_caps_and_tag_protection():
    """Verify small caps style and ensure HTML tags remain intact."""
    plain = "Hello World"
    styled_sc = apply_unicode_style(plain, style="smallcaps")
    assert "ʜᴇʟʟᴏ" in styled_sc or "ᴡᴏʀʟᴅ" in styled_sc

    # Crucial test: Ensure HTML tags are NOT corrupted into invalid tags like <𝑚𝑜𝑏>
    html_text = "<b>bold text</b> and <a href=\"https://t.me\">link</a>"
    styled_html = apply_unicode_style(html_text, style="italic")
    assert "<b>" in styled_html
    assert "</b>" in styled_html
    assert "<a href=\"https://t.me\">" in styled_html
    assert "</a>" in styled_html

def test_sanitize_telegram_html():
    """Verify invalid tags are stripped while valid Telegram tags remain."""
    corrupted = "Valid <b>text</b> and <mob>invalid tag</mob>"
    sanitized = sanitize_telegram_html(corrupted)
    assert "<b>text</b>" in sanitized
    assert "<mob>" not in sanitized
    assert "</mob>" not in sanitized

def test_rich_table_block_and_payload_generation():
    """Verify Bot API 10.1 RichBlockTable schema generation."""
    headers = ["Col A", "Col B"]
    rows = [["Val 1", "Val 2"], ["Val 3", "Val 4"]]
    table_block = build_rich_table_block(headers, rows, is_bordered=True, is_striped=True, align="center")

    assert table_block["type"] == "table"
    assert table_block["is_bordered"] is True
    assert table_block["is_striped"] is True
    assert len(table_block["cells"]) == 3  # 1 header row + 2 data rows

    # Header cell checks
    assert table_block["cells"][0][0]["is_header"] is True
    assert table_block["cells"][0][0]["text"] == "Col A"
    assert table_block["cells"][0][0]["align"] == "center"

    # Data cell checks
    assert table_block["cells"][1][0].get("is_header") is not True
    assert table_block["cells"][1][0]["text"] == "Val 1"

    # Test full message payload assembly
    payload = build_rich_message_payload(
        text="Hello table test",
        table_data={"headers": headers, "rows": rows, "is_bordered": True, "is_striped": True, "align": "center"}
    )
    assert "blocks" in payload
    assert len(payload["blocks"]) == 2
    assert payload["blocks"][0]["type"] == "paragraph"
    assert payload["blocks"][0]["text"] == "Hello table test"
    assert payload["blocks"][1]["type"] == "table"

def test_parse_table_input():
    """Verify parsing user pipe-separated text into structured table data."""
    raw = "Col 1 | Col 2\nVal 1 | Val 2\nVal 3 | Val 4"
    parsed = parse_table_input(raw)
    assert parsed is not None
    assert parsed["headers"] == ["Col 1", "Col 2"]
    assert len(parsed["rows"]) == 2
    assert parsed["rows"][0] == ["Val 1", "Val 2"]
    assert parsed["rows"][1] == ["Val 3", "Val 4"]

def test_parse_keyboard_input_and_reply_keyboard():
    """Verify parsing reply keyboard buttons and constructing ReplyKeyboardMarkup."""
    raw = "Option 1 | Option 2\nHelp | Support"
    parsed = parse_keyboard_input(raw)
    assert len(parsed) == 4
    assert parsed[0]["text"] == "Option 1"
    assert parsed[0]["row"] == 0
    assert parsed[1]["text"] == "Option 2"
    assert parsed[1]["row"] == 0
    assert parsed[2]["text"] == "Help"
    assert parsed[2]["row"] == 1
    assert parsed[3]["text"] == "Support"
    assert parsed[3]["row"] == 1

    reply_kb = build_post_reply_keyboard(parsed)
    assert len(reply_kb.keyboard) == 2
    assert len(reply_kb.keyboard[0]) == 2
    assert reply_kb.keyboard[0][0].text == "Option 1"
    assert reply_kb.keyboard[1][1].text == "Support"

def test_render_inbody_buttons_html():
    """Verify native Bot API 10.3 in-body row button rendering."""
    from src.bot.utils.formatting import render_inbody_buttons_html
    buttons = [
        {"text": "Official Site", "url": "https://example.com", "style": "primary", "row": 0},
        {"text": "Join Telegram", "url": "https://t.me/channel", "style": "success", "row": 0},
        {"text": "Alert / Rules", "url": "https://t.me/rules", "style": "danger", "row": 1},
    ]
    html_output = render_inbody_buttons_html(buttons)
    assert "<tg-button-row>" in html_output
    assert '<tg-button url="https://example.com" style="primary">Official Site</tg-button>' in html_output
    assert '<tg-button url="https://t.me/channel" style="success">Join Telegram</tg-button>' in html_output
    assert '<tg-button url="https://t.me/rules" style="danger">Alert / Rules</tg-button>' in html_output
    assert "</tg-button-row>" in html_output

def test_expandable_blockquote_entity_parsing():
    """Verify parse_html_to_entities distinguishes between blockquote and expandable_blockquote."""
    from src.bot.utils.formatting import parse_html_to_entities

    html_code = "<b>Header</b>\n<blockquote expandable>Expandable quote content</blockquote>\n<blockquote>Standard quote</blockquote>"
    text, entities = parse_html_to_entities(html_code)

    assert "Header" in text
    assert "Expandable quote content" in text
    assert "Standard quote" in text

    exp_entities = [e for e in entities if e["type"] == "expandable_blockquote"]
    std_entities = [e for e in entities if e["type"] == "blockquote"]

    assert len(exp_entities) == 1
    assert len(std_entities) == 1
    assert exp_entities[0]["length"] == len("Expandable quote content")
    assert std_entities[0]["length"] == len("Standard quote")

def test_wrap_and_remove_text_blockquote():
    """Verify wrap_text_blockquote and remove_text_blockquote helpers."""
    from src.bot.utils.formatting import wrap_text_blockquote, remove_text_blockquote

    base_text = "Important channel announcement"
    # 1. Standard quote
    q1 = wrap_text_blockquote(base_text, expandable=False)
    assert q1.startswith("<blockquote>")
    assert q1.endswith("</blockquote>")
    assert base_text in q1

    # 2. Expandable quote with cite
    q2 = wrap_text_blockquote(base_text, expandable=True, cite="Admin")
    assert "<blockquote expandable" in q2
    assert 'cite="Admin"' in q2

    # 3. Remove quote
    unquoted = remove_text_blockquote(q2)
    assert unquoted == base_text
    assert "<blockquote" not in unquoted

def test_nested_media_and_table_in_expandable_blockquote():
    """Verify Bot API 10.5: expandable quote blocks can contain nested media and tables."""
    from src.bot.utils.formatting import build_rich_message_payload

    text = "Intro\n<blockquote expandable cite='Source'>\nCheck the photo:\n{media}\nAnd the stats:\n{table}\n</blockquote>\nOutro"
    media_list = [{"file_id": "photo_nested_999", "media_type": "photo"}]
    table_data = {"headers": ["A", "B"], "rows": [["1", "2"]]}

    payload = build_rich_message_payload(text=text, table_data=table_data, media_list=media_list)
    blocks = payload["blocks"]

    # Block 0: Intro paragraph
    assert blocks[0]["type"] == "paragraph"
    assert "Intro" in blocks[0]["text"]

    # Block 1: Expandable blockquote block
    assert blocks[1]["type"] == "expandable_blockquote"
    assert blocks[1]["credit"] == "Source"

    inner_blocks = blocks[1]["blocks"]
    assert any(b["type"] == "photo" and b["photo"]["media"] == "photo_nested_999" for b in inner_blocks)
    assert any(b["type"] == "table" for b in inner_blocks)

    # Block 2: Outro paragraph
    assert blocks[2]["type"] == "paragraph"
    assert "Outro" in blocks[2]["text"]
