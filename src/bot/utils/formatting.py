import html
from html.parser import HTMLParser
import re
from typing import Any, Dict, List, Optional, Tuple
from .validation import is_valid_url

# Telegram supported HTML tags
VALID_TELEGRAM_TAGS = {
    "b", "strong", "i", "em", "u", "ins", "s", "strike", "del",
    "span", "tg-spoiler", "a", "code", "pre", "blockquote", "tg-blockquote",
    "tg-button-row", "tg-button", "tg-emoji"
}

# Unicode transformations for decorative styling (Page 3 & 6 of DX-Notes)
UNICODE_BOLD_MAP = {
    c: chr(ord(c) + 0x1D3F0 if 'A' <= c <= 'Z' else ord(c) + 0x1D3EA)
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
}
UNICODE_ITALIC_MAP = {
    c: chr(ord(c) + 0x1D424 if 'A' <= c <= 'Z' else ord(c) + 0x1D41E)
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
}
UNICODE_MONO_MAP = {
    c: chr(ord(c) + 0x1D638 if 'A' <= c <= 'Z' else ord(c) + 0x1D632)
    for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
}
UNICODE_SMALL_CAPS_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ',
    'g': 'ɢ', 'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ',
    'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ',
    's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
    'A': 'ᴀ', 'B': 'ʙ', 'C': 'ᴄ', 'D': 'ᴅ', 'E': 'ᴇ', 'F': 'ꜰ',
    'G': 'ɢ', 'H': 'ʜ', 'I': 'ɪ', 'J': 'ᴊ', 'K': 'ᴋ', 'L': 'ʟ',
    'M': 'ᴍ', 'N': 'ɴ', 'O': 'ᴏ', 'P': 'ᴘ', 'Q': 'ǫ', 'R': 'ʀ',
    'S': 'ꜱ', 'T': 'ᴛ', 'U': 'ᴜ', 'V': 'ᴠ', 'W': 'ᴡ', 'X': 'x',
    'Y': 'ʏ', 'Z': 'ᴢ',
}

def sanitize_telegram_html(text: str) -> str:
    """
    Strips unsupported HTML tags so Telegram never throws 'Can't parse entities: unsupported start tag'.
    Preserves valid tags like <b>, <i>, <u>, <a>, <tg-spoiler>, <pre>, <code>.
    """
    if not text:
        return ""

    def tag_filter(match: re.Match) -> str:
        full_tag = match.group(0)
        tag_name = match.group(1).lower()
        if tag_name in VALID_TELEGRAM_TAGS:
            return full_tag
        return ""

    # Match <tag...> or </tag>
    return re.sub(r'</?([a-zA-Z0-9_\-]+)[^>]*>', tag_filter, text)

def apply_unicode_style(text: str, style: str) -> str:
    """
    Apply decorative Unicode transformation to alphanumeric text.
    Crucially protects HTML tags (<...>) and HTML entities (&...;) from corruption.
    Supports 'bold', 'italic', 'mono', and 'smallcaps' / 'small_caps'.
    """
    if not text:
        return ""

    if style == "bold":
        char_map = UNICODE_BOLD_MAP
    elif style == "italic":
        char_map = UNICODE_ITALIC_MAP
    elif style == "mono":
        char_map = UNICODE_MONO_MAP
    elif style in {"smallcaps", "small_caps"}:
        char_map = UNICODE_SMALL_CAPS_MAP
    else:
        return text

    # Split by HTML tags and entities so we only modify visible text
    parts = re.split(r"(<[^>]+>|&[a-zA-Z0-9#]+;)", text)
    result = []
    for part in parts:
        if (part.startswith("<") and part.endswith(">")) or (part.startswith("&") and part.endswith(";")):
            result.append(part)
        else:
            result.append("".join(char_map.get(c, c) for c in part))
    return "".join(result)

def extract_formatted_text(message: Any) -> str:
    """
    Extracts text while auto-detecting Telegram native visual formatting.
    Preserves formatting applied via Telegram's visual menu or raw HTML tags.
    """
    if not message:
        return ""

    if getattr(message, "text", None):
        raw = message.text
        has_html = any(f"<{t}" in raw.lower() for t in VALID_TELEGRAM_TAGS)
        if has_html:
            return sanitize_telegram_html(raw)
        return sanitize_telegram_html(message.text_html)

    elif getattr(message, "caption", None):
        raw = message.caption
        has_html = any(f"<{t}" in raw.lower() for t in VALID_TELEGRAM_TAGS)
        if has_html:
            return sanitize_telegram_html(raw)
        return sanitize_telegram_html(message.caption_html)

    return ""

def format_post_text(text: str, escape_html: bool = False) -> str:
    """Clean and optionally escape text while preserving user formatting."""
    if not text:
        return ""
    if escape_html:
        return html.escape(text)
    return text.strip()

def render_text_table(headers: List[str], rows: List[List[str]]) -> str:
    """Render aligned monospace text table for Telegram (legacy fallback)."""
    if not headers and not rows:
        return ""

    all_data = [headers] + rows if headers else rows
    col_widths = [0] * len(all_data[0])
    for row in all_data:
        for i, val in enumerate(row):
            if i < len(col_widths):
                col_widths[i] = max(col_widths[i], len(str(val)))

    lines = []
    if headers:
        header_str = " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(headers))
        lines.append(header_str)
        sep_str = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
        lines.append(sep_str)

    for row in rows:
        row_str = " | ".join(str(val).ljust(col_widths[i]) for i, val in enumerate(row))
        lines.append(row_str)

    return f"<pre>\n{chr(10).join(lines)}\n</pre>"

def build_rich_table_block(
    headers: List[str],
    rows: List[List[str]],
    is_bordered: bool = True,
    is_striped: bool = True,
    align: str = "left"
) -> Dict[str, Any]:
    """
    Constructs a native Telegram Bot API 10.1 RichBlockTable dictionary.
    Supports alignment, borders, striped styling, and header flags.
    """
    cells = []
    if headers:
        header_row = [
            {"text": str(h), "is_header": True, "align": align, "valign": "middle"}
            for h in headers
        ]
        cells.append(header_row)

    for row in rows:
        cells.append([
            {"text": str(cell), "align": align, "valign": "middle"}
            for cell in row
        ])

    return {
        "type": "table",
        "is_bordered": is_bordered,
        "is_striped": is_striped,
        "cells": cells,
    }

class TelegramHTMLToEntities(HTMLParser):
    """Parses standard Telegram HTML tags into plain text with UTF-16 offset MessageEntity dicts."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self.utf16_length = 0
        self.tag_stack = []
        self.entities = []

    def handle_data(self, data: str):
        self.text_parts.append(data)
        # Telegram entities require UTF-16 code units for offset and length
        utf16_len = len(data.encode("utf-16-le")) // 2
        self.utf16_length += utf16_len

    def handle_starttag(self, tag: str, attrs: list):
        attr_dict = dict(attrs)
        self.tag_stack.append((tag.lower(), self.utf16_length, attr_dict))

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        for i in range(len(self.tag_stack) - 1, -1, -1):
            if self.tag_stack[i][0] == tag:
                start_tag, start_offset, attr_dict = self.tag_stack.pop(i)
                length = self.utf16_length - start_offset
                if length > 0:
                    ent = {"offset": start_offset, "length": length}
                    if tag in {"b", "strong"}:
                        ent["type"] = "bold"
                    elif tag in {"i", "em"}:
                        ent["type"] = "italic"
                    elif tag in {"u", "ins"}:
                        ent["type"] = "underline"
                    elif tag in {"s", "strike", "del"}:
                        ent["type"] = "strikethrough"
                    elif tag in {"blockquote", "tg-blockquote"}:
                        if "expandable" in attr_dict:
                            ent["type"] = "expandable_blockquote"
                        else:
                            ent["type"] = "blockquote"
                    elif tag == "code":
                        ent["type"] = "code"
                    elif tag == "pre":
                        ent["type"] = "pre"
                    elif tag == "tg-spoiler":
                        ent["type"] = "spoiler"
                    elif tag == "a" and "href" in attr_dict:
                        ent["type"] = "text_link"
                        ent["url"] = attr_dict["href"]
                    else:
                        continue
                    self.entities.append(ent)
                break

    def get_result(self) -> Tuple[str, List[Dict[str, Any]]]:
        return "".join(self.text_parts), self.entities

def parse_html_to_entities(html_str: str) -> Tuple[str, List[Dict[str, Any]]]:
    """Parse HTML string into plain text and UTF-16 offset Telegram MessageEntity dictionaries."""
    if not html_str:
        return "", []
    parser = TelegramHTMLToEntities()
    parser.feed(html_str)
    return parser.get_result()

def make_paragraph_block(html_content: str) -> Optional[Dict[str, Any]]:
    """Helper to convert HTML formatted text into a valid native InputRichBlockParagraph."""
    clean = html_content.strip()
    if not clean:
        return None
    plain, entities = parse_html_to_entities(clean)
    if not plain:
        return None
    block: Dict[str, Any] = {"type": "paragraph", "text": plain}
    if entities:
        block["entities"] = entities
    return block

def wrap_text_blockquote(text: str, expandable: bool = False, cite: Optional[str] = None) -> str:
    """Wraps text in <blockquote> or <blockquote expandable>, removing previous blockquote wrappers."""
    if not text:
        return ""
    clean = re.sub(r'</?(?:blockquote|tg-blockquote)[^>]*>', '', text).strip()
    cite_attr = f' cite="{html.escape(cite)}"' if cite else ""
    if expandable:
        return f"<blockquote expandable{cite_attr}>\n{clean}\n</blockquote>"
    else:
        return f"<blockquote{cite_attr}>\n{clean}\n</blockquote>"

def remove_text_blockquote(text: str) -> str:
    """Removes blockquote tags from text."""
    if not text:
        return ""
    return re.sub(r'</?(?:blockquote|tg-blockquote)[^>]*>', '', text).strip()

def build_rich_message_payload(
    text: str,
    table_data: Optional[Dict[str, Any]] = None,
    media_list: Optional[List[Dict[str, Any]]] = None,
    in_body_buttons: Optional[List[Dict[str, Any]]] = None,
    media_position: str = "top",
) -> Dict[str, Any]:
    """
    Constructs an InputRichMessage payload with media blocks, paragraph blocks (with HTML parsing),
    native Bot API 10.1 / 10.5 table block, Bot API 10.5 expandable quote blocks (with nested blocks),
    and Bot API 10.3 in-body buttons.
    Supports media placement at 'top', 'middle', 'bottom', or via {media} placeholder.
    Supports nesting media or tables inside <blockquote expandable>...</blockquote>.
    """
    blocks = []

    media_block = None
    if media_list and len(media_list) > 0:
        if len(media_list) == 1:
            item = media_list[0]
            file_id = item.get("file_id")
            media_type = item.get("media_type", "photo")
            if file_id:
                if media_type == "video":
                    media_block = {
                        "type": "video",
                        "video": {"type": "video", "media": file_id}
                    }
                elif media_type == "sticker":
                    media_block = {
                        "type": "animation",
                        "animation": {"type": "animation", "media": file_id}
                    }
                else:
                    media_block = {
                        "type": "photo",
                        "photo": {"type": "photo", "media": file_id}
                    }
        else:
            # Telegram Bot API 10.1+ Native Slideshow block (Carousel with navigation arrows & dots)
            inner_blocks = []
            for item in media_list:
                fid = item.get("file_id")
                mtype = item.get("media_type", "photo")
                if fid:
                    if mtype == "video":
                        inner_blocks.append({
                            "type": "video",
                            "video": {"type": "video", "media": fid}
                        })
                    elif mtype == "sticker":
                        inner_blocks.append({
                            "type": "animation",
                            "animation": {"type": "animation", "media": fid}
                        })
                    else:
                        inner_blocks.append({
                            "type": "photo",
                            "photo": {"type": "photo", "media": fid}
                        })
            if inner_blocks:
                media_block = {
                    "type": "slideshow",
                    "blocks": inner_blocks
                }

    table_block = None
    if table_data:
        headers = table_data.get("headers", [])
        rows = table_data.get("rows", [])
        is_bordered = table_data.get("is_bordered", True)
        is_striped = table_data.get("is_striped", True)
        align = table_data.get("align", "left")
        table_block = build_rich_table_block(
            headers=headers,
            rows=rows,
            is_bordered=is_bordered,
            is_striped=is_striped,
            align=align
        )

    clean_text = text.strip() if text else ""
    clean_text = re.sub(r'<pre>.*?</pre>', '', clean_text, flags=re.DOTALL).strip()

    media_consumed = False
    table_consumed = False

    # Bot API 10.5: Parse all blockquotes into native rich blocks
    matches = list(re.finditer(r'<(blockquote|tg-blockquote)([^>]*)>(.*?)</\1>', clean_text, flags=re.DOTALL | re.IGNORECASE))
    if matches:
        last_idx = 0
        for m in matches:
            before_text = clean_text[last_idx:m.start()].strip()
            if before_text:
                if "{media}" in before_text and media_block and not media_consumed:
                    p1, p2 = before_text.split("{media}", 1)
                    b1 = make_paragraph_block(p1)
                    if b1: blocks.append(b1)
                    blocks.append(media_block)
                    media_consumed = True
                    b2 = make_paragraph_block(p2)
                    if b2: blocks.append(b2)
                elif "{table}" in before_text and table_block and not table_consumed:
                    p1, p2 = before_text.split("{table}", 1)
                    b1 = make_paragraph_block(p1)
                    if b1: blocks.append(b1)
                    blocks.append(table_block)
                    table_consumed = True
                    b2 = make_paragraph_block(p2)
                    if b2: blocks.append(b2)
                else:
                    b_before = make_paragraph_block(before_text)
                    if b_before:
                        blocks.append(b_before)

            attr_str = m.group(2)
            inner_content = m.group(3).strip()
            is_expandable = bool(re.search(r'\bexpandable\b', attr_str, re.IGNORECASE))
            b_type = "expandable_blockquote" if is_expandable else "blockquote"
            cite_match = re.search(r'\b(?:cite|credit)=["\']([^"\']+)["\']', attr_str, re.IGNORECASE)
            credit = cite_match.group(1) if cite_match else None

            inner_blocks = []
            has_media_inside = "{media}" in inner_content and media_block and not media_consumed
            has_table_inside = "{table}" in inner_content and table_block and not table_consumed

            if has_media_inside and not has_table_inside:
                parts = inner_content.split("{media}", 1)
                b1 = make_paragraph_block(parts[0])
                if b1: inner_blocks.append(b1)
                inner_blocks.append(media_block)
                media_consumed = True
                b2 = make_paragraph_block(parts[1])
                if b2: inner_blocks.append(b2)
            elif has_table_inside and not has_media_inside:
                parts = inner_content.split("{table}", 1)
                b1 = make_paragraph_block(parts[0])
                if b1: inner_blocks.append(b1)
                inner_blocks.append(table_block)
                table_consumed = True
                b2 = make_paragraph_block(parts[1])
                if b2: inner_blocks.append(b2)
            elif has_media_inside and has_table_inside:
                idx_m = inner_content.find("{media}")
                idx_t = inner_content.find("{table}")
                if idx_m < idx_t:
                    p1 = inner_content[:idx_m]
                    p2 = inner_content[idx_m + 7:idx_t]
                    p3 = inner_content[idx_t + 7:]
                    b1 = make_paragraph_block(p1)
                    if b1: inner_blocks.append(b1)
                    inner_blocks.append(media_block)
                    media_consumed = True
                    b2 = make_paragraph_block(p2)
                    if b2: inner_blocks.append(b2)
                    inner_blocks.append(table_block)
                    table_consumed = True
                    b3 = make_paragraph_block(p3)
                    if b3: inner_blocks.append(b3)
                else:
                    p1 = inner_content[:idx_t]
                    p2 = inner_content[idx_t + 7:idx_m]
                    p3 = inner_content[idx_m + 7:]
                    b1 = make_paragraph_block(p1)
                    if b1: inner_blocks.append(b1)
                    inner_blocks.append(table_block)
                    table_consumed = True
                    b2 = make_paragraph_block(p2)
                    if b2: inner_blocks.append(b2)
                    inner_blocks.append(media_block)
                    media_consumed = True
                    b3 = make_paragraph_block(p3)
                    if b3: inner_blocks.append(b3)
            else:
                b_in = make_paragraph_block(inner_content)
                if b_in:
                    inner_blocks.append(b_in)

            if inner_blocks:
                quote_block = {"type": b_type, "blocks": inner_blocks}
                if credit:
                    quote_block["credit"] = credit
                blocks.append(quote_block)

            last_idx = m.end()

        after_text = clean_text[last_idx:].strip()
        if after_text:
            if "{media}" in after_text and media_block and not media_consumed:
                p1, p2 = after_text.split("{media}", 1)
                b1 = make_paragraph_block(p1)
                if b1: blocks.append(b1)
                blocks.append(media_block)
                media_consumed = True
                b2 = make_paragraph_block(p2)
                if b2: blocks.append(b2)
            elif "{table}" in after_text and table_block and not table_consumed:
                p1, p2 = after_text.split("{table}", 1)
                b1 = make_paragraph_block(p1)
                if b1: blocks.append(b1)
                blocks.append(table_block)
                table_consumed = True
                b2 = make_paragraph_block(p2)
                if b2: blocks.append(b2)
            else:
                b_after = make_paragraph_block(after_text)
                if b_after:
                    blocks.append(b_after)

    else:
        # Standard processing when no top-level blockquotes
        if media_block:
            if "{media}" in clean_text:
                parts = clean_text.split("{media}", 1)
                p1 = parts[0].strip()
                p2 = parts[1].strip() if len(parts) > 1 else ""
                b1 = make_paragraph_block(p1)
                if b1:
                    blocks.append(b1)
                blocks.append(media_block)
                media_consumed = True
                b2 = make_paragraph_block(p2)
                if b2:
                    blocks.append(b2)
            elif media_position == "middle":
                if "\n\n" in clean_text:
                    paragraphs = [p.strip() for p in clean_text.split("\n\n") if p.strip()]
                    mid = max(1, len(paragraphs) // 2)
                    p1 = "\n\n".join(paragraphs[:mid])
                    p2 = "\n\n".join(paragraphs[mid:])
                    b1 = make_paragraph_block(p1)
                    if b1:
                        blocks.append(b1)
                    blocks.append(media_block)
                    media_consumed = True
                    b2 = make_paragraph_block(p2)
                    if b2:
                        blocks.append(b2)
                elif "\n" in clean_text:
                    lines = [l.strip() for l in clean_text.split("\n") if l.strip()]
                    mid = max(1, len(lines) // 2)
                    p1 = "\n".join(lines[:mid])
                    p2 = "\n".join(lines[mid:])
                    b1 = make_paragraph_block(p1)
                    if b1:
                        blocks.append(b1)
                    blocks.append(media_block)
                    media_consumed = True
                    b2 = make_paragraph_block(p2)
                    if b2:
                        blocks.append(b2)
                else:
                    blocks.append(media_block)
                    media_consumed = True
                    b = make_paragraph_block(clean_text)
                    if b:
                        blocks.append(b)
            elif media_position == "bottom":
                b = make_paragraph_block(clean_text)
                if b:
                    blocks.append(b)
                blocks.append(media_block)
                media_consumed = True
            else:  # top (default)
                blocks.append(media_block)
                media_consumed = True
                b = make_paragraph_block(clean_text)
                if b:
                    blocks.append(b)
        else:
            b = make_paragraph_block(clean_text)
            if b:
                blocks.append(b)

    # Position media_block if not yet consumed
    if media_block and not media_consumed:
        if media_position == "middle":
            if len(blocks) > 1:
                mid = max(1, len(blocks) // 2)
                blocks = blocks[:mid] + [media_block] + blocks[mid:]
            else:
                blocks = [media_block] + blocks
        elif media_position == "bottom":
            blocks.append(media_block)
        else:  # top
            blocks = [media_block] + blocks
        media_consumed = True

    # 3. Native Bot API 10.1 / 10.5 Table Block
    if table_block and not table_consumed:
        blocks.append(table_block)

    # 4. Bot API 10.3 In-Body Buttons (<tg-button-row>)
    if in_body_buttons:
        btn_rows: Dict[int, List[Dict[str, Any]]] = {}
        for btn in in_body_buttons:
            r = int(btn.get("row", 0))
            b_item = {"text": str(btn.get("text", "Button"))}
            if btn.get("url"):
                b_item["url"] = btn.get("url")
            if btn.get("style") in {"primary", "success", "danger", "link"}:
                b_item["style"] = btn.get("style")
            btn_rows.setdefault(r, []).append(b_item)

        for r in sorted(btn_rows.keys()):
            blocks.append({
                "type": "buttons",
                "buttons": btn_rows[r],
                "align": "center",
            })

    return {"blocks": blocks}

def render_table_html(table_data: Dict[str, Any]) -> str:
    """Render native Telegram Bot API HTML table for rich messages."""
    headers = table_data.get("headers", [])
    rows = table_data.get("rows", [])
    is_bordered = table_data.get("is_bordered", True)
    border_attr = ' border="1"' if is_bordered else ''

    parts = [f"<table{border_attr}>"]
    if headers:
        parts.append("<tr>" + "".join(f"<th>{html.escape(str(h))}</th>" for h in headers) + "</tr>")
    for row in rows:
        parts.append("<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in row) + "</tr>")
    parts.append("</table>")
    return "\n".join(parts)

def render_inbody_buttons_html(buttons: List[Dict[str, Any]]) -> str:
    """
    Render native Bot API 10.3 in-body row buttons for rich article HTML.
    Tags: <tg-button-row> and <tg-button url="..." style="...">
    """
    if not buttons:
        return ""
    btn_rows: Dict[int, List[Dict[str, Any]]] = {}
    for btn in buttons:
        r = int(btn.get("row", 0))
        btn_rows.setdefault(r, []).append(btn)

    html_rows = []
    for r in sorted(btn_rows.keys()):
        row_btns = []
        for b in btn_rows[r]:
            b_text = html.escape(str(b.get("text", "Button")))
            b_url = b.get("url", "")
            b_style = b.get("style")
            style_attr = f' style="{b_style}"' if b_style in {"primary", "success", "danger"} else ""
            if b_url:
                row_btns.append(f'<tg-button url="{html.escape(b_url)}"{style_attr}>{b_text}</tg-button>')
            else:
                row_btns.append(f'<tg-button{style_attr}>{b_text}</tg-button>')
        if row_btns:
            html_rows.append("<tg-button-row>\n  " + "\n  ".join(row_btns) + "\n</tg-button-row>")
    return "\n".join(html_rows)

def build_article_html(
    text: str,
    table_data: Optional[Dict[str, Any]] = None,
    buttons_list: Optional[List[Dict[str, Any]]] = None,
    button_type: str = "inline",
    media_list: Optional[List[Dict[str, Any]]] = None,
    media_position: str = "top",
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Builds full HTML document and InputRichMessageMedia objects for sendRichMessage.
    Embeds media at 'top', 'middle', 'bottom', or wherever {media} placeholder is placed.
    """
    clean_text = (text or "").strip()
    clean_text = re.sub(r'<pre>.*?</pre>', '', clean_text, flags=re.DOTALL).strip()

    embedded_media: List[Dict[str, Any]] = []
    media_tag = ""

    if media_list and len(media_list) > 0:
        item = media_list[0]
        file_id = item.get("file_id")
        m_type = item.get("media_type", "photo")
        if file_id:
            media_id = "media1"
            input_media_type = "video" if m_type == "video" else ("animation" if m_type == "sticker" else "photo")
            embedded_media.append({
                "id": media_id,
                "media": {
                    "type": input_media_type,
                    "media": file_id
                }
            })
            scheme_type = "video" if m_type == "video" else "photo"
            media_tag = f'<a href="tg://{scheme_type}?id={media_id}">&#8288;</a>'

    body_parts = []
    if media_tag:
        if "{media}" in clean_text:
            clean_text = clean_text.replace("{media}", media_tag)
            body_parts.append(clean_text)
        elif media_position == "middle":
            if "\n\n" in clean_text:
                paragraphs = clean_text.split("\n\n")
                mid = max(1, len(paragraphs) // 2)
                top_part = "\n\n".join(paragraphs[:mid])
                bot_part = "\n\n".join(paragraphs[mid:])
                body_parts.append(top_part)
                body_parts.append(media_tag)
                body_parts.append(bot_part)
            elif "\n" in clean_text:
                lines = clean_text.split("\n")
                mid = max(1, len(lines) // 2)
                top_part = "\n".join(lines[:mid])
                bot_part = "\n".join(lines[mid:])
                body_parts.append(top_part)
                body_parts.append(media_tag)
                body_parts.append(bot_part)
            else:
                body_parts.append(clean_text)
                body_parts.append(media_tag)
        elif media_position == "bottom":
            if clean_text:
                body_parts.append(clean_text)
            body_parts.append(media_tag)
        else:  # top (default)
            body_parts.append(media_tag)
            if clean_text:
                body_parts.append(clean_text)
    else:
        if clean_text:
            body_parts.append(clean_text)

    if table_data:
        body_parts.append(render_table_html(table_data))

    if button_type == "row" and buttons_list:
        btn_html = render_inbody_buttons_html(buttons_list)
        if btn_html:
            body_parts.append(btn_html)

    full_html = "\n\n".join(p for p in body_parts if p.strip())
    return full_html, embedded_media

def parse_table_input(raw_text: str) -> Optional[Dict[str, Any]]:
    """
    Parses user-entered table text into headers and rows.
    Format:
    Header 1 | Header 2 | Header 3
    Val 1 | Val 2 | Val 3
    Val 4 | Val 5 | Val 6
    """
    lines = [line.strip() for line in raw_text.strip().splitlines() if line.strip()]
    if not lines:
        return None

    parsed_rows = []
    for line in lines:
        cols = [col.strip() for col in line.split("|")]
        if any(cols):
            parsed_rows.append(cols)

    if not parsed_rows:
        return None

    # First row is treated as header if there is more than 1 row
    if len(parsed_rows) >= 2:
        headers = parsed_rows[0]
        rows = parsed_rows[1:]
    else:
        headers = []
        rows = parsed_rows

    return {
        "headers": headers,
        "rows": rows,
        "is_bordered": True,
        "is_striped": True,
        "align": "left",
    }

def parse_button_input(raw_text: str) -> List[Dict[str, Any]]:
    """Parse user-entered button markup into button models with rows and styles."""
    buttons = []
    lines = raw_text.strip().splitlines()
    for row_idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        col_items = line.split("|")
        for item in col_items:
            item = item.strip()
            if not item:
                continue

            if " - " in item:
                label, rest = item.split(" - ", 1)
            elif "-" in item:
                label, rest = item.split("-", 1)
            else:
                tokens = item.split()
                if len(tokens) >= 2:
                    label = tokens[0]
                    rest = " ".join(tokens[1:])
                else:
                    continue

            label = label.strip()
            rest_tokens = rest.strip().split()
            if not rest_tokens:
                continue

            url = rest_tokens[0].strip()
            style = rest_tokens[1].lower().strip() if len(rest_tokens) > 1 else None

            if style not in {"primary", "success", "danger"}:
                style = None

            if is_valid_url(url):
                buttons.append({
                    "text": label,
                    "url": url,
                    "style": style,
                    "row": row_idx,
                })
    return buttons

def parse_keyboard_input(raw_text: str) -> List[Dict[str, Any]]:
    """Parse user-entered reply keyboard markup into button models with rows."""
    buttons = []
    lines = raw_text.strip().splitlines()
    for row_idx, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        col_items = line.split("|")
        for item in col_items:
            item = item.strip()
            if not item:
                continue
            buttons.append({
                "text": item,
                "row": row_idx,
            })
    return buttons
