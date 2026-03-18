from __future__ import annotations

from .base import router
from . import ingest as _ingest  # noqa: F401
from . import insights as _insights  # noqa: F401
from . import team as _team  # noqa: F401

__all__ = ["router"]
