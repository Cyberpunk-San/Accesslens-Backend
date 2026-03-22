---
title: AccessLens Backend
emoji: 🏎️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# AccessLens Backend — Full Documentation

AccessLens is a web accessibility auditing API. It uses a seven-layer engine pipeline, a headless browser (Playwright/Chromium), and an optional AI layer to detect and report accessibility issues on any public URL. The backend is a FastAPI application backed by SQLite and optionally Redis for caching.

---

## Quick Start

### Run locally (Python)
```bash
pip install -r requirements.txt
playwright install chromium
python run.py
```

### Run with Docker
```bash
docker-compose up --build
```

The API will be available at **http://localhost:8000** and the Swagger UI at **http://localhost:8000/docs**.

---

## Project Structure

```
backend/
├── app/                        # Application source
│   ├── main.py                 # FastAPI app factory & lifespan
│   ├── ai/                     # AI model integration layer
│   ├── api/                    # HTTP route definitions
│   ├── core/                   # Infrastructure (browser, DB, config...)
│   ├── engines/                # Accessibility analysis engines
│   ├── middleware/             # Rate limiting middleware
│   ├── models/                 # Pydantic schemas
│   ├── services/               # External service helpers
│   └── utils/                  # Shared utilities
├── migrations/                 # SQL schema migrations
├── scripts/                    # DevOps & maintenance scripts
├── tests/                      # Automated test suite
├── Dockerfile                  # Container build definition
├── docker-compose.yml          # Multi-service orchestration
├── requirements.txt            # Python dependencies
├── pytest.ini                  # Test runner configuration
├── run.py                      # Local dev entry point
└── .env.example                # Environment variable reference
```

---

## Root-Level Files

| File | Purpose |
|---|---|
| `run.py` | Local server entry point — starts Uvicorn with hot-reload |
| `requirements.txt` | All Python dependencies with minimum version pins |
| `pytest.ini` | pytest configuration — asyncio mode, coverage, test paths |
| `Dockerfile` | Builds on `mcr.microsoft.com/playwright/python:v1.40.0-jammy` (Chromium included) |
| `docker-compose.yml` | Starts `accesslens-api` + `accesslens-redis` services |
| `.dockerignore` | Excludes `venv/`, `data/`, `models/`, `tests/`, `tmp/`, build artifacts |
| `.env` | Active environment config (not committed) |
| `.env.example` | Template for environment variables |
| `.coveragerc` | Code coverage reporting configuration |
| `API.md` | REST endpoint reference |
| `ARCHITECTURE.md` | High-level system architecture notes |

---

## `app/` — Application Package

### `app/main.py`
FastAPI application factory. Defines the `lifespan` context manager that:
1. Initialises the cache, browser, rate limiter, and report storage
2. Registers all seven engines with their aliases into `EngineRegistry`
3. Mounts CORS, rate limiting, Prometheus metrics, and security-header middleware
4. Registers the `/api/v1` router

---

## `app/api/` — HTTP API Layer

| File | Purpose |
|---|---|
| `routes.py` | All REST endpoints (`POST /audit`, `GET /audit`, `GET /audit/{id}`, `GET /engines`, etc.). Launches audits as FastAPI `BackgroundTasks`. |
| `__init__.py` | Exports the `router` object |

**Key endpoints defined in `routes.py`:**

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/audit` | Start an accessibility audit (async, returns `audit_id`) |
| `GET` | `/api/v1/audit` | List recent audit reports |
| `GET` | `/api/v1/audit/{id}` | Fetch full audit report by ID |
| `GET` | `/api/v1/audit/{id}/status` | Poll audit completion status |
| `GET` | `/api/v1/engines` | List all registered engines |
| `GET` | `/health` | Health check |
| `GET` | `/metrics` | Prometheus metrics |

---

## `app/core/` — Infrastructure Layer

| File | Purpose |
|---|---|
| `config.py` | Pydantic `Settings` model — reads all config from env vars or `.env`. Controls browser, AI, DB, rate limiting, and logging settings. |
| `browser_manager.py` | Singleton Playwright browser manager. Manages a shared `BrowserContext`, page pool (`_active_pages`), and lifecycle (`initialize`, `get_page`, `release_page`, `close`). |
| `page_controller.py` | Navigates a browser page to a URL, waits for load, captures screenshot and accessibility tree. Page ownership transfers to `AuditOrchestrator`. |
| `audit_orchestrator.py` | Core audit pipeline — fetches a page, runs all requested engines in parallel (`_run_engine_safe`), aggregates issues, builds `AuditReport`. Releases the browser page in `finally`. |
| `report_storage.py` | Async SQLite persistence using `aiosqlite`. Tables: `reports`, `issues`. Provides `save_report`, `get_report`, `list_reports`. Falls back to in-memory store on error. |
| `accessibility_tree.py` | Extracts the browser's native accessibility tree via Playwright's `accessibility.snapshot()`. Normalises it into a structured dict for engine consumption. |
| `scoring.py` | `ConfidenceCalculator` — computes per-issue confidence scores from detection reliability, context clarity, and evidence quality weights. |
| `color_utils.py` | Colour math utilities — luminance, contrast ratio (WCAG 2.1 formula), hex/RGB parsing. Used by `ContrastEngine`. |
| `heading_analyzer.py` | Analyses heading hierarchy extracted from the DOM — detects skipped levels and multiple `<h1>` elements. |
| `landmark_validator.py` | Checks for presence and balance of ARIA landmark regions (`<main>`, `<nav>`, `<header>`, `<footer>`). |
| `logging_config.py` | Configures JSON-structured logging via `python-json-logger`. |
| `rate_limiter.py` | Re-exports `RateLimitMiddleware` and `rate_limiter` from the middleware package. |
| `__init__.py` | Package init — exposes `browser_manager`, `report_storage`, `AuditOrchestrator`. |

---

## `app/engines/` — Accessibility Analysis Engines

Each engine inherits from `BaseAccessibilityEngine` and implements `async analyze(page_data, request) -> List[UnifiedIssue]`.

| File | Engine Name | What It Detects |
|---|---|---|
| `base.py` | `BaseAccessibilityEngine` | Abstract base class defining the `analyze` interface and shared fields (`name`, `version`, `capabilities`). |
| `registry.py` | `EngineRegistry` | Dict-based registry for engine instances. Supports `register`, `get`, `get_all`, `get_by_capability`. |
| `wcag_engine.py` | `wcag_deterministic` | Runs **axe-core** (via `axe-playwright-python`) to find WCAG 2.1 A/AA violations. Result is normalised into `UnifiedIssue` objects with unique UUIDs. |
| `structural_engine.py` | `structural_engine` | Detects semantic structure failures: missing landmarks, heading hierarchy jumps, clickable `<div>` elements, redundant ARIA roles. Uses improved `getUniqueSelector` with `:nth-child` for accurate selectors. |
| `contrast_engine.py` | `contrast_engine` | Deep contrast analysis — extracts computed colours via JavaScript, calculates WCAG 2.1 contrast ratios for text and UI components. Also simulates hover/focus states. |
| `form_engine.py` | `form_engine` | Validates form accessibility: missing `<label>` associations, placeholder-as-label misuse, error messages not linked via `aria-describedby`. |
| `heuristic_engine.py` | `heuristic` | UX heuristics: repetitive/generic link text ("click here"), reading complexity score, redundant `title` attributes. |
| `navigation_engine.py` | `navigation` | Simulates keyboard navigation: Tab traversal order, focus trap detection, focus indicator presence. |
| `ai_engine.py` | `ai_engine` | The adaptive intelligence layer. It implements a multimodal pipeline: (1) **Vision Analysis (LLaVA)**: Uses screenshots to detect visual clutter, UI overlaps, and non-text elements embedded in graphics. (2) **Code Fixes (Mistral)**: Generates localized HTML/ARIA replacement blocks based on the surrounding DOM context. (3) **Quality Heuristics**: Analyzes the semantic meaning of alt-text (detecting vague terms like 'logo' or 'image') and evaluates content density ($total\_elements / viewport$). Includes a **Self-Doubt Filter** to prune hallucinations and malformed AI outputs. |
| `accessibility_structure_engine.py` | Utility | Lightweight helper for structural node analysis (used internally). |
| `__init__.py` | — | Exports all engine classes. |

---

## `app/models/` — Data Schemas

| File | Purpose |
|---|---|
| `schemas.py` | All Pydantic v2 models: `AuditRequest`, `AuditReport`, `AuditSummary`, `UnifiedIssue`, `IssueSeverity`, `IssueSource`, `WCAGCriteria`, `ElementLocation`, `RemediationSuggestion`, `EvidenceData`, `ConfidenceLevel`. `UnifiedIssue.id` uses a `default_factory=uuid4` to guarantee uniqueness in the database. |
| `__init__.py` | Re-exports all models |

---

## `app/ai/` — AI Integration Layer

| File | Purpose |
|---|---|
| `ai_service.py` | Orchestrates AI requests — routes to local LLaVA or Mistral endpoints, handles retries, parses and normalises model responses into `UnifiedIssue` objects. |
| `llava_integration.py` | Client for the LLaVA vision model HTTP endpoint — sends base64 screenshot + prompt, parses JSON response. |
| `mistral_integration.py` | Client for the Mistral 7B text model HTTP endpoint — sends accessibility tree + prompt, parses JSON response. |
| `__init__.py` | Exports `AIService` |

---

## `app/middleware/` — HTTP Middleware

| File | Purpose |
|---|---|
| `rate_limit.py` | `RateLimitMiddleware` — sliding-window per-IP rate limiting using an in-process counter. Configurable via `RATE_LIMIT_PER_MINUTE`. Returns `429` when exceeded. |
| `__init__.py` | Exports `RateLimitMiddleware` and `rate_limiter` |

---

## `app/utils/` — Shared Utilities

| File | Purpose |
|---|---|
| `cache.py` | `CacheManager` — async cache backed by Redis (if `REDIS_URL` is set) or an in-memory `dict`. Provides `get`, `set`, `delete`, `clear` with TTL support. |
| `validators.py` | `is_valid_url` — validates URLs against blocklists (private IPs, localhost, unsafe schemes) before auditing. |
| `helpers.py` | General helper functions: text truncation, duration formatting, severity normalisation, JSON sanitisation. |
| `tree_traversal.py` | Utilities for traversing nested accessibility tree structures. |
| `__init__.py` | Package exports |

---

## `app/services/` — Service Layer

| File | Purpose |
|---|---|
| `tree_extractor.py` | Helper service that wraps `AccessibilityTreeExtractor` for use outside the core module. |
| `__init__.py` | Package init |

---

## `migrations/` — Database Schema

SQL migration files for the SQLite schema (applied manually or via `scripts/run_migrations.py`).

| File | Description |
|---|---|
| `001_init.sql` | Creates `reports` and `issues` tables with full schema |
| `002_add_indices.sql` | Adds performance indices on `url`, `timestamp`, `severity` |
| `003_add_audit_queue.sql` | Adds `audit_queue` table for tracking async job state |
| `004_add_user_tables.sql` | Adds user and session tables (future feature) |

---

## `scripts/` — DevOps & Maintenance

| File | Purpose |
|---|---|
| `docker-entrypoint.sh` | Container startup script — creates `/app/data`, `/app/models`, `/app/logs`, runs DB setup, then launches the app |
| `scripts/setup.sh` | Local environment setup — creates virtualenv, installs deps, installs Playwright |
| `scripts/dev.sh` | Starts the dev server with hot-reload |
| `scripts/cleanup.sh` | Removes build artifacts, `__pycache__`, `.pytest_cache` |
| `setup_db.py` | Creates the SQLite database and runs the migration files |
| `run_migrations.py` | Applies pending SQL migration files |
| `download_models.py` | Downloads LLaVA / Mistral 7B model weights |
| `scripts/download_models.sh` | Shell wrapper around `download_models.py` |
| `backup_db.py` | Creates a timestamped backup of `accesslens.db` |
| `restore_db.py` | Restores a database from a backup file |
| `cleanup_reports.py` | Purges old audit reports older than a configurable age |

---

## `tests/` — Test Suite

Tests use `pytest` + `pytest-asyncio`. The FastAPI app is tested via `httpx.AsyncClient` with `ASGITransport` (no real HTTP server needed).

| File | What It Tests |
|---|---|
| `conftest.py` | Shared fixtures: app client, engine registry, test DB, browser mock |
| `test_api.py` | REST endpoint integration tests |
| `test_browser_manager.py` | Browser page pool, page acquisition, release lifecycle |
| `test_concurrency.py` | Parallel audit requests — verifies no race conditions |
| `test_contrast_engine.py` | Contrast ratio detection and colour parsing |
| `test_structural_engine.py` | Landmark, heading, and semantic HTML checks |
| `test_wcag_rules.py` | axe-core wrapper correctness |
| `test_performance.py` | Response time, memory growth, concurrent audit throughput, per-process CPU |
| `test_integration.py` | End-to-end audit flow with real page load |
| `test_report_storage.py` | SQLite save/load/list operations |
| `test_report_storage_units.py` | Unit tests for individual storage methods |
| `test_rate_limit.py` | Rate limit enforcement via HTTP |
| `test_rate_limit_units.py` | Unit tests for the sliding-window counter |
| `test_ai_engine.py` | AI engine mock tests |
| `test_ai_integrations_mock.py` | LLaVA / Mistral client mock tests |
| `test_cache_service.py` | In-memory and Redis cache behaviour |
| `test_security.py` | URL validation, private IP blocking |
| `test_load.py` | High-volume request stress test |
| `test_error_recovery.py` | Engine failure isolation and recovery |
| `test_engines_edge.py` | Edge cases: empty pages, malformed HTML |
| `test_scoring_logic.py` | Confidence score calculation |
| `test_color_utils_edge.py` | Edge cases in colour math |
| `test_color_utils_more.py` | Extended colour utility coverage |
| `test_helpers_coverage.py` | Helper function coverage |
| `test_accessibility_structure.py` | Accessibility tree structure validation |

---

## Environment Variables

Key variables from `.env.example`:

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | `0.0.0.0` | Server bind address |
| `API_PORT` | `8000` | Server port |
| `DATABASE_URL` | `sqlite:///./accesslens.db` | SQLite database path |
| `REDIS_URL` | *(unset)* | Redis URL — leave unset to use in-memory cache |
| `BROWSER_HEADLESS` | `true` | Run Chromium headless |
| `BROWSER_MAX_PAGES` | `10` | Max concurrent browser pages |
| `BROWSER_TIMEOUT` | `60000` | Page navigation timeout (ms) |
| `CORS_ORIGINS` | `http://localhost:3000` | Allowed CORS origins (comma-separated) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `ENABLE_AI_ENGINE` | `true` | Enable the AI analysis layer |

---

## Data Flow

```
POST /api/v1/audit
    │
    ▼
AuditOrchestrator.run_audit()
    │
    ├─► PageController.navigate_and_extract()
    │       └─► BrowserManager.get_page()
    │           └─► Playwright Chromium → Page
    │
    ├─► Engine Pipeline (parallel)
    │       ├─ `WCAGEngine`        (axe-core)
    │       ├─ `StructuralEngine`  (DOM semantic analysis)
    │       ├─ `ContrastEngine`    (colour contrast)
    │       ├─ `FormEngine`        (label & error associations)
    │       ├─ `HeuristicEngine`   (UX patterns)
    │       ├─ `NavigationEngine`  (keyboard simulation)
    │       └─ `AIEngine`          (contextual AI)
    │
    ├─► Issue Aggregation → AuditReport
    │
    └─► ReportStorage.save_report() → SQLite
```
