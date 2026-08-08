# GamePulse Fusion Web — Design Specification

**Date:** 2026-08-08  
**Status:** Approved design  
**Target branch:** `feature/gamepulse-fusion-web`  
**Production target:** Vercel  

## 1. Product objective

GamePulse becomes a clean, public, Steam/PC-focused web application that helps three distinct audiences answer three distinct questions:

- **Player:** What should I play next?
- **Streamer:** What should I stream as a new or zero-audience channel?
- **Developer:** What game opportunity should I explore, and what evidence supports it?

The public application must preserve the strongest recommendation, trend, mapping, and market-analysis logic already present across the existing repository branches while replacing the Streamlit/native-desktop presentation with a dedicated web frontend.

The first release is deliberately focused on Steam/PC. Console and mobile support are out of scope.

## 2. Design principles

1. **One audience, one page.** Player, Streamer, and Developer are separate workspaces.
2. **Simple first, depth on demand.** Summary cards and recommendations appear before detailed charts.
3. **Evidence before generated ideas.** Market facts, derived scores, and AI-generated concepts are visually and semantically separated.
4. **No required Twitch or Streams Charts credentials.** The product must remain useful without them.
5. **Cached by default.** Normal page loads read normalized snapshots from Postgres instead of waiting for multiple third-party providers.
6. **Graceful degradation.** One failed provider must never blank or crash a page.
7. **Explainable scores.** Recommendations expose the important score factors and concise reasons.
8. **Real game presentation.** Use Steam artwork and metadata instead of spreadsheet-like rows.
9. **No login in v1.** The shareable Vercel deployment is immediately usable.
10. **Session-only user secrets.** A user-supplied Steam Web API key must not be persisted.

## 3. Repository fusion strategy

The implementation must not perform a blind multi-branch merge.

### 3.1 Base

Create all production work from `main`.

`main` remains the source for the stable Player foundation, existing curated/localized presentation ideas, recommendation/forecasting foundations, game details, market analysis, and current prototype dataset.

### 3.2 Streamer branch inputs

Selectively port the useful logic from:

`agent/gamepulse-twitch-streamer-recommendations`

High-value candidates include:

- `gamepulse/growth_windows.py`
- `gamepulse/game_mapping.py`
- `gamepulse/creator_aggregation.py`
- expanded `streamer_fit.py`
- expanded `streamer_opportunity.py`
- Twitch/Steam alias mapping data
- snapshot collection logic
- provider/growth/mapping/provenance tests

This branch is compatible with `main` history and should be treated as the strongest existing source of tested streamer logic.

### 3.3 SteamSpy/developer branch inputs

Selectively port useful concepts and code from:

`codex/twitchtracker-steamspy-estimates`

This branch must **not** be merged wholesale because it has unrelated Git history and replaces the web prototype entry point with a native desktop application.

Candidates to port or adapt include:

- provider contracts and composition patterns
- provider caching patterns
- SteamSpy integration
- Steam public-signal helpers
- developer intelligence logic
- developer prediction logic
- source/confidence metadata patterns

The following must not become the public application architecture:

- native desktop UI
- monolithic desktop app
- credential-dependent streamer behavior
- crowded desktop presentation

### 3.4 Conflict rule

When branches contain competing implementations, priority is:

1. behavior required by this specification;
2. tested domain logic that can be isolated from UI;
3. `main` compatibility;
4. simpler implementation.

No old UI is preserved merely because it already exists.

## 4. Public information architecture

### 4.1 Landing page

The first page contains a short GamePulse introduction and exactly three primary mode choices:

- **Player — Find what to play**
- **Streamer — Find what to stream**
- **Developer — Find what to build**

The landing page must not contain dense market dashboards or multiple charts.

Global navigation:

- Home
- Player
- Streamer
- Developer
- Settings
- About

### 4.2 Shared game cards

Game cards are image-first and use Steam artwork when available.

Default card content is limited to:

- image
- game title
- one primary score or status
- at most two supporting metrics
- short recommendation/trend reason

Clicking a card opens the internal GamePulse game-detail page. It does not immediately redirect to Steam.

## 5. Player mode

### 5.1 Input

Primary input is a Steam profile URL.

Steam-profile personalization is unlocked with a user-provided Steam Web API key when required by the Steam endpoint. The key is session-only.

### 5.2 Output sections

#### Play Next From Your Library

Ranks games already owned by the player.

#### Discover Something New

Ranks catalog games the user does not own but is likely to enjoy.

### 5.3 Ranking objective

Player recommendations balance:

- personal fit from library/playtime patterns
- genre/tag similarity
- review quality
- current player activity
- trend momentum

Popularity alone must not dominate personal fit.

### 5.4 Explainability

Each recommendation displays an overall score and compact factor breakdown, for example:

- Personal fit
- Review quality
- Current activity
- Trend momentum
- Overall recommendation score

The exact weights may differ by available data, but the scoring service must expose normalized factor scores and the final weighted score so the frontend can explain the result.

## 6. Streamer mode

### 6.1 Purpose

Streamer mode is a **cold-start simulator** for a new or empty channel. It must not require an established Twitch account or historical channel analytics.

### 6.2 Simple simulator

The default form may include:

- preferred genres
- casual vs competitive preference
- solo vs multiplayer preference
- language/region

All are optional except the action to run the simulation.

### 6.3 Advanced simulator

Advanced inputs can include:

- available streaming hours
- language/region
- hardware constraints
- game budget
- preferred game types
- content style

### 6.4 Optimization objective

The user can switch between:

- **Discoverability**
- **Audience Potential**
- **Balanced Growth**

Default: **Balanced Growth**.

The opportunity engine considers, where available:

- viewer demand
- number of competing channels
- viewer-to-channel ratio
- category growth
- Steam player momentum
- game fit
- volatility/stability

A large Twitch category may legitimately rank below a smaller category if a zero-audience creator is likely to be buried by competition.

### 6.5 Output

Streamer recommendations must include:

- ranked games/categories
- opportunity score
- compact breakdown of demand, competition, discoverability, momentum, and fit
- short explanation
- visible data freshness and confidence

The page should show a small number of high-value charts rather than a dense analytics wall.

## 7. Developer mode

Developer mode uses a progressive evidence-to-concept flow.

### 7.1 Stage 1 — Market dashboard

Show concise evidence for:

- rising genres
- rising tags/mechanics
- Steam player momentum
- streaming demand
- release saturation
- review sentiment
- ownership estimates where available
- price bands

### 7.2 Stage 2 — Opportunity cards

Each opportunity includes:

- market segment label
- opportunity score
- demand indicator
- competition/saturation indicator
- streaming fit
- confidence
- concise evidence summary

### 7.3 Stage 3 — Explore opportunity

Opening an opportunity shows supporting games, charts, source data, risks, and why the opportunity was detected.

### 7.4 Stage 4 — Suggest direction

GamePulse may translate the evidence into a product direction, but it must clearly label the direction as a recommendation rather than market fact.

### 7.5 Stage 5 — Generate mini game brief

The generated brief includes:

- working concept/name
- genre and subgenre
- core gameplay loop
- 3–5 key mechanics
- target players
- solo/multiplayer structure
- suggested Steam price band
- comparable Steam games
- market opportunity score
- saturation/risk summary
- evidence-backed rationale

A full production roadmap, team plan, or detailed commercial forecast is out of scope for v1.

## 8. Game-detail page

Route pattern:

`/games/[steamAppId]`

### 8.1 Summary section

The top of the page stays visually simple and includes:

- large Steam artwork/header
- title
- short description
- current price when available
- review summary
- current/recent player activity
- concise trend state
- **View on Steam** button

### 8.2 Deeper analysis

Below the fold, add focused sections for:

- Steam player activity chart
- streaming trend chart
- review breakdown
- market position / ownership estimates
- genre/tags
- similar/comparable games
- recommendation reason

When the page was opened from a Player, Streamer, or Developer recommendation, mode-specific explanation may be shown without changing the core game record.

## 9. Visual design system

The approved direction is clean and restrained, not a dense analytics terminal.

### 9.1 Layout rules

- generous whitespace
- large content cards
- clear section hierarchy
- one primary chart per analytical section where practical
- responsive desktop/tablet/mobile layouts
- image-first game presentation
- subtle hover/focus states
- skeleton loaders for network data
- no giant all-modes dashboard

### 9.2 Style

- modern dark-mode-first product aesthetic
- restrained purple/violet accent
- high contrast text
- minimal decorative gradients
- consistent rounded card surfaces
- restrained animation

The design should feel closer to a modern game discovery product plus analytics than to a BI terminal.

## 10. Web architecture

### 10.1 Frontend

Use Next.js/React for the public interface.

Responsibilities:

- routing
- forms
- card/detail presentation
- charts
- session-scoped settings
- loading and error states
- responsive behavior

### 10.2 Python analytics API

Keep reusable Python intelligence and expose it behind a web API.

Responsibilities:

- recommendation scoring
- trend calculations
- game mapping/normalization
- provider ingestion
- Steam-profile processing
- streamer opportunity scoring
- developer opportunity scoring
- concept input preparation

The Python layer must be UI-agnostic.

### 10.3 Database

Use durable cloud Postgres, deployed through a Vercel-compatible provider. Neon Postgres through the Vercel Marketplace is the preferred v1 deployment choice.

Migrate useful SQLite prototype data into Postgres instead of discarding it.

## 11. Data model

Minimum logical tables/entities:

### `games`

Canonical Steam game identity and normalized metadata.

Key fields:

- Steam App ID
- title
- canonical slug
- Steam URL
- artwork URLs
- release date
- developer/publisher
- genres/tags

### `game_prices`

Historical/current price snapshots.

### `steam_snapshots`

Player activity observations and Steam-derived public signals.

### `streaming_snapshots`

Normalized streaming/category observations.

### `steamspy_snapshots`

Ownership and market estimates with estimate-range/confidence metadata.

### `review_snapshots`

Review count and sentiment observations.

### `trend_scores`

Derived normalized trend and opportunity metrics by game and evaluation window.

### `source_status`

Latest success/failure/freshness state for each provider.

### `refresh_runs`

Provider refresh execution history and errors.

## 12. Provider policy

### 12.1 Steam

Steam is the canonical game identifier and principal game metadata source.

Use permitted Steam endpoints/store data for:

- App ID identity
- metadata
- artwork
- price/store URL
- reviews where accessible
- current player signals where accessible
- user library/profile personalization when the user supplies a Steam Web API key

### 12.2 SteamSpy

SteamSpy is an estimate source, not ground truth.

Ownership must be presented as an estimate/range with confidence where possible. Do not label ownership estimates as exact sales.

SteamSpy failure must not prevent Player, Streamer, or Developer pages from loading.

### 12.3 TwitchTracker

Use TwitchTracker only through a permitted documented/basic API or other explicitly allowed interface. Do not scrape TwitchTracker HTML.

Use available category/game summaries as streaming demand/competition inputs.

### 12.4 SullyGnome

SullyGnome may be used as a public validation/enrichment source only where the method of access is permitted and stable. It must remain optional rather than a single point of failure.

### 12.5 SteamDB

SteamDB may be used manually during development as a validation/reference source.

Automated SteamDB scraping/crawling is excluded from v1 unless explicit permission is obtained. The production system should reproduce useful SteamDB-style insights from permitted underlying Steam data and GamePulse's own stored history.

### 12.6 Twitch and Streams Charts credentials

The production product must not require:

- Twitch Client ID
- Twitch Client Secret
- Streams Charts client/token credentials

Compatibility hooks may remain internal if useful, but these credentials must not be required or presented as normal setup fields.

## 13. Snapshot and caching policy

Normal user requests read cached, normalized Postgres data.

Initial refresh policy:

- Steam current-player signals for tracked/ranked games: hourly
- streaming/category signals: every 6 hours
- SteamSpy estimates: daily
- review/price changes: daily
- relatively static Steam metadata/artwork: weekly, with on-demand refresh for missing records

If Vercel plan limits prevent the desired cron frequency, use GitHub Actions or another signed scheduler to call the same protected refresh endpoint. The application logic must not depend on the scheduler vendor.

Historical charts are built from GamePulse's stored snapshots.

## 14. Freshness and confidence

Every externally derived metric exposed in the UI must be capable of showing:

- source
- last updated time
- freshness/staleness state
- confidence when the value is estimated or derived

The UI may suppress these details in compact cards, but they must be available on details/analysis views.

## 15. Settings and secrets

### 15.1 No login

There is no account system in v1.

### 15.2 Steam Web API key

The Settings page allows a user to enter a Steam Web API key for Steam-profile personalization.

Rules:

- stored only in the active session
- never written to Postgres
- never committed to Git
- never written to browser `localStorage`
- never written to permanent cookies
- never surfaced back to the client once submitted to a server-side session mechanism
- disappears when the session ends

### 15.3 Data-source status

Settings should show simple source health such as:

- GamePulse database
- Steam metadata/activity
- streaming statistics
- SteamSpy
- Steam profile personalization

Do not expose confusing unused credential fields.

## 16. Failure and fallback behavior

Provider failures must degrade individual metrics, not whole pages.

### Streaming provider unavailable

Use the latest stored streaming snapshot and label it stale when appropriate.

### SteamSpy unavailable

Hide/degrade ownership estimates and continue ranking using other factors.

### Steam current-player request unavailable

Use the latest stored observation and mark freshness accordingly.

### Steam profile key missing/invalid

Keep the general application usable and clearly explain that personalized Steam-library lookup requires a valid key.

### Artwork unavailable

Use a branded GamePulse placeholder without layout collapse.

### API/analytics error

Render a user-facing recoverable error state. Never expose Python stack traces in production.

## 17. API boundaries

The exact transport can evolve, but the frontend/backend boundary should expose stable resources conceptually equivalent to:

- `GET /api/games/{appid}`
- `GET /api/games/{appid}/history`
- `POST /api/player/recommend`
- `POST /api/streamer/simulate`
- `GET /api/developer/opportunities`
- `GET /api/developer/opportunities/{id}`
- `POST /api/developer/concept`
- `GET /api/sources/status`
- protected refresh endpoints for scheduled ingestion

Responses should return normalized UI-ready models rather than exposing provider-specific raw payloads.

## 18. Deployment

### 18.1 Vercel

The public web application is deployed to Vercel and must produce shareable preview URLs from the fusion branch before production promotion.

### 18.2 Git workflow

- feature work occurs on `feature/gamepulse-fusion-web`
- preview deployment validates the branch
- production promotion happens only after end-to-end and UI review
- `main` remains protected from unvalidated direct replacement

### 18.3 Environment configuration

Server-side secrets/configuration must use Vercel environment variables or linked integration credentials. Never commit real keys.

## 19. Testing strategy

### 19.1 Python unit tests

Cover:

- normalization
- trend calculations
- score weights
- player recommendation factors
- streamer objectives
- developer opportunity scoring
- mapping/aliases
- confidence/freshness handling

Reuse and adapt the strongest tests from the streamer branch.

### 19.2 Provider tests

Mock:

- timeouts
- malformed payloads
- unavailable source
- missing fields
- stale cache
- rate-limit responses

### 19.3 Frontend/component tests

Cover:

- landing mode cards
- forms
- game cards
- score breakdowns
- game-detail sections
- source/freshness labels
- skeleton/error states

### 19.4 End-to-end flows

Required successful flows:

1. Landing → Player → Steam profile → recommendations → game details.
2. Landing → Streamer → cold-start simulation → ranked opportunities → game details.
3. Landing → Developer → opportunity → evidence → suggested direction → mini game brief.
4. Settings → session Steam key → Player personalization.
5. Provider failure → cached fallback with visible stale/freshness state.

## 20. Security and privacy

- no account collection in v1
- no permanent storage of user Steam API keys
- no secrets in client bundles
- protected refresh endpoints use a server-side secret/token
- sanitize/validate Steam profile URLs and all user input
- enforce outbound request timeouts and allowlisted providers
- avoid storing unnecessary user profile data after a recommendation request

## 21. Accessibility

Minimum v1 requirements:

- keyboard-accessible navigation and cards
- visible focus states
- semantic headings
- sufficient contrast
- labels for form controls
- chart summaries available as text
- no critical meaning conveyed by color alone

## 22. Non-goals for v1

- console game support
- mobile game support
- user accounts
- permanent saved profiles
- social features
- exact sales/revenue claims
- full game-production plans
- automated SteamDB scraping
- dependence on private Twitch/Streams Charts credentials
- preserving the native desktop UI

## 23. Implementation sequence

1. Create the fusion branch from `main`.
2. Inventory and migrate useful existing dataset/schema content.
3. Define Postgres schema and migration/seed tooling.
4. Isolate/port domain logic from `main`, streamer branch, and SteamSpy/developer branch.
5. Implement provider contracts, normalization, caching, source status, and scheduled ingestion.
6. Add/port Python unit and provider tests.
7. Build the Next.js design system and global navigation.
8. Build the landing page.
9. Build shared game cards and Game Detail page.
10. Build Player mode.
11. Build Streamer cold-start simulator and its three objectives.
12. Build Developer evidence → opportunity → direction → mini-brief flow.
13. Build Settings and session-only Steam key handling.
14. Configure scheduled refreshes and Postgres deployment.
15. Add frontend/component tests and end-to-end tests.
16. Deploy a Vercel preview from the fusion branch.
17. Perform visual/responsive/accessibility QA against the approved clean mockup direction.
18. Fix regressions and provider fallback issues.
19. Promote only the validated deployment.

## 24. Acceptance criteria

The design is implemented successfully when all of the following are true:

- The Vercel URL opens without login and shows a clean three-mode landing page.
- Player, Streamer, and Developer are separate pages.
- Game cards contain real game artwork when available and open internal GamePulse detail pages.
- Every game detail page has a working **View on Steam** action.
- Player mode supports both owned-library and new-game recommendations.
- Player recommendations expose a compact factor score breakdown.
- Streamer mode works for a zero-audience channel without requiring Twitch credentials.
- Streamer mode supports Discoverability, Audience Potential, and Balanced Growth objectives.
- Developer mode presents evidence before recommendations and can generate the defined mini game brief.
- Market/generated content is clearly distinguished.
- The app works without Twitch Client ID/secret and without Streams Charts credentials.
- Steam-profile personalization can use a session-only user Steam API key.
- User Steam API keys are not persisted.
- Normal pages read cached Postgres snapshots and remain usable during provider outages.
- Source freshness/staleness is visible in detailed views.
- SteamSpy estimates are labeled as estimates, not exact sales.
- Automated SteamDB scraping is absent unless explicit permission is later documented.
- Historical charts use stored GamePulse snapshots.
- Existing useful streamer/mapping tests are preserved or equivalently replaced.
- End-to-end tests cover all three primary mode flows and provider fallback.
- The final UI follows the approved clean, spacious, image-rich design rather than the crowded desktop layout.
