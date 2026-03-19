# Backend modularization plan (phase 2 complete)

## Completed in this pass
- Added shared HTTP client utility: `app/services/http_client.py`
- Added unified API error handlers: `app/core/errors.py`
- Registered handlers in `app/main.py`
- Added package scaffolding for `app/api/` and `app/api/routes/`
- Moved SQLAlchemy base/session setup to package module `app/db/__init__.py`
- Moved SQLAlchemy models into `app/db/models.py`
- Moved Pydantic response models into `app/schemas/` (`common.py`, `fpl.py`, `__init__.py`)
- Added scoring/recommendation helper service: `app/services/scoring.py`
- Slimmed route shared module `app/api/routes/base.py` to orchestration + metadata/fetch helpers

## Remaining extraction steps
1. Gradually remove wildcard imports (`from .base import *`) in route modules and switch to explicit imports
2. Consider splitting large route modules (`team.py`, `insights_research.py`) into narrower route/service units
3. Add targeted unit tests for `app/services/scoring.py` and schemas package compatibility
