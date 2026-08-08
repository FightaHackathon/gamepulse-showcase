# GamePulse Fusion Web Orchestration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `sol-chat-orchestrator` when native child-worker/chat capabilities exist. Each implementation worker must also follow the relevant Superpowers plan/task discipline. Never claim a worker exists unless a tool proves it.

**Goal:** Build the approved GamePulse Fusion Web application by integrating the strongest tested logic from the existing branches into a clean Next.js + Python API + Postgres application deployable on Vercel.

**Architecture:** `main` is the only Git base. The compatible streamer branch is a source of tested logic; the unrelated TwitchTracker/SteamSpy branch is a source of selectively ported modules and patterns only. The public UI is rebuilt in Next.js, analytics remain in Python behind FastAPI, and durable snapshots live in Postgres.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, Recharts, FastAPI, Pydantic, SQLAlchemy 2.x, psycopg 3, Postgres/Neon, pytest, Vitest/React Testing Library, Playwright, Vercel Functions and Vercel Cron.

## Global Constraints

- v1 supports Steam/PC only.
- No login is required.
- Landing page has exactly three primary choices: Player, Streamer, Developer.
- Player, Streamer, and Developer are separate pages/workspaces.
- Clicking a game opens an internal `/games/[steamAppId]` page; Steam is reached from a `View on Steam` button.
- UI is clean, image-first, dark-mode-first, spacious, and restrained; no dense all-mode dashboard.
- Twitch Client ID/secret and Streams Charts credentials are not required and are not shown in normal Settings UI.
- User-supplied Steam Web API keys exist only in browser runtime memory and must not be persisted to Postgres, localStorage, sessionStorage, cookies, logs, analytics, or committed files.
- Normal page reads use cached Postgres snapshots.
- Every external metric retains source, observed-at timestamp, freshness, and confidence metadata.
- SteamSpy ownership is an estimate and must never be labelled as exact sales.
- SteamDB is manual validation/reference only unless explicit permission for automated access is obtained.
- Provider failures degrade individual metrics and use the latest valid snapshot when possible; they must not blank entire pages.
- Generated Developer concepts are visually separated from market evidence and have a deterministic non-LLM fallback.
- Work starts from `feature/gamepulse-fusion-web`; do not merge `codex/twitchtracker-steamspy-estimates` wholesale.

---

## Sol Orchestrator Capability Gate

The `sol-chat-orchestrator` skill requires tools for create/spawn worker, send task, read status/result, retry, and close/delete. Before execution, the parent must inspect the active environment for those capabilities.

- If native child-worker tools exist: use the worker graph below.
- If they do not exist: report that limitation. Do not invent workers or fake parallel execution.
- Logical in-chat workers may be used only after explicit user acceptance of that fallback.
- Successful child cleanup is allowed only for children created by this orchestrator and only after essential output and verification evidence have been copied into the parent ledger.

## Dependency Graph

```text
O1 Foundation / Data / API
          |
          v
O2 Shared Web Shell + Game Details
          |
          +-------------------+-------------------+
          |                   |                   |
          v                   v                   v
     O3 Player           O4 Streamer         O5 Developer
          \                   |                   /
           \                  |                  /
            +-----------------+-----------------+
                              |
                              v
                    O6 Deployment + QA
```

## Workstream Contracts

### O1 — Foundation / Data / API

**Objective:** Establish the new web/API runtime, Postgres schema, migration path, provider contracts, snapshot repository, and stable API health/data-source surfaces.

**Inputs:** Approved design spec; `main`; selected provider patterns from `codex/twitchtracker-steamspy-estimates`; existing SQLite schema/data.

**Dependencies:** None.

**Allowed scope:** Build/runtime configuration, Python API, database abstractions, migrations, provider contracts, snapshot persistence, baseline CI.

**Must not:** Implement final Player/Streamer/Developer pages or port desktop UI.

**Acceptance:** Next.js and FastAPI build locally; Postgres migrations run; seed migration produces canonical game records; provider tests prove stale/failure fallback; no secret persistence.

**Plan:** `docs/superpowers/plans/2026-08-08-gamepulse-fusion-foundation.md`

### O2 — Shared Web Shell + Game Details

**Objective:** Create the approved visual system, landing page, global navigation, reusable game cards, shared API client, and `/games/[steamAppId]` summary/deep-analysis page.

**Inputs:** O1 API/database contracts.

**Dependencies:** O1.

**Allowed scope:** Shared frontend components/routes, game-detail read APIs, common chart/source/freshness UI.

**Must not:** Implement mode-specific ranking engines.

**Acceptance:** Landing page contains only the three mode cards; cards are image-first; game detail opens internally and exposes `View on Steam`; loading/error/stale states are tested.

**Plan:** `docs/superpowers/plans/2026-08-08-gamepulse-fusion-web-shell.md`

### O3 — Player

**Objective:** Deliver Steam-profile Player Mode with two outputs: owned-library ranking and new-game discovery.

**Inputs:** O1 API/data; O2 shared UI; existing `player_profile.py`, Steam provider, recommendation logic.

**Dependencies:** O1, O2.

**Allowed scope:** Player analytics service/API/UI/tests and session-only Steam key handling.

**Acceptance:** Steam URL + runtime-memory key can load a public library; owned and discovery sections are separate; scores expose personal fit, review quality, activity, and momentum; no key persistence occurs.

**Plan:** `docs/superpowers/plans/2026-08-08-gamepulse-fusion-player.md`

### O4 — Streamer

**Objective:** Deliver a cold-start streamer simulator that does not require an established Twitch channel.

**Inputs:** O1/O2; `agent/gamepulse-twitch-streamer-recommendations` growth/mapping/opportunity logic; no-key streaming sources/snapshots.

**Dependencies:** O1, O2.

**Allowed scope:** Streamer scoring, inputs, data normalization, API, UI and tests.

**Acceptance:** Simple and Advanced simulator modes work; objective selector supports Discoverability, Audience Potential and Balanced Growth; zero-audience ranking is explainable; Twitch credentials are unnecessary.

**Plan:** `docs/superpowers/plans/2026-08-08-gamepulse-fusion-streamer.md`

### O5 — Developer

**Objective:** Deliver market dashboard -> opportunity -> direction -> mini game brief.

**Inputs:** O1/O2; existing market/forecast/review logic; selectively ported developer intelligence and SteamSpy/public-signal helpers.

**Dependencies:** O1, O2.

**Allowed scope:** Developer opportunity engine, evidence APIs, concept generator/fallback, UI and tests.

**Acceptance:** Market evidence is separate from generated ideas; opportunity cards are explainable; mini brief has the approved fields; no-LLM fallback works; no sales guarantees are shown.

**Plan:** `docs/superpowers/plans/2026-08-08-gamepulse-fusion-developer.md`

### O6 — Deployment + QA

**Objective:** Integrate all workstreams, configure production caching/cron/secrets, run complete tests and visual QA, deploy a Vercel preview, then promote only after verification.

**Inputs:** O1-O5.

**Dependencies:** O3, O4, O5 complete and reviewed.

**Allowed scope:** Integration fixes, CI, Vercel config, cron, environment docs, E2E, accessibility/performance, preview deployment and promotion.

**Acceptance:** All required test suites pass; preview URL is verified; no secret leaks; cached-data failure cases work; production promotion is based on the verified preview artifact.

**Plan:** `docs/superpowers/plans/2026-08-08-gamepulse-fusion-deployment-qa.md`

## Orchestrator Scheduling

1. Run O1 alone because it defines shared interfaces.
2. Run O2 after O1 and freeze the shared game/API presentation contracts.
3. When native isolated child workers exist, O3/O4/O5 may be delegated independently because their mode-specific files must not overlap. Each worker must consume the frozen shared interfaces and must not edit another mode's files.
4. Parent verifies each workstream's acceptance checks before marking `COMPLETE`.
5. O6 runs only after all three mode workstreams are verified.
6. On `BLOCKED`/`FAILED`, attempt up to two parent remediation cycles. If unresolved, stop dependent tasks and report the smallest decision/input required.

## Worker Return Contract

Every delegated worker must return one of:

- `COMPLETE`
- `BLOCKED`
- `FAILED`

And include:

- concise summary;
- files/commits changed;
- exact validation commands and outcomes;
- concerns/limitations;
- error details when blocked/failed.

`COMPLETE` is provisional until the parent independently verifies its acceptance checks.

## Parent Integration Rules

- No simultaneous worker edits to shared files such as `package.json`, `requirements.txt`, `vercel.json`, `gamepulse/config.py`, database migrations, root layout, or shared API contracts.
- O1/O2 own shared files. O3/O4/O5 must request parent integration for a shared-contract change instead of editing it independently.
- Preserve provenance and confidence fields end-to-end.
- Prefer focused cherry-pick/porting over merge commits from the unrelated Codex branch.
- Run focused tests after every workstream and the entire suite during O6.

## Completion Definition

GamePulse Fusion is complete only when:

1. the three audience flows work from the landing page;
2. game cards and game-detail routes use real Steam imagery and internal navigation;
3. Player recommendations produce both owned and discovery results with explainable factors;
4. Streamer simulation works for a zero-audience channel with no Twitch credentials;
5. Developer mode progresses from market evidence to an explicitly generated mini brief;
6. Postgres-backed snapshots provide source/freshness/confidence metadata and safe fallbacks;
7. the session Steam key is demonstrably not persisted;
8. automated tests and E2E flows pass;
9. a Vercel preview is verified before production promotion;
10. the parent ledger records all workstream results and actual cleanup status.
