from __future__ import annotations

from .base import router
from . import ingest as _ingest  # noqa: F401
from . import insights as _insights  # noqa: F401
from . import insights_brief as _insights_brief  # noqa: F401
from . import insights_notifications as _insights_notifications  # noqa: F401
from . import insights_planner as _insights_planner  # noqa: F401
from . import insights_research as _insights_research  # noqa: F401
from . import insights_settings as _insights_settings  # noqa: F401
from . import team as _team  # noqa: F401

__all__ = ["router"]
