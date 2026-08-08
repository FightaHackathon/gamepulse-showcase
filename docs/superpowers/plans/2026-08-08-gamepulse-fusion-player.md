# GamePulse Fusion Player Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Player Mode so a user can paste a Steam profile URL, optionally provide a session-only Steam Web API key, receive ranked owned-library suggestions, and discover new Steam games with explainable scores.

**Architecture:** Reuse `gamepulse/providers/steam.py` profile/library resolution and `gamepulse/player_profile.py` preference inference, but wrap them in a UI-agnostic Player service that consumes Postgres repositories rather than opening SQLite directly. The browser owns the visitor key in React runtime memory and sends it only on Player API calls via an ephemeral request header.

**Tech Stack:** FastAPI, Pydantic, existing Steam provider logic, Postgres repositories, Next.js/React, TypeScript, Vitest, pytest.

## Global Constraints

- Depends on O1 and O2 frozen shared contracts.
- Player output has exactly two primary result groups: `Play Next From Your Library` and `Discover Something New`.
- Ranking balances personal fit, review quality, current activity and trend momentum.
- Explainability shows normalized factor scores plus final score.
- Steam API key is optional and runtime-memory-only.
- No key may be persisted in localStorage, sessionStorage, cookies, Postgres, logs, analytics or committed files.
- Public Steam profile fallback remains usable when possible without an API key.

---

### Task 1: Define Player recommendation contracts and service

**Files:**
- Create: `gamepulse/services/player_recommendations.py`
- Create: `gamepulse/web_api/schemas/player.py`
- Test: `tests/test_player_recommendation_service.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class PlayerScoreBreakdown:
    personal_fit: float
    review_quality: float
    current_activity: float
    trend_momentum: float

@dataclass(frozen=True)
class PlayerRecommendationResult:
    app_id: int
    name: str
    score: int
    breakdown: PlayerScoreBreakdown
    reasons: tuple[str, ...]
    owned: bool

class PlayerRecommendationService:
    def recommend(self, library: PlayerLibrary, limit_owned: int = 10, limit_discovery: int = 10) -> tuple[list[PlayerRecommendationResult], list[PlayerRecommendationResult]]: ...
```

- [ ] Write failing tests proving owned games never appear in discovery results, discovery never returns already-owned App IDs, and score is 0-100.
- [ ] Add a fixture where a personally relevant game with strong reviews outranks a more popular unrelated game.
- [ ] Implement normalization helpers for each score factor and explicit weights summing to 1.0. Initial v1 weights: personal fit `0.45`, review quality `0.20`, current activity `0.15`, trend momentum `0.20`.
- [ ] If a factor is unavailable, re-normalize remaining available weights rather than treating missing data as zero.
- [ ] Generate up to three concise reasons from the strongest factor evidence.
- [ ] Run `python -m pytest tests/test_player_recommendation_service.py -q`; expect PASS.
- [ ] Commit with `git commit -m "feat: add explainable Player recommendation service"`.

### Task 2: Add Player profile analysis API with ephemeral key header

**Files:**
- Create: `gamepulse/web_api/routes/player.py`
- Modify: `gamepulse/web_api/app.py`
- Test: `tests/test_player_api.py`
- Test: `tests/test_player_secret_handling.py`

**Interfaces:**
- `POST /player/analyze`
- Request JSON: `{ "profile_url": string }`
- Optional header: `X-GamePulse-Steam-Key: <visitor key>`
- Response: profile summary, `library_complete`, `source_name`, `owned_recommendations[]`, `discovery_recommendations[]`.

- [ ] Write a failing API test using a mocked `SteamProvider` and fake repository.
- [ ] Write a secret-handling test that asserts the provided key does not appear in response JSON, exception strings, captured logs, settings objects or repository calls.
- [ ] Implement header extraction with `Header(default=None, alias="X-GamePulse-Steam-Key")` and construct `SteamProvider(api_key=steam_key)` inside request scope.
- [ ] Use `resolve_profile()` and `get_library()` from the existing provider.
- [ ] Map private/unavailable profile errors to safe 422/503 responses without echoing the key.
- [ ] Run focused tests; expect PASS.
- [ ] Commit with `git commit -m "feat: expose Player profile analysis API"`.

### Task 3: Add runtime-memory Steam key store

**Files:**
- Create: `src/features/player/steam-key-context.tsx`
- Create: `src/features/player/steam-key-input.tsx`
- Modify: `src/app/settings/page.tsx`
- Test: `src/features/player/steam-key-context.test.tsx`
- Test: `src/app/settings/page.test.tsx`

**Interfaces:**
- `useSteamKey(): { steamKey: string; setSteamKey(value: string): void; clearSteamKey(): void }`
- Storage is React state only.

- [ ] Write a test that setting the key updates the context and clearing removes it.
- [ ] Mock `window.localStorage.setItem`, `sessionStorage.setItem`, and `document.cookie`; assert none are called.
- [ ] Implement provider with `useState("")`; do not initialize from browser storage.
- [ ] Add Settings card labelled `Steam Web API Key` with `Used only for this page session` copy and Clear action.
- [ ] Ensure no Twitch or Streams Charts credential fields are added.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: add session-only Steam key setting"`.

### Task 4: Build Player input flow

**Files:**
- Create: `src/app/player/page.tsx`
- Create: `src/features/player/player-form.tsx`
- Create: `src/features/player/player-api.ts`
- Create: `src/app/player/loading.tsx`
- Test: `src/features/player/player-form.test.tsx`

**Interfaces:**
- `analyzePlayer(profileUrl: string, steamKey?: string): Promise<PlayerAnalysisResponse>`.

- [ ] Write form tests for valid Steam profile URL, vanity URL, empty input and API-error display.
- [ ] Implement a clean single-input primary flow with optional key status indicator, not a large onboarding form.
- [ ] On submit, pass the runtime-memory key only as request header.
- [ ] Show meaningful states: analyzing, profile private/unavailable, rate limited, partial public-library fallback.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: add Player Steam profile flow"`.

### Task 5: Build owned and discovery result sections

**Files:**
- Create: `src/features/player/player-results.tsx`
- Create: `src/features/player/score-breakdown.tsx`
- Modify: `src/app/player/page.tsx`
- Test: `src/features/player/player-results.test.tsx`

**Interfaces:**
- Reuse shared `GameCard` from O2.
- Player card primary score is overall recommendation score; supporting metrics are selected from review/activity/momentum.

- [ ] Write a test that the two section headings render separately and owned items do not leak into discovery.
- [ ] Implement compact score breakdown for Personal fit, Review quality, Current activity and Trend momentum.
- [ ] Game card click must continue to internal GamePulse game detail.
- [ ] Add profile data-source note (`Steam Web API`, `Public Steam games page`, or partial public profile fallback).
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: render Player recommendations"`.

### Task 6: Add Player regression and privacy tests

**Files:**
- Create: `tests/test_player_end_to_end_contract.py`
- Create: `e2e/player.spec.ts`

- [ ] Add backend contract test covering numeric SteamID, vanity URL resolution, complete API library and public partial fallback.
- [ ] Add Playwright flow: Landing -> Player -> profile URL -> results -> click game -> internal detail -> `View on Steam` present.
- [ ] Add browser test asserting refresh resets the key and no relevant storage key exists.
- [ ] Run:
  - `python -m pytest tests/test_player_recommendation_service.py tests/test_player_api.py tests/test_player_secret_handling.py tests/test_player_end_to_end_contract.py -q`
  - `npm test -- src/features/player src/app/settings`
  - `npx playwright test e2e/player.spec.ts`
  - `npm run build`
- [ ] Commit with `git commit -m "test: verify Player Mode and secret privacy"`.

## Player Acceptance Gate

Parent verifies:

1. A public Steam profile can be analyzed without requiring Twitch credentials.
2. API key, when supplied, exists only in browser runtime memory/request scope.
3. No key appears in logs, response payloads, Postgres or browser persistence.
4. Owned and discovery outputs are separate and mutually exclusive by App ID.
5. Recommendation score exposes all four approved factors.
6. Missing activity/trend data reduces confidence/available factors without unfairly zeroing the game.
7. Game cards route internally to GamePulse detail pages.
8. Focused Python, frontend and Playwright tests pass.
