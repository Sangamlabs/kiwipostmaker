from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class PostButton:
    text: str
    url: Optional[str] = None
    callback_data: Optional[str] = None
    style: Optional[str] = None  # 'primary' (blue), 'success' (green), 'danger' (red)
    row: int = 0
