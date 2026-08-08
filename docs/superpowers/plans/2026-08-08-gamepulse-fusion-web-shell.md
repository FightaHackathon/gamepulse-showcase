# GamePulse Fusion Web Shell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the approved clean GamePulse visual system, landing page, shared game cards, API client, source/freshness UI, and reusable game-detail experience.

**Architecture:** Next.js App Router owns presentation only. Shared components consume typed API responses from the FastAPI read endpoints created by O1. No mode-specific ranking logic belongs in shared UI.

**Tech Stack:** Next.js, React, TypeScript, Tailwind CSS, Recharts, Vitest, React Testing Library, Playwright.

## Global Constraints

- O1 foundation interfaces are frozen unless the parent approves a contract change.
- Landing page has exactly three primary mode choices.
- Player, Streamer and Developer remain separate pages.
- Game cards are image-first and clicking a card routes internally to `/games/[steamAppId]`.
- Game detail summary appears before deeper charts.
- Dark-mode-first, spacious, restrained purple/violet accent, minimal animation.
- Do not put dense analytics on the landing page.
- Every displayed external metric can surface source, freshness and confidence.

---

### Task 1: Create design tokens, app shell and navigation

**Files:**
- Create: `src/components/app-shell.tsx`
- Create: `src/components/sidebar-nav.tsx`
- Create: `src/components/ui/card.tsx`
- Create: `src/components/ui/button.tsx`
- Create: `src/components/ui/badge.tsx`
- Create: `src/components/ui/skeleton.tsx`
- Create: `src/lib/cn.ts`
- Modify: `src/app/globals.css`
- Modify: `src/app/layout.tsx`
- Test: `src/components/app-shell.test.tsx`

**Interfaces:**
- `AppShell({children})` renders brand + Home/Player/Streamer/Developer + Settings/About.
- Reusable `Card`, `Button`, `Badge`, `Skeleton` components expose className and standard HTML props.

- [ ] Write a failing test asserting the shell contains exactly the six navigation destinations and `GAMEPULSE` branding.
- [ ] Run `npm test -- src/components/app-shell.test.tsx` and confirm failure.
- [ ] Implement shell/tokens with accessible focus states and no dashboard widgets.
- [ ] Run the focused test and `npm run build`; expect PASS.
- [ ] Commit with `git commit -m "feat: add GamePulse web design shell"`.

### Task 2: Build simple landing page

**Files:**
- Create: `src/components/mode-card.tsx`
- Modify: `src/app/page.tsx`
- Test: `src/app/page.test.tsx`

**Interfaces:**
- `ModeCard` accepts `{title, description, href, iconName}`.

- [ ] Write a failing test that the page has exactly three primary cards labelled `Player`, `Streamer`, and `Developer` and links to `/player`, `/streamer`, `/developer`.
- [ ] Implement concise hero copy plus the three cards; do not add trends, KPIs or charts.
- [ ] Run focused test and build; expect PASS.
- [ ] Commit with `git commit -m "feat: build simple GamePulse landing page"`.

### Task 3: Add typed frontend API client and shared metric metadata

**Files:**
- Create: `src/lib/api/types.ts`
- Create: `src/lib/api/client.ts`
- Create: `src/components/source-meta.tsx`
- Test: `src/lib/api/client.test.ts`
- Test: `src/components/source-meta.test.tsx`

**Interfaces:**

```ts
export type MetricValue = {
  metric: string;
  value: number | string | null;
  observed_at: string;
  source_name: string;
  source_mode: string;
  confidence: string;
  freshness_seconds?: number | null;
};

export async function getGame(appId: number): Promise<GameDetail>;
export async function getGameHistory(appId: number, metric: string): Promise<MetricPoint[]>;
export async function getSourceStatus(): Promise<SourceStatus[]>;
```

- [ ] Write fetch-mocked tests for success, 404 and 503 responses.
- [ ] Implement a single `apiFetch<T>` wrapper that throws typed `ApiError` with HTTP status and safe message.
- [ ] Implement `SourceMeta` showing source, relative/absolute freshness and confidence without exposing raw provider payloads.
- [ ] Run focused tests; expect PASS.
- [ ] Commit with `git commit -m "feat: add typed GamePulse API client"`.

### Task 4: Create reusable image-first game card

**Files:**
- Create: `src/components/game-card.tsx`
- Create: `src/components/game-image.tsx`
- Create: `src/app/games/[steamAppId]/loading.tsx`
- Test: `src/components/game-card.test.tsx`

**Interfaces:**
- `GameCard` accepts `steamAppId`, `name`, `headerImageUrl`, `primaryScore`, `supportingMetrics` (max 2), `reason`.
- Card root routes to `/games/${steamAppId}`.

- [ ] Write tests proving only two supporting metrics render, image fallback works, and card href is internal.
- [ ] Implement with `next/image`, configured Steam image hosts, responsive sizes and branded fallback.
- [ ] Ensure no direct Steam redirect occurs on card click.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: add reusable game discovery cards"`.

### Task 5: Build game-detail summary route

**Files:**
- Create: `src/app/games/[steamAppId]/page.tsx`
- Create: `src/components/game-detail/hero.tsx`
- Create: `src/components/game-detail/key-metrics.tsx`
- Create: `src/app/games/[steamAppId]/not-found.tsx`
- Create: `src/app/games/[steamAppId]/error.tsx`
- Test: `src/app/games/[steamAppId]/page.test.tsx`

**Interfaces:**
- Server page consumes `getGame(Number(params.steamAppId))`.
- `View on Steam` links to `https://store.steampowered.com/app/{appId}` in a new tab with safe rel attributes.

- [ ] Write tests for title/artwork/review/price/current activity/trend summary and Steam button.
- [ ] Implement top summary with no more than four headline metrics.
- [ ] Implement explicit 404 and API-error states.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: add GamePulse game detail summary"`.

### Task 6: Add deep-analysis sections and focused charts

**Files:**
- Create: `src/components/charts/time-series-chart.tsx`
- Create: `src/components/game-detail/player-activity.tsx`
- Create: `src/components/game-detail/streaming-trend.tsx`
- Create: `src/components/game-detail/review-breakdown.tsx`
- Create: `src/components/game-detail/market-position.tsx`
- Modify: `src/app/games/[steamAppId]/page.tsx`
- Test: `src/components/charts/time-series-chart.test.tsx`

**Interfaces:**
- `TimeSeriesChart` accepts one primary series plus optional comparison series; it never silently interpolates missing points.

- [ ] Write chart test verifying ordered points, empty-state rendering and accessible label.
- [ ] Implement each analysis section independently; one primary chart per section.
- [ ] Add source/freshness metadata adjacent to derived values.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: add focused game analytics sections"`.

### Task 7: Add Settings and About shells

**Files:**
- Create: `src/app/settings/page.tsx`
- Create: `src/app/about/page.tsx`
- Create: `src/components/source-status-list.tsx`
- Test: `src/app/settings/page.test.tsx`

**Interfaces:**
- Settings displays source readiness/status from `/status/sources`.
- Steam key input is intentionally deferred to O3 because Player owns the runtime-memory key contract.

- [ ] Write a test asserting no Twitch Client ID/Secret or Streams Charts fields exist.
- [ ] Implement source status list with ready/degraded/stale states.
- [ ] Add About page explaining Player/Streamer/Developer roles and estimate disclaimers.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: add GamePulse settings and about pages"`.

## Web Shell Acceptance Gate

Parent verifies:

1. Landing page has exactly three primary mode cards and no analytics wall.
2. Navigation is consistent and responsive.
3. Game card click remains inside GamePulse.
4. Game detail summary renders before analytics sections.
5. `View on Steam` is explicit and safe.
6. Empty/stale/error states exist.
7. No Twitch/Streams Charts credential fields appear.
8. `npm test` and `npm run build` pass.
