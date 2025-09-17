from __future__ import annotations

from typing import Protocol
from typing import Any


class BaseTool(Protocol):
    
    def execute(self, *args: Any, **kwargs: Any) -> Any: ...