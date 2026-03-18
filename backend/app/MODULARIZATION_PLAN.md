# Backend modularization plan (phase 1 complete)

## Completed in this pass
- Added shared HTTP client utility: `app/services/http_client.py`
- Added unified API error handlers: `app/core/errors.py`
- Registered handlers in `app/main.py`
- Added package scaffolding for `app/api/` and `app/api/routes/`

## Next extraction steps
1. Move SQLAlchemy models into `app/db/models.py`
2. Move Pydantic response models into `app/schemas/`
3. Move scoring + recommendation helpers into `app/services/scoring.py`
4. Move endpoints into route modules under `app/api/routes/`
