import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

@dataclass
class Post:
    id: Optional[int] = None
    owner_user_id: int = 0
    channel_id: Optional[str] = None
    text: Optional[str] = None
    media_json: str = "[]"
    buttons_json: str = "[]"
    inline_buttons_json: str = "[]"
    row_buttons_json: str = "[]"
    table_json: Optional[str] = None
    post_type: str = "standard"  # standard, article
    button_type: str = "inline"  # legacy: inline, row
    media_position: str = "top"  # top, middle, bottom
    scheduled_at: Optional[str] = None
    status: str = "draft"  # draft, queued, publishing, published, failed
    telegram_message_ids: str = "[]"
    last_error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

    @property
    def media_list(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.media_json or "[]")
        except Exception:
            return []

    @property
    def inline_buttons_list(self) -> List[Dict[str, Any]]:
        try:
            res = json.loads(self.inline_buttons_json or "[]")
            if res:
                return res
        except Exception:
            pass
        # Fallback to legacy buttons_json if button_type != 'row'
        if getattr(self, "button_type", "inline") != "row":
            return self.buttons_list
        return []

    @property
    def row_buttons_list(self) -> List[Dict[str, Any]]:
        try:
            res = json.loads(self.row_buttons_json or "[]")
            if res:
                return res
        except Exception:
            pass
        # Fallback to legacy buttons_json if button_type == 'row'
        if getattr(self, "button_type", "inline") == "row":
            return self.buttons_list
        return []

    @property
    def buttons_list(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.buttons_json or "[]")
        except Exception:
            return []

    @property
    def table_data(self) -> Optional[Dict[str, Any]]:
        if not self.table_json:
            return None
        try:
            return json.loads(self.table_json)
        except Exception:
            return None

    @property
    def message_ids_list(self) -> List[int]:
        try:
            return json.loads(self.telegram_message_ids or "[]")
        except Exception:
            return []
