# GamePulse Fusion Deployment and QA Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the verified Player, Streamer and Developer workstreams, enforce CI/quality/security gates, provision Vercel-compatible Postgres, verify a shareable Vercel preview, and promote only the validated artifact.

**Architecture:** The repository remains one Vercel project: Next.js serves the public UI and `api/index.py` exposes FastAPI functions. Neon/Postgres is provisioned through the Vercel Marketplace where available. Production refresh is cron-triggered and authenticated with `CRON_SECRET`. Deployment follows preview -> verification -> promote rather than unverified direct production deployment.

**Tech Stack:** GitHub Actions, pytest, Vitest, Playwright, Next.js build, Vercel CLI/platform, Neon Postgres, Vercel Cron.

## Global Constraints

- O3, O4 and O5 must each be independently verified before integration.
- Never commit Vercel tokens, database credentials, Steam keys or Mistral keys.
- Preview deployment must be tested before production promotion.
- User Steam Web API keys are never Vercel environment variables; they remain browser/request session values only.
- Production can use server-owned `MISTRAL_API_KEY` optionally, but Developer deterministic fallback must remain functional without it.
- Twitch/Streams Charts credentials are not required.
- SteamDB automated access remains disabled without explicit permission.
- On Vercel Hobby, keep scheduled jobs within the documented maximum of two and daily minimum interval; the v1 configuration uses one daily refresh.

---

### Task 1: Integrate mode branches/contracts and run local full regression

**Files:**
- Modify only as required for integration: shared API schemas/client imports, route registration, navigation.
- Create: `docs/verification/gamepulse-fusion-local-regression.md`

**Interfaces:**
- Shared GameDetail/Metric/SourceStatus contracts from O1/O2 are authoritative.
- Mode code must adapt to shared contracts rather than duplicating them.

- [ ] Confirm O3/O4/O5 completion commits and acceptance evidence in the parent ledger.
- [ ] Resolve any duplicate schema/type definitions by keeping the O1/O2 version and updating mode imports.
- [ ] Run `python -m pytest -q` and record total/pass/fail count.
- [ ] Run `python -m compileall -q api gamepulse scripts tests`.
- [ ] Run `npm test -- --run`.
- [ ] Run `npm run build`.
- [ ] Run `npx playwright test` against the local app/API stack.
- [ ] Record exact commands/outcomes in `docs/verification/gamepulse-fusion-local-regression.md`; do not claim any command was run if it was not.
- [ ] Commit with `git commit -m "test: integrate and verify GamePulse fusion locally"`.

### Task 2: Add GitHub CI quality gate

**Files:**
- Create or replace: `.github/workflows/fusion-ci.yml`
- Test: workflow syntax via local parser/`gh` where available.

**Interfaces:**
- CI runs on pull requests and pushes to `feature/gamepulse-fusion-web` and `main`.

- [ ] Configure Python setup and dependency install.
- [ ] Configure Node setup with dependency cache.
- [ ] Start an ephemeral Postgres service for Python repository/migration tests.
- [ ] Run Alembic migration, Python tests, compileall, frontend tests and Next.js build.
- [ ] Install Playwright browsers and run E2E against locally started services, using mocked external providers/seed data so CI needs no third-party credentials.
- [ ] Ensure secret-dependent optional tests are skipped explicitly rather than silently passing.
- [ ] Commit with `git commit -m "ci: add GamePulse fusion quality gate"`.

### Task 3: Provision/link Vercel project and Neon Postgres

**Files:**
- Modify: `.env.example`
- Create: `docs/deployment/vercel.md`

**Interfaces:**
- Required production env: `DATABASE_URL`, `CRON_SECRET`.
- Optional production env: `MISTRAL_API_KEY`.
- Deployment authentication env/CI secrets, when CLI automation is used: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`.

- [ ] Inspect whether a Vercel project already exists for the repository; reuse it if appropriate rather than creating duplicates.
- [ ] Prefer Vercel Marketplace Neon provisioning; use an existing external Neon account only if explicitly chosen or Marketplace is unavailable.
- [ ] Verify generated `DATABASE_URL` works from a migration smoke test.
- [ ] Set `CRON_SECRET` to a high-entropy value in Vercel, not in Git.
- [ ] Do not configure `STEAM_WEB_API_KEY`, Twitch credentials or Streams Charts credentials as required production secrets.
- [ ] Document preview/production environment separation in `docs/deployment/vercel.md`.
- [ ] Commit documentation only; never commit `.vercel/project.json` if repo policy excludes it or any secret value.

### Task 4: Run production-schema migration and seed/import

**Files:**
- Modify if necessary: `scripts/migrate_sqlite_to_postgres.py`
- Create: `docs/verification/gamepulse-production-seed.md`

- [ ] Run `alembic upgrade head` against the production/target Postgres using a secure local/CI environment.
- [ ] Run the deterministic SQLite-to-Postgres importer from the available prototype dataset; do not ship the large SQLite file in the Vercel function bundle.
- [ ] Record entity counts for games, tags, genres, review summaries and available historical snapshots.
- [ ] Re-run importer and confirm idempotent counts/no duplicate rows.
- [ ] Sample at least five known Steam App IDs and compare title/artwork/review fields with source SQLite values.
- [ ] Record evidence in `docs/verification/gamepulse-production-seed.md`.
- [ ] Commit only the verification note, not database credentials or raw private payloads.

### Task 5: Create and inspect Vercel preview deployment

**Files:**
- Modify: `docs/verification/gamepulse-preview.md`

- [ ] Deploy the current fusion branch as a Vercel preview using repository Git integration or `vercel deploy`.
- [ ] Capture the exact preview URL/ID in the verification note.
- [ ] Use `vercel inspect`/connector deployment inspection to confirm build status and Python/Next.js functions are present.
- [ ] Verify `/`, `/player`, `/streamer`, `/developer`, one `/games/{appid}` and `/settings` return successful responses.
- [ ] Verify `/api/health` returns `{"status":"ok"}`.
- [ ] Verify wrong/missing cron secret returns 401.
- [ ] Commit the preview verification note with `git commit -m "docs: record GamePulse Vercel preview verification"`.

### Task 6: Perform visual and responsive QA

**Files:**
- Create: `docs/verification/gamepulse-visual-qa.md`
- Modify frontend files only for defects found.

**Acceptance viewports:**
- Mobile: 390x844
- Tablet: 768x1024
- Desktop: 1440x900

- [ ] Verify landing page remains simple: exactly three primary mode cards and no analytics wall.
- [ ] Verify Player/Streamer/Developer each have their own page and clear primary action.
- [ ] Verify game artwork does not stretch, crop critical text unexpectedly or cause layout shift.
- [ ] Verify game-detail summary is visible before deeper analytics.
- [ ] Verify charts have labels/empty states and do not overflow at all three viewports.
- [ ] Verify keyboard focus states and basic screen-reader labels for navigation/forms/buttons.
- [ ] Fix only concrete defects and rerun relevant component/E2E tests.
- [ ] Record screenshots/observations references and results in `docs/verification/gamepulse-visual-qa.md`.
- [ ] Commit fixes with focused messages rather than one broad `cleanup` commit.

### Task 7: Verify failure/degradation behavior on preview

**Files:**
- Create: `docs/verification/gamepulse-failure-modes.md`

- [ ] Simulate stale snapshots and verify UI labels data stale/directional instead of blanking.
- [ ] Simulate SteamSpy failure and verify ownership estimate disappears/degrades without breaking rankings/page.
- [ ] Simulate TwitchTracker failure and verify latest stored streaming snapshot remains usable with lower freshness/confidence.
- [ ] Simulate missing Steam visitor key and verify Player explains limitations/public fallback while Streamer/Developer still work.
- [ ] Simulate Mistral unavailable and verify deterministic Developer brief works.
- [ ] Verify no stack traces, raw provider payloads or secrets appear in browser-visible errors.
- [ ] Record exact outcomes in `docs/verification/gamepulse-failure-modes.md`.

### Task 8: Run secret/privacy and bundle audit

**Files:**
- Create: `docs/verification/gamepulse-security-audit.md`

- [ ] Search built/source outputs for literal test Steam keys, `TWITCH_CLIENT_SECRET`, `STREAMSCHARTS_TOKEN`, `VERCEL_TOKEN` and database passwords; expected no committed/served secret values.
- [ ] Verify browser storage after Player key entry contains no Steam key in localStorage/sessionStorage/cookies/IndexedDB.
- [ ] Verify request logs do not include `X-GamePulse-Steam-Key` value; configure header redaction or avoid request-header logging if necessary.
- [ ] Verify the large prototype SQLite database/raw datasets are absent from the Vercel function bundle according to `.vercelignore`/build inspection.
- [ ] Record results in `docs/verification/gamepulse-security-audit.md`.

### Task 9: Final whole-branch verification and code review

**Files:**
- Create: `docs/verification/gamepulse-final-readiness.md`

- [ ] Run final `python -m pytest -q`.
- [ ] Run final `python -m compileall -q api gamepulse scripts tests`.
- [ ] Run final `npm test -- --run`.
- [ ] Run final `npm run build`.
- [ ] Run final `npx playwright test` against preview where tests support remote base URL.
- [ ] Inspect GitHub CI result for the final commit.
- [ ] Perform broad code review against the approved design spec and all six plan acceptance gates.
- [ ] Record blockers separately from deferred improvements.
- [ ] Mark readiness `READY_TO_PROMOTE` only if there are no load-bearing blockers.
- [ ] Commit with `git commit -m "docs: record GamePulse final readiness"`.

### Task 10: Promote verified preview and perform production smoke check

**Files:**
- Modify: `docs/verification/gamepulse-final-readiness.md`

- [ ] Promote the exact verified preview deployment to production using Vercel promote/Git integration; do not rebuild a different artifact if promotion is available.
- [ ] Smoke-test production Landing, Player, Streamer, Developer, Settings, one Game Detail and `/api/health`.
- [ ] Confirm production cron is registered; do not trigger destructive/full refresh repeatedly.
- [ ] Record production URL/deployment ID and smoke results.
- [ ] Update the Sol parent ledger: O6 `COMPLETE`, with result refs and verification evidence.
- [ ] Cleanup orchestrator-created successful children only if actual child-worker cleanup tools exist; otherwise record cleanup as unavailable.

## Deployment/QA Acceptance Gate

GamePulse Fusion is production-ready only when:

1. O1-O5 acceptance gates are verified.
2. Full Python/frontend/E2E suites and Next.js build pass.
3. CI succeeds without external provider credentials.
4. Production Postgres is migrated/seeded and importer idempotency is proven.
5. Preview deployment is inspected and visually verified at mobile/tablet/desktop sizes.
6. Failure modes degrade gracefully.
7. Steam visitor key does not persist or leak to logs/storage.
8. Twitch/Streams Charts credentials remain unnecessary.
9. Deterministic Developer concept works without Mistral.
10. The exact verified preview artifact is promoted and production smoke checks pass.
