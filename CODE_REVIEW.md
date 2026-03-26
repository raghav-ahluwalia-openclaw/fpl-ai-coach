# FPL AI Coach - Code Review & Improvement Recommendations

**Review Date:** March 25, 2026  
**Reviewer:** Gwen (AI Coding Agent)  
**Scope:** Tech Stack, Code Quality, Functionality

---

## Executive Summary

This is a **well-architected FPL assistant** with solid foundations:
- ✅ Clean separation of concerns (routes/services/schemas)
- ✅ Comprehensive feature set (team recommendations, captaincy, live tracking, performance analytics)
- ✅ Good CI/CD pipeline with validation scripts
- ✅ Thoughtful ML integration with XGBoost
- ✅ Excellent documentation and developer experience

**Overall Grade:** B+ (85/100)

**Key Areas for Improvement:**
1. **Security hardening** (env vars, rate limiting, input validation)
2. **Performance optimization** (caching, query optimization, async I/O)
3. **Testing coverage** (unit/integration tests missing)
4. **Observability** (structured logging, metrics, alerting)
5. **ML pipeline maturity** (model versioning, A/B testing, retraining automation)

---

## 1. Tech Stack Recommendations

### 1.1 Backend (FastAPI)

#### Current State
- FastAPI 0.135.1 ✅ (recent)
- SQLAlchemy 2.0.48 ✅
- Python 3.11 (from CI) ⚠️
- `requests` library for HTTP ⚠️
- No async database driver ⚠️

#### Recommendations

| Priority | Change | Rationale |
|----------|--------|-----------|
| **HIGH** | Add `asyncpg` instead of `psycopg2-binary` | Async DB driver for better concurrency with FastAPI |
| **HIGH** | Replace `requests` with `httpx` (already in deps) | You have httpx installed but still using sync requests |
| **MEDIUM** | Add `pydantic-settings` | Better env var management with validation |
| **MEDIUM** | Add `structlog` or `loguru` | Structured logging for better observability |
| **LOW** | Consider `SQLModel` | Unifies SQLAlchemy + Pydantic, reduces boilerplate |

#### Missing Dependencies to Add
```txt
# Security
fastapi-limiter==0.1.6          # Rate limiting
slowapi==0.1.9                   # Alternative rate limiter
pydantic-settings==2.7.0         # Settings management

# Observability
structlog==24.4.0                # Structured logging
prometheus-fastapi-instrumentator==7.0.0  # Metrics

# Testing
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-cov==6.0.0
httpx==0.28.1                    # Already present, use it!

# Database
asyncpg==0.30.0                  # Async Postgres driver
alembic==1.14.0                  # DB migrations (CRITICAL)
```

### 1.2 Frontend (Next.js)

#### Current State
- Next.js 16.1.7 ✅ (cutting edge)
- React 19.2.3 ✅
- Tailwind CSS 4 ✅
- TypeScript ✅
- No state management library ⚠️
- No error boundary ⚠️

#### Recommendations

| Priority | Change | Rationale |
|----------|--------|-----------|
| **HIGH** | Add error boundaries | Prevent full app crashes on component errors |
| **HIGH** | Add React Query (TanStack Query) | Better data fetching, caching, retries |
| **MEDIUM** | Add Zod for runtime validation | Type-safe API response validation |
| **MEDIUM** | Add `next-themes` | Dark/light mode support |
| **LOW** | Consider `shadcn/ui` | Pre-built accessible components |

#### Missing Dependencies to Add
```json
{
  "@tanstack/react-query": "^5",
  "zod": "^3.24.0",
  "next-themes": "^0.4.0",
  "@sentry/nextjs": "^8.0.0",
  "react-error-boundary": "^5.0.0"
}
```

### 1.3 Infrastructure

#### Missing Critical Components

1. **Database Migrations** (CRITICAL)
   - No Alembic setup
   - Schema changes require manual intervention
   - **Action:** Initialize Alembic immediately

2. **Docker Production Image**
   - Only has `docker-compose.yml` for Postgres
   - No multi-stage build for backend/frontend
   - **Action:** Add production Dockerfiles

3. **Environment Management**
   - `.env.example` exists but minimal
   - No secrets management strategy
   - **Action:** Add comprehensive `.env.example` with all required vars

4. **CI/CD Enhancements**
   - No deployment pipeline
   - No automated model training
   - No security scanning
   - **Action:** Add deploy workflow, model retraining job

---

## 2. Code Quality Issues

### 2.1 Critical Issues

#### 2.1.1 No Database Migrations
**File:** `backend/app/db/models.py`

```python
# Current: Direct create_all() in main.py
@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)  # ❌ No versioning!
```

**Problem:** Schema changes will break production. No rollback capability.

**Fix:**
```bash
cd backend
alembic init alembic
# Configure alembic.ini
# Create initial migration
alembic revision --autogenerate -m "Initial schema"
alembic upgrade head
```

#### 2.1.2 Missing Input Validation
**File:** `backend/app/api/routes/team.py`

```python
@router.get("/api/fpl/team/{entry_id}/recommendation")
def team_recommendation(
    entry_id: int,  # ❌ No validation - could be any int
    gameweek: Optional[int] = Query(default=None, ge=1, le=38),
    mode: str = Query(default="balanced", pattern="^(safe|balanced|aggressive)$"),
):
```

**Problem:** `entry_id` has no bounds. Could lead to abuse or errors.

**Fix:**
```python
entry_id: int = Path(..., ge=1, le=10_000_000, description="FPL Entry ID")
```

#### 2.1.3 No Rate Limiting
**File:** `backend/app/main.py`

**Problem:** No rate limiting on API endpoints. FPL API could block you, or users could abuse your endpoints.

**Fix:**
```python
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter

@app.on_event("startup")
async def startup():
    redis = await redis.Redis()
    FastAPILimiter.init(redis)

@router.get("/api/fpl/team/{entry_id}/recommendation")
async def team_recommendation(
    ...,
    _ = Depends(RateLimiter(times=10, seconds=60))  # 10 req/min
):
```

#### 2.1.4 Synchronous HTTP Calls in Async App
**File:** `backend/app/services/http_client.py`

```python
def fetch_json(url: str, ...) -> Any:
    response = requests.get(url, timeout=timeout)  # ❌ Blocking!
```

**Fix:**
```python
import httpx

async def fetch_json(url: str, ...) -> Any:
    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=timeout)
```

### 2.2 High Priority Issues

#### 2.2.1 No Unit Tests
**Status:** Zero test files found

**Impact:** No safety net for refactoring. Bugs will slip through.

**Action:** Add pytest with minimum 70% coverage target

```bash
# Directory structure
backend/
  tests/
    conftest.py
    test_scoring.py
    test_team_routes.py
    test_ingest.py
    test_ml_recommender.py
```

#### 2.2.2 Magic Numbers Throughout
**File:** `backend/app/services/scoring.py`

```python
base = {1: 1.12, 2: 1.06, 3: 1.0, 4: 0.94, 5: 0.88}.get(round(avg_diff), 1.0)
dgw_boost = min(1.45, 1.0 + max(0, count - 1) * 0.28)
```

**Problem:** No documentation on where these numbers come from. Hard to tune.

**Fix:**
```python
# Add configuration class
@dataclass
class ScoringConfig:
    FIXTURE_DIFFICULTY_WEIGHTS: dict[int, float] = field(default_factory=lambda: {
        1: 1.12, 2: 1.06, 3: 1.0, 4: 0.94, 5: 0.88
    })
    DGW_BOOST_BASE: float = 1.0
    DGW_BOOST_PER_EXTRA: float = 0.28
    DGW_BOOST_MAX: float = 1.45

# Use with comments explaining source
# Source: Empirical analysis of 2023-24 season data (see docs/scoring-model.md)
base = config.FIXTURE_DIFFICULTY_WEIGHTS.get(round(avg_diff), 1.0)
```

#### 2.2.3 Inconsistent Error Handling
**File:** Multiple route files

```python
try:
    ...
except Exception as e:  # ❌ Bare except
    raise HTTPException(status_code=500, detail=f"...: {e}")
```

**Problems:**
- Catches everything (including KeyboardInterrupt, SystemExit)
- Exposes internal error details to users
- No structured logging

**Fix:**
```python
from app.core.errors import AppError

try:
    ...
except SQLAlchemyError as e:
    logger.error("Database error", extra={"error": str(e), "query": "..."})
    raise AppError("Database operation failed", status_code=500)
except HTTPException:
    raise  # Re-raise FastAPI HTTP exceptions
except Exception as e:
    logger.exception("Unexpected error in endpoint")
    raise AppError("Internal server error", status_code=500)
```

#### 2.2.4 No API Versioning
**File:** All routes

**Problem:** Breaking changes will break existing clients.

**Fix:**
```python
# Use URL versioning
/api/v1/fpl/team/{entry_id}/recommendation

# Or header versioning
@app.get(..., headers={"X-API-Version": "1"})
```

### 2.3 Medium Priority Issues

#### 2.3.1 Database Connection Management
**File:** Multiple route files

```python
db = SessionLocal()
try:
    ...
finally:
    db.close()  # ❌ Manual cleanup
```

**Fix:** Use dependency injection
```python
from fastapi import Depends
from app.db import get_db

@router.get("/endpoint")
def endpoint(db: Session = Depends(get_db)):
    ...

# In db/__init__.py
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

#### 2.3.2 No Request/Response Logging
**File:** `backend/app/main.py`

```python
# Current logging is basic
logging.basicConfig(level=logging.INFO, ...)
```

**Fix:** Add structured logging with request context
```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.dev.ConsoleRenderer()
    ],
    wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
)

logger = structlog.get_logger()
```

#### 2.3.3 Frontend: No Loading States
**File:** `frontend/src/app/weekly/page.tsx`

```tsx
{loading ? "Loading..." : "Run Weekly Plan"}  // ❌ Basic loading
```

**Fix:** Add skeleton loaders, optimistic updates
```tsx
import { Skeleton } from "@/components/ui/skeleton"

{loading ? (
  <Skeleton className="h-10 w-full" />
) : (
  <Button>Run Weekly Plan</Button>
)}
```

#### 2.3.4 No Health Check Depth
**File:** `backend/app/api/routes/ingest.py`

```python
@router.get("/health")
def health():
    ok = True
    try:
        with engine.connect() as c:
            c.exec_driver_sql("SELECT 1")
    except Exception as e:
        ok = False
```

**Fix:** Add comprehensive health checks
```python
@router.get("/health")
async def health():
    checks = {
        "database": await check_db(),
        "fpl_api": await check_fpl_api(),
        "model": await check_model_loaded(),
        "memory": check_memory_usage(),
    }
    status = 200 if all(c["ok"] for c in checks.values()) else 503
    return JSONResponse(status_code=status, content={"checks": checks})
```

### 2.4 Low Priority Issues

#### 2.4.1 Inconsistent Naming
- Mix of `snake_case` and `camelCase` in API responses
- Some functions start with `_` (private), some don't
- Inconsistent error message formats

#### 2.4.2 No API Documentation
- No OpenAPI/Swagger customization
- No example requests/responses
- No endpoint descriptions

#### 2.4.3 Frontend: Large Component
**File:** `frontend/src/app/weekly/page.tsx` (800+ lines)

**Fix:** Break into smaller components:
- `TeamHealthTable.tsx`
- `TransferPlans.tsx`
- `CaptainMatrix.tsx`
- `LineupOptimizer.tsx`

---

## 3. Functionality Improvements

### 3.1 High Priority Features

#### 3.1.1 User Authentication & Sessions
**Current:** No auth - anyone with entry_id can access data

**Add:**
- OAuth (Google/GitHub) or magic links
- Session management
- User preferences storage
- Saved teams (multiple FPL entries per user)

#### 3.1.2 Caching Layer
**Current:** Every request hits FPL API + database

**Add:**
```python
from functools import lru_cache
from datetime import timedelta

@cache.cached(timeout=timedelta(minutes=15))
async def get_team_data(entry_id: int, gw: int):
    ...
```

**Recommended:** Redis for distributed caching

#### 3.1.3 Webhook/Notification System
**Current:** Manual checking only

**Add:**
- Deadline reminders (email/push/SMS)
- Price change alerts
- Injury news alerts
- Team value change notifications

#### 3.1.4 Model Retraining Pipeline
**Current:** Manual model training

**Add:**
- Automated weekly retraining
- Model performance tracking
- A/B testing framework
- Model rollback capability

### 3.2 Medium Priority Features

#### 3.2.1 Historical Data Analysis
- Season-long performance tracking
- Head-to-head comparisons
- Transfer efficiency over time
- Captain choice analysis

#### 3.2.2 Social Features
- Share team recommendations
- League challenges
- Public leaderboards (opt-in)

#### 3.2.3 Advanced Analytics
- Expected points confidence intervals
- Monte Carlo simulations for season finish
- Optimal chip timing recommendations
- Wildcard optimization

#### 3.2.4 Mobile Optimization
- PWA support
- Touch-friendly UI
- Offline mode for cached data

### 3.3 Nice-to-Have Features

#### 3.3.1 AI-Powered Features
- Natural language queries ("Who should I captain this week?")
- Automated transfer explanations
- Chatbot interface

#### 3.3.2 Integration Features
- Discord/Slack bot
- Browser extension
- API for third-party apps

#### 3.3.3 Premium Features
- Advanced ML models
- Priority support
- Custom leagues
- Export capabilities

---

## 4. Security Recommendations

### 4.1 Critical Security Issues

#### 4.1.1 No Rate Limiting
**Risk:** API abuse, FPL API bans, DoS

**Fix:** Implement rate limiting (see 2.1.3)

#### 4.1.2 Exposed Database Credentials
**File:** `docker-compose.yml`

```yaml
environment:
  POSTGRES_PASSWORD: fpl  # ❌ Default password!
```

**Fix:**
- Use secrets management
- Generate strong passwords
- Never commit credentials

#### 4.1.3 No Input Sanitization
**Risk:** SQL injection, XSS

**Fix:**
- SQLAlchemy ORM helps prevent SQL injection ✅
- Add input validation with Pydantic
- Sanitize user-generated content

### 4.2 Security Hardening Checklist

- [ ] Add HTTPS enforcement (HSTS headers)
- [ ] Implement CSRF protection
- [ ] Add Content Security Policy headers
- [ ] Enable CORS only for trusted origins
- [ ] Add security headers (X-Frame-Options, X-Content-Type-Options)
- [ ] Implement request signing for internal APIs
- [ ] Add audit logging for sensitive operations
- [ ] Regular dependency vulnerability scanning (`npm audit`, `pip-audit`)
- [ ] Secrets rotation policy
- [ ] Database backup encryption

---

## 5. Performance Optimizations

### 5.1 Database

#### Current Issues
- N+1 queries in team routes
- No query optimization
- No connection pooling config

#### Fixes
```python
# Use eager loading
players = db.query(Player).options(joinedload(Player.team)).all()

# Add indexes (check models.py)
__table_args__ = (
    Index("ix_players_element_type", "element_type"),
    Index("ix_fixtures_event", "event"),
    # Add more based on query patterns
)

# Connection pooling
engine = create_engine(
    DATABASE_URL,
    pool_size=20,
    max_overflow=40,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

### 5.2 API Response Times

#### Current Issues
- Multiple FPL API calls per request
- No response compression
- No CDN for static assets

#### Fixes
```python
# Add gzip compression
from fastapi.middleware.gzip import GZipMiddleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Cache FPL API responses
@cache.cached(timeout=300)  # 5 minutes
async def fetch_fpl_data(url: str):
    ...

# Add ETag support for conditional requests
```

### 5.3 Frontend Performance

#### Current Issues
- Large bundle size (no analysis done)
- No image optimization
- No lazy loading

#### Fixes
```tsx
// Code splitting
const TeamHealthTable = dynamic(() => import('@/components/TeamHealthTable'))

// Image optimization (Next.js built-in)
import Image from 'next/image'
<Image src="..." width={100} height={100} alt="..." />

// Lazy load heavy components
<Suspense fallback={<Skeleton />}>
  <HeavyComponent />
</Suspense>
```

---

## 6. Testing Strategy

### 6.1 Recommended Test Structure

```
backend/
  tests/
    unit/
      test_scoring.py
      test_ml_recommender.py
      test_schemas.py
    integration/
      test_team_routes.py
      test_ingest_routes.py
      test_fpl_api.py
    conftest.py
    factories.py

frontend/
  tests/
    components/
      TeamHealthTable.test.tsx
      TransferPlans.test.tsx
    pages/
      weekly.test.tsx
    utils/
      api.test.ts
```

### 6.2 Test Coverage Targets

| Component | Target | Current |
|-----------|--------|---------|
| Services (scoring, ml) | 90% | 0% |
| API Routes | 80% | 0% |
| Schemas | 100% | 0% |
| Frontend Components | 70% | 0% |
| **Overall** | **80%** | **0%** |

### 6.3 CI Test Requirements

```yaml
# Add to .github/workflows/ci.yml
- name: Run tests with coverage
  run: |
    pytest --cov=app --cov-report=xml --cov-report=term-missing
    # Fail if coverage < 80%
    pytest --cov-fail-under=80
```

---

## 7. Documentation Improvements

### 7.1 Missing Documentation

- [ ] API reference (OpenAPI/Swagger customization)
- [ ] Architecture diagram
- [ ] Deployment guide
- [ ] Development setup guide (expand existing)
- [ ] ML model documentation (features, training process)
- [ ] Scoring algorithm explanation
- [ ] Troubleshooting guide
- [ ] Changelog/Release notes

### 7.2 Code Documentation

- [ ] Add docstrings to all public functions
- [ ] Add type hints (mostly done ✅)
- [ ] Document complex algorithms
- [ ] Add inline comments for magic numbers

---

## 8. Action Plan

### Phase 1: Critical Fixes (Week 1-2)
- [ ] Set up Alembic migrations
- [ ] Add rate limiting
- [ ] Fix async HTTP client usage
- [ ] Add input validation
- [ ] Secure database credentials
- [ ] Add basic unit tests (scoring service)

### Phase 2: Foundation (Week 3-4)
- [ ] Add comprehensive logging
- [ ] Set up monitoring/metrics
- [ ] Add error boundaries (frontend)
- [ ] Implement caching layer
- [ ] Add React Query (frontend)
- [ ] Expand test coverage to 50%

### Phase 3: Features (Week 5-8)
- [ ] User authentication
- [ ] Notification system
- [ ] Model retraining pipeline
- [ ] Performance optimizations
- [ ] Mobile optimization
- [ ] Expand test coverage to 80%

### Phase 4: Polish (Week 9-12)
- [ ] Advanced analytics features
- [ ] Documentation completion
- [ ] Security audit
- [ ] Load testing
- [ ] CI/CD enhancements
- [ ] Production deployment

### Phase 5: "Pro" Level Optimization (Next)
- [ ] **Feature Drift & Prediction Logging** - Track XP vs Actuals for model tuning
- [ ] **"Deadline Rush" SWR Strategy** - Stale-While-Revalidate caching for pre-deadline spikes
- [ ] **Type-Safe API Contract** - Generate frontend types from OpenAPI schema
- [ ] **PII & Data Privacy Anonymization** - Remove sensitive FPL data from storage
- [ ] **"Golden Master" Integration Testing** - Mocked DGW/Blank GW snapshots for regression testing

---

## 9. Summary

### Strengths
1. Well-organized code structure
2. Comprehensive feature set
3. Good use of TypeScript/Python type systems
4. Thoughtful ML integration
5. Solid CI pipeline foundation

### Weaknesses
1. No testing culture
2. Missing security measures
3. No database migrations
4. Limited observability
5. Performance not optimized

### Opportunities
1. User authentication & personalization
2. Real-time notifications
3. Advanced ML features
4. Mobile app/PWA
5. Community features

### Threats
1. FPL API changes/rate limits
2. Security vulnerabilities
3. Performance degradation at scale
4. Technical debt accumulation

---

## Appendix A: Quick Wins

These can be done in <1 day each:

1. Add `.env.example` with all required variables
2. Initialize Alembic
3. Add rate limiting middleware
4. Add error boundaries to frontend
5. Add Zod validation to API calls
6. Add React Query for data fetching
7. Set up basic pytest structure
8. Add structured logging
9. Add health check improvements
10. Add API documentation

---

## Appendix B: Recommended Tech Stack Updates

```txt
# Backend Additions
alembic==1.14.0
asyncpg==0.30.0
fastapi-limiter==0.1.6
pydantic-settings==2.7.0
structlog==24.4.0
prometheus-fastapi-instrumentator==7.0.0
redis==5.2.0
pytest==8.3.0
pytest-asyncio==0.24.0
pytest-cov==6.0.0

# Frontend Additions
@tanstack/react-query: ^5
zod: ^3.24.0
next-themes: ^0.4.0
@sentry/nextjs: ^8.0.0
react-error-boundary: ^5.0.0
@tanstack/react-table: ^8.0.0  # For better tables
```

---

**Generated by:** Gwen 🤓  
**Contact:** raghav-ahluwalia-openclaw (GitHub)
