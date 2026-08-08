# GamePulse Fusion Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the production-ready Next.js + FastAPI + Postgres foundation, migrate the useful prototype data, and create provider/snapshot contracts that every GamePulse mode can consume.

**Architecture:** Keep existing Python domain logic under `gamepulse/`, add a FastAPI boundary under `api/` and `gamepulse/web_api/`, add a Next.js App Router frontend at repository root, and replace runtime SQLite reads with SQLAlchemy repositories backed by Postgres. SQLite remains only as a migration/source artifact during the transition.

**Tech Stack:** Next.js App Router, TypeScript, Tailwind CSS, FastAPI, Pydantic, SQLAlchemy 2.x, Alembic, psycopg 3, Neon/Postgres, pytest, Vitest.

## Global Constraints

- Work on `feature/gamepulse-fusion-web`; never implement directly on `main`.
- v1 supports Steam/PC only.
- No required Twitch/Streams Charts credentials.
- User-provided Steam keys must never be persisted or logged.
- Normal reads come from cached Postgres snapshots.
- Provider values carry source, observed-at, freshness and confidence.
- SteamSpy values are ownership estimates, not exact sales.
- Do not automate SteamDB access without explicit permission.
- Do not port the native desktop UI.

---

### Task 1: Establish baseline and dual-runtime scaffold

**Files:**
- Create: `package.json`
- Create: `tsconfig.json`
- Create: `next.config.ts`
- Create: `postcss.config.mjs`
- Create: `src/app/layout.tsx`
- Create: `src/app/page.tsx`
- Create: `src/app/globals.css`
- Create: `api/index.py`
- Create: `gamepulse/web_api/__init__.py`
- Create: `gamepulse/web_api/app.py`
- Modify: `requirements.txt`
- Modify: `.gitignore`
- Test: `tests/test_web_api_health.py`
- Test: `src/app/page.test.tsx`

**Interfaces:**
- Produces: FastAPI application object `gamepulse.web_api.app:app`.
- Produces: `GET /api/health -> {"status":"ok"}`.
- Produces: Next.js App Router root page rendering the GamePulse brand placeholder only; final landing design belongs to O2.

- [ ] **Step 1: Add failing Python health test**

```python
from fastapi.testclient import TestClient
from gamepulse.web_api.app import app


def test_health_endpoint():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 2: Run the focused test and confirm failure**

Run: `python -m pytest tests/test_web_api_health.py -q`
Expected: import/module failure because `gamepulse.web_api.app` does not exist yet.

- [ ] **Step 3: Add production dependencies and minimal FastAPI app**

`requirements.txt` must retain the current analytics dependencies and add:

```text
fastapi>=0.115
pydantic>=2.9
pydantic-settings>=2.5
sqlalchemy>=2.0
alembic>=1.13
psycopg[binary]>=3.2
httpx>=0.27
```

`gamepulse/web_api/app.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="GamePulse API", version="1")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

`api/index.py`:

```python
from gamepulse.web_api.app import app
```

- [ ] **Step 4: Add Next.js scaffold and smoke test**

Use a single App Router project at repository root with scripts:

```json
{
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "test": "vitest run"
  }
}
```

Root page copy must contain `GamePulse` and must not add final mode dashboards yet.

- [ ] **Step 5: Run baseline verification**

Run:
- `python -m pytest tests/test_web_api_health.py -q`
- `python -m compileall -q api gamepulse`
- `npm test -- --run`
- `npm run build`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add package.json tsconfig.json next.config.ts postcss.config.mjs src api gamepulse/web_api requirements.txt .gitignore tests/test_web_api_health.py
git commit -m "feat: scaffold GamePulse web and API runtimes"
```

### Task 2: Add production settings with explicit secret boundaries

**Files:**
- Create: `gamepulse/web_api/settings.py`
- Create: `tests/test_web_settings.py`
- Modify: `.env.example`

**Interfaces:**
- Produces: `WebSettings` with `database_url`, `cron_secret`, optional `mistral_api_key`, `app_env`, provider timeouts.
- Explicitly does **not** include visitor Steam API keys; those arrive per request.

- [ ] **Step 1: Write settings tests**

```python
from gamepulse.web_api.settings import WebSettings


def test_web_settings_do_not_model_user_steam_secret(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost/db")
    settings = WebSettings()
    assert not hasattr(settings, "steam_web_api_key")


def test_database_url_is_required(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    try:
        WebSettings()
    except Exception:
        pass
    else:
        raise AssertionError("DATABASE_URL must be required")
```

- [ ] **Step 2: Run test and verify failure**

Run: `python -m pytest tests/test_web_settings.py -q`
Expected: missing module.

- [ ] **Step 3: Implement `WebSettings`**

Use `pydantic_settings.BaseSettings` and define only server-owned secrets/config. `.env.example` must include `DATABASE_URL`, `CRON_SECRET`, optional `MISTRAL_API_KEY`, provider timeout/cache settings. Remove Twitch/Streams Charts fields from the normal production example; keep legacy notes only if required for old prototype scripts.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_web_settings.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add gamepulse/web_api/settings.py tests/test_web_settings.py .env.example
git commit -m "feat: define production web settings"
```

### Task 3: Create Postgres schema and repository boundary

**Files:**
- Create: `gamepulse/db/__init__.py`
- Create: `gamepulse/db/session.py`
- Create: `gamepulse/db/models.py`
- Create: `gamepulse/db/repositories.py`
- Create: `alembic.ini`
- Create: `migrations/env.py`
- Create: `migrations/versions/0001_gamepulse_core.py`
- Test: `tests/test_postgres_models.py`
- Test: `tests/test_snapshot_repository.py`

**Interfaces:**
- `GameRepository.get_game(app_id: int) -> GameRecord | None`
- `GameRepository.list_games(limit: int, offset: int) -> list[GameRecord]`
- `SnapshotRepository.latest_for_game(app_id: int) -> GameSignalSnapshot | None`
- `SnapshotRepository.history_for_game(app_id: int, metric: str, limit: int) -> list[MetricPoint]`
- `SnapshotRepository.upsert_snapshot(snapshot: GameSignalSnapshot) -> None`

- [ ] **Step 1: Write model/repository tests**

Use a temporary Postgres test URL when available and skip with an explicit reason otherwise. Assert the schema can store one game plus one Steam metric and one streaming metric with `source_name`, `observed_at`, and `confidence`.

- [ ] **Step 2: Define SQLAlchemy models**

Minimum tables:
- `games`
- `game_tags`
- `game_genres`
- `review_summaries`
- `steam_snapshots`
- `streaming_snapshots`
- `steamspy_snapshots`
- `trend_scores`
- `provider_runs`

Every snapshot row must include `source_name`, `source_mode`, `observed_at`, and `confidence`; nullable `source_url` is allowed.

- [ ] **Step 3: Add SQLAlchemy session factory**

Use `NullPool` for the serverless runtime unless a managed pooling URL is explicitly supplied. Keep connection creation inside request/job scope.

- [ ] **Step 4: Implement repository dataclasses and methods**

Repositories return typed Python dataclasses/Pydantic models, never raw SQLAlchemy rows to mode services.

- [ ] **Step 5: Run tests**

Run:
- `python -m pytest tests/test_postgres_models.py tests/test_snapshot_repository.py -q`
- `alembic upgrade head`

Expected: PASS against configured test Postgres.

- [ ] **Step 6: Commit**

```bash
git add gamepulse/db migrations alembic.ini tests/test_postgres_models.py tests/test_snapshot_repository.py
git commit -m "feat: add Postgres snapshot schema"
```

### Task 4: Add deterministic SQLite-to-Postgres importer

**Files:**
- Create: `scripts/migrate_sqlite_to_postgres.py`
- Create: `gamepulse/db/importer.py`
- Test: `tests/test_sqlite_importer.py`
- Modify: `.vercelignore`

**Interfaces:**
- `import_sqlite(sqlite_path: Path, repository: ImportRepository) -> ImportReport`
- `ImportReport` contains row counts per entity, skipped rows, and validation failures.

- [ ] **Step 1: Create a tiny SQLite fixture in test code**

Fixture must include two games, tags, genres, one review summary and one market snapshot.

- [ ] **Step 2: Assert deterministic mapping**

Test that the importer preserves Steam App IDs, artwork URLs, review scores, ownership bounds and tags, and is idempotent when run twice.

- [ ] **Step 3: Implement importer**

Read through the existing SQLite schema rather than copying the large database into the Vercel deployment. Batch inserts/upserts in deterministic Steam App ID order.

- [ ] **Step 4: Exclude prototype SQLite/LFS artifacts from Vercel runtime**

`.vercelignore` must include the prototype database and raw/processed datasets that are not required by the web runtime.

- [ ] **Step 5: Verify**

Run: `python -m pytest tests/test_sqlite_importer.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add scripts/migrate_sqlite_to_postgres.py gamepulse/db/importer.py tests/test_sqlite_importer.py .vercelignore
git commit -m "feat: add prototype data migration"
```

### Task 5: Add provider contracts and no-key public providers

**Files:**
- Create: `gamepulse/providers/contracts.py`
- Create: `gamepulse/providers/steam_public.py`
- Create: `gamepulse/providers/steamspy.py`
- Create: `gamepulse/providers/twitchtracker.py`
- Create: `gamepulse/providers/composite.py`
- Test: `tests/test_provider_contracts.py`
- Test: `tests/test_twitchtracker_provider.py`
- Test: `tests/test_provider_fallback.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ProviderMetric:
    metric: str
    value: float | int | str | None
    observed_at: datetime
    source_name: str
    source_mode: str
    confidence: str
    source_url: str | None = None

class GameSignalProvider(Protocol):
    def fetch(self, game: GameIdentity) -> list[ProviderMetric]: ...
```

- [ ] **Step 1: Test normalization and provenance**

Tests must prove a provider cannot return a metric without `observed_at`, `source_name`, `source_mode`, and `confidence`.

- [ ] **Step 2: Implement Steam public player-count provider**

Use Steam's public current-player endpoint and normalize to `current_players`.

- [ ] **Step 3: Implement SteamSpy provider**

Normalize owners into lower/upper bounds. Never emit a `sales` metric.

- [ ] **Step 4: Implement TwitchTracker summary provider**

Use the documented category-summary endpoint `https://twitchtracker.com/api/games/summary/{twitch_id_or_full_name}`. Treat it as a 30-day summary source and preserve source timestamp/fetch timestamp separately when source payload allows.

- [ ] **Step 5: Implement composite provider**

The composite collects independent providers, records per-provider failures, and returns all successful normalized metrics without converting one provider failure into a full failure.

- [ ] **Step 6: Verify with mocked HTTP**

Run: `python -m pytest tests/test_provider_contracts.py tests/test_twitchtracker_provider.py tests/test_provider_fallback.py -q`
Expected: PASS with network mocked.

- [ ] **Step 7: Commit**

```bash
git add gamepulse/providers tests/test_provider_contracts.py tests/test_twitchtracker_provider.py tests/test_provider_fallback.py
git commit -m "feat: add source-neutral public signal providers"
```

### Task 6: Add snapshot refresh service and protected cron endpoint

**Files:**
- Create: `gamepulse/services/snapshot_refresh.py`
- Create: `gamepulse/web_api/routes/jobs.py`
- Modify: `gamepulse/web_api/app.py`
- Create: `vercel.json`
- Test: `tests/test_snapshot_refresh.py`
- Test: `tests/test_cron_auth.py`

**Interfaces:**
- `SnapshotRefreshService.refresh_catalog(limit: int | None = None) -> RefreshReport`
- `GET /jobs/refresh` requires `Authorization: Bearer <CRON_SECRET>`.

- [ ] **Step 1: Write auth test**

Unauthenticated and wrong-secret requests return 401; correct secret reaches a mocked refresh service.

- [ ] **Step 2: Write refresh fallback test**

Given Steam success + TwitchTracker failure + SteamSpy success, the run persists Steam/SteamSpy metrics, records TwitchTracker failure in `provider_runs`, and returns a partial-success report.

- [ ] **Step 3: Implement refresh service**

Do not perform arbitrary provider requests from frontend page loads. The refresh service owns external market refreshes.

- [ ] **Step 4: Configure conservative v1 cron**

Because Vercel Hobby supports at most two cron jobs and a minimum daily interval, configure one daily refresh endpoint in `vercel.json`:

```json
{
  "crons": [
    {"path": "/api/jobs/refresh", "schedule": "0 2 * * *"}
  ]
}
```

The service design must allow a faster schedule on Pro without code changes.

- [ ] **Step 5: Verify**

Run:
- `python -m pytest tests/test_snapshot_refresh.py tests/test_cron_auth.py -q`
- `python -m compileall -q api gamepulse scripts tests`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add gamepulse/services/snapshot_refresh.py gamepulse/web_api/routes/jobs.py gamepulse/web_api/app.py vercel.json tests/test_snapshot_refresh.py tests/test_cron_auth.py
git commit -m "feat: add cached signal refresh pipeline"
```

### Task 7: Add read APIs and source-status contract

**Files:**
- Create: `gamepulse/web_api/schemas/common.py`
- Create: `gamepulse/web_api/routes/games.py`
- Create: `gamepulse/web_api/routes/status.py`
- Modify: `gamepulse/web_api/app.py`
- Test: `tests/test_game_read_api.py`
- Test: `tests/test_source_status_api.py`

**Interfaces:**
- `GET /games/{app_id}` returns canonical metadata plus latest normalized metrics.
- `GET /games/{app_id}/history?metric=current_players` returns ordered points.
- `GET /status/sources` returns source name, latest success, latest failure, freshness and state.

- [ ] **Step 1: Write API contract tests**

Assert `GET /games/10` returns `steam_app_id`, `name`, `header_image_url`, `steam_store_url`, and `metrics[]`, where every metric has provenance fields.

- [ ] **Step 2: Implement Pydantic response schemas**

No SQLAlchemy model objects should leak through JSON responses.

- [ ] **Step 3: Implement routes using repositories only**

Routes do not call external providers.

- [ ] **Step 4: Verify**

Run: `python -m pytest tests/test_game_read_api.py tests/test_source_status_api.py -q`
Expected: PASS.

- [ ] **Step 5: Run foundation regression suite**

Run:
- `python -m pytest tests/test_web_api_health.py tests/test_web_settings.py tests/test_postgres_models.py tests/test_snapshot_repository.py tests/test_sqlite_importer.py tests/test_provider_contracts.py tests/test_twitchtracker_provider.py tests/test_provider_fallback.py tests/test_snapshot_refresh.py tests/test_cron_auth.py tests/test_game_read_api.py tests/test_source_status_api.py -q`
- `npm run build`

Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add gamepulse/web_api tests/test_game_read_api.py tests/test_source_status_api.py
git commit -m "feat: expose cached GamePulse read APIs"
```

## Foundation Acceptance Gate

Before O1 is marked `COMPLETE`, the parent verifies:

1. Next.js build succeeds.
2. FastAPI health/read routes pass focused tests.
3. Postgres migrations and importer are idempotent.
4. No runtime page route depends on SQLite.
5. No visitor Steam key field exists in server settings or persistence models.
6. TwitchTracker/Steam/SteamSpy failures are isolated and recorded.
7. All metrics returned to callers carry provenance/freshness/confidence.
8. `vercel.json` cron route is protected by `CRON_SECRET`.
