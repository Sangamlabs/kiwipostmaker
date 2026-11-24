from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Channel:
    channel_id: str
    title: str
    username: Optional[str] = None
    owner_id: int = 0
    authorized_users: List[int] = field(default_factory=list)
    added_at: Optional[str] = None
