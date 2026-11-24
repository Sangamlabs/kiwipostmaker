from urllib.parse import urlparse
from typing import List, Tuple

VALID_BUTTON_STYLES = {"primary", "success", "danger"}

def is_valid_url(url: str) -> bool:
    """Validate that a URL has a valid web or telegram scheme and network location."""
    if not url or not isinstance(url, str):
        return False
    try:
        parsed = urlparse(url.strip())
        return parsed.scheme in {"http", "https", "tg", "t.me"} and bool(parsed.netloc or parsed.path)
    except Exception:
        return False

def validate_album_media_count(count: int) -> Tuple[bool, str]:
    """Validate that media album count fits Telegram restrictions (2 to 10 items)."""
    if count < 2:
        return False, "An album must contain at least 2 media items."
    if count > 10:
        return False, "Telegram allows a maximum of 10 media items per album."
    return True, ""
