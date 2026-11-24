from typing import Any, Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from ..utils.validation import is_valid_url, VALID_BUTTON_STYLES

def build_post_inline_keyboard(buttons_data: List[Dict[str, Any]]) -> InlineKeyboardMarkup:
    """
    Constructs an InlineKeyboardMarkup supporting colored button styles (primary, success, danger)
    matching Pages 4-5 of DX-Notes.
    """
    if not buttons_data:
        return InlineKeyboardMarkup([])

    # Group buttons by row
    rows: Dict[int, List[InlineKeyboardButton]] = {}
    for item in buttons_data:
        text = str(item.get("text", "")).strip()
        url = str(item.get("url", "")).strip() if item.get("url") else None
        callback_data = item.get("callback_data")
        style = item.get("style")
        row_idx = int(item.get("row", 0))

        if not text:
            continue

        # Validate button style
        btn_kwargs: Dict[str, Any] = {"text": text}
        if url and is_valid_url(url):
            btn_kwargs["url"] = url
        elif callback_data:
            btn_kwargs["callback_data"] = callback_data
        else:
            # Fallback for display/preview
            btn_kwargs["callback_data"] = "noop"

        if style in VALID_BUTTON_STYLES:
            btn_kwargs["style"] = style

        try:
            btn = InlineKeyboardButton(**btn_kwargs)
        except TypeError:
            # In case running on an environment without style support
            btn_kwargs.pop("style", None)
            btn = InlineKeyboardButton(**btn_kwargs)

        rows.setdefault(row_idx, []).append(btn)

    sorted_rows = [rows[idx] for idx in sorted(rows.keys())]
    return InlineKeyboardMarkup(sorted_rows)

def build_post_reply_keyboard(buttons_data: List[Dict[str, Any]]) -> ReplyKeyboardMarkup:
    """
    Constructs a ReplyKeyboardMarkup from user-entered keyboard buttons.
    """
    if not buttons_data:
        return ReplyKeyboardMarkup([], resize_keyboard=True)

    rows: Dict[int, List[KeyboardButton]] = {}
    for item in buttons_data:
        text = str(item.get("text", "")).strip()
        row_idx = int(item.get("row", 0))
        if not text:
            continue
        rows.setdefault(row_idx, []).append(KeyboardButton(text=text))

    sorted_rows = [rows[idx] for idx in sorted(rows.keys())]
    return ReplyKeyboardMarkup(sorted_rows, resize_keyboard=True)
