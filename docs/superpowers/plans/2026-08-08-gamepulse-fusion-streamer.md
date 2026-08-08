# GamePulse Fusion Streamer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Streamer Mode as a cold-start simulator for a new/empty channel, with simple and advanced inputs plus selectable Discoverability, Audience Potential and Balanced Growth objectives.

**Architecture:** Port the tested time-window, mapping and opportunity ideas from `agent/gamepulse-twitch-streamer-recommendations`, but remove the assumption that the user already has Twitch history. The service scores cached streaming/Steam evidence from Postgres and returns explainable game/category opportunities. External providers are refreshed by O1 jobs, not called from page renders.

**Tech Stack:** Python scoring services, Postgres repositories, FastAPI, Next.js/React, Recharts, pytest, Vitest, Playwright.

## Global Constraints

- Depends on O1/O2; do not change shared contracts without parent approval.
- No Twitch Client ID/Secret is required.
- No established Twitch account is required.
- Default objective is `balanced_growth`.
- Objective selector values are exactly `discoverability`, `audience_potential`, `balanced_growth`.
- Scores show demand, competition, discoverability/reachability, momentum, stability and fit when available.
- Missing history is unavailable evidence, not fake zero growth.
- Use explicit growth windows; never label arbitrary oldest-to-newest comparisons as 1-day or 7-day growth.

---

### Task 1: Port explicit growth-window helper and reliable mapping primitives

**Files:**
- Create/port: `gamepulse/growth_windows.py`
- Create/port: `gamepulse/game_mapping.py`
- Create: `tests/test_growth_windows_web.py`
- Create: `tests/test_game_mapping_web.py`

**Interfaces:**
- Preserve `calculate_window_growth(..., window="one-day"|"seven-day") -> GrowthComparison`.
- Mapping output must expose Steam App ID, method, confidence/score and reliability flag.

- [ ] Port the tested 18-30 hour one-day and 144-192 hour seven-day baseline tolerances from the streamer branch.
- [ ] Write/port tests proving no baseline outside the tolerance window is used.
- [ ] Port conservative exact/alias/fuzzy Steam-to-streaming category mapping; auto fuzzy mapping is reliable only at the approved threshold used by the existing tested branch (0.90 or higher).
- [ ] Ensure demos/playtests are excluded unless explicitly mapped.
- [ ] Run focused tests; expect PASS.
- [ ] Commit with `git commit -m "feat: port reliable streamer growth and mapping"`.

### Task 2: Define cold-start simulator profile and objective weights

**Files:**
- Create: `gamepulse/services/streamer_simulator.py`
- Create: `gamepulse/web_api/schemas/streamer.py`
- Test: `tests/test_streamer_simulator.py`

**Interfaces:**

```python
StreamerObjective = Literal["discoverability", "audience_potential", "balanced_growth"]

@dataclass(frozen=True)
class ColdStartStreamerProfile:
    objective: StreamerObjective = "balanced_growth"
    preferred_genres: tuple[str, ...] = ()
    preferred_tags: tuple[str, ...] = ()
    languages: tuple[str, ...] = ()
    multiplayer_preference: str | None = None
    competitive_preference: str | None = None
    available_hours: tuple[int, ...] = ()
    hardware_tier: str | None = None
    max_game_price_usd: float | None = None
    content_style: str | None = None
```

- [ ] Write tests proving an empty/default profile is valid and defaults to `balanced_growth`.
- [ ] Define objective weight dictionaries that sum to 1.0:
  - discoverability: prioritize reachability and lower competition;
  - audience potential: prioritize viewer demand and momentum;
  - balanced growth: balance demand, reachability, momentum, competition, stability and fit.
- [ ] Do not include existing-channel follower/viewer history as a required input.
- [ ] Run focused tests; expect PASS.
- [ ] Commit with `git commit -m "feat: define cold-start streamer simulation profile"`.

### Task 3: Build explainable opportunity scoring over cached snapshots

**Files:**
- Modify: `gamepulse/services/streamer_simulator.py`
- Create: `gamepulse/services/streamer_features.py`
- Test: `tests/test_streamer_opportunity_web.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class StreamerOpportunityScore:
    overall: int
    demand: float | None
    reachability: float | None
    momentum: float | None
    competition: float | None
    stability: float | None
    fit: float | None
    confidence: float
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]
```

- [ ] Create fixtures where a massive category with huge channel competition ranks below a smaller rising category under `discoverability`.
- [ ] Create fixtures where the massive category can rank higher under `audience_potential`.
- [ ] Under `balanced_growth`, require a viable demand floor and penalize categories with extreme channel saturation.
- [ ] Use stored 1-day/7-day growth comparisons only when valid; otherwise set momentum unavailable and lower confidence.
- [ ] Use verified Steam mappings to enrich with Steam momentum/genre/tag fit; unreliable mappings cannot contribute Steam evidence.
- [ ] Return at most three reasons and three cautions.
- [ ] Run focused tests; expect PASS.
- [ ] Commit with `git commit -m "feat: score cold-start streaming opportunities"`.

### Task 4: Expose Streamer simulation API

**Files:**
- Create: `gamepulse/web_api/routes/streamer.py`
- Modify: `gamepulse/web_api/app.py`
- Test: `tests/test_streamer_api.py`

**Interfaces:**
- `POST /streamer/simulate`
- Request contains the simple/advanced profile fields and objective.
- Response contains ranked games/categories, breakdown, source/freshness/confidence and mapped Steam App IDs where reliable.

- [ ] Write API tests for default request, each objective, invalid objective and sparse-history fallback.
- [ ] Implement route using Postgres repositories and `StreamerSimulator`; it must not call TwitchTracker/Steam live during the request.
- [ ] Filter out non-game categories that cannot serve the Steam/PC v1 objective unless they are explicitly supported by the catalog policy.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: expose Streamer simulator API"`.

### Task 5: Build simple Streamer page and objective switcher

**Files:**
- Create: `src/app/streamer/page.tsx`
- Create: `src/features/streamer/streamer-form.tsx`
- Create: `src/features/streamer/objective-switcher.tsx`
- Create: `src/features/streamer/streamer-api.ts`
- Test: `src/features/streamer/streamer-form.test.tsx`

**Interfaces:**
- Simple form exposes genres, casual/competitive, solo/multiplayer and language/region without requiring any field except submit.
- Objective switcher labels: `Discoverability`, `Audience Potential`, `Balanced Growth`.

- [ ] Write tests proving Balanced Growth is selected by default.
- [ ] Implement a clean form with a single `Advanced simulator` disclosure rather than showing every control at once.
- [ ] Do not show Twitch login/channel URL input in v1.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: build Streamer cold-start simulator form"`.

### Task 6: Build Advanced Simulator controls

**Files:**
- Create: `src/features/streamer/advanced-controls.tsx`
- Modify: `src/features/streamer/streamer-form.tsx`
- Test: `src/features/streamer/advanced-controls.test.tsx`

- [ ] Add optional available streaming hours, language/region, hardware tier, game budget and content style.
- [ ] Ensure collapsed state does not remove previously entered values until the user explicitly resets them.
- [ ] Keep all fields optional and validate budget as non-negative.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: add advanced Streamer simulation inputs"`.

### Task 7: Render ranked opportunities with focused evidence

**Files:**
- Create: `src/features/streamer/streamer-results.tsx`
- Create: `src/features/streamer/opportunity-breakdown.tsx`
- Create: `src/features/streamer/streaming-evidence-chart.tsx`
- Modify: `src/app/streamer/page.tsx`
- Test: `src/features/streamer/streamer-results.test.tsx`

- [ ] Reuse shared `GameCard` for mapped games.
- [ ] Show overall opportunity score plus compact Demand, Competition, Discoverability, Momentum, Fit breakdown.
- [ ] Render one focused trend chart for the selected/recommended item, not charts on every card.
- [ ] Show `insufficient history` rather than fabricated growth when no valid baseline exists.
- [ ] Display source/freshness/confidence near the evidence.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: render Streamer opportunity recommendations"`.

### Task 8: Add Streamer E2E regression

**Files:**
- Create: `e2e/streamer.spec.ts`

- [ ] Test Landing -> Streamer -> default simulation -> results.
- [ ] Switch between all three objectives and assert result explanation label updates.
- [ ] Open Advanced Simulator, set optional controls, rerun and confirm request payload.
- [ ] Click a mapped game and verify internal GamePulse detail route.
- [ ] Run:
  - `python -m pytest tests/test_growth_windows_web.py tests/test_game_mapping_web.py tests/test_streamer_simulator.py tests/test_streamer_opportunity_web.py tests/test_streamer_api.py -q`
  - `npm test -- src/features/streamer`
  - `npx playwright test e2e/streamer.spec.ts`
  - `npm run build`
- [ ] Commit with `git commit -m "test: verify Streamer cold-start workflow"`.

## Streamer Acceptance Gate

Parent verifies:

1. No Twitch credentials or established channel are required.
2. Balanced Growth is the default and all three objectives work.
3. Discoverability can prefer a smaller category over a saturated giant category.
4. Growth labels use explicit valid time windows only.
5. Steam evidence contributes only through reliable mappings.
6. Source/freshness/confidence is visible.
7. Mapped games route to internal detail pages.
8. Python/frontend/E2E tests pass.
