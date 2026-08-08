# GamePulse Fusion Web — Design Specification

**Date:** 2026-08-08  
**Status:** Approved design  
**Target branch:** `feature/gamepulse-fusion-web`  
**Production target:** Vercel

## 1. Product objective

GamePulse becomes a clean, public, Steam/PC-focused web application built around three separate questions:

- **Player:** What should I play next?
- **Streamer:** What should I stream as a new or zero-audience channel?
- **Developer:** What game opportunity should I explore, and what evidence supports it?

The web release preserves useful recommendation, trend, mapping, forecasting, and market-analysis logic already present across the repository while replacing the Streamlit/native-desktop presentation with a dedicated Next.js frontend.

Steam/PC is the only platform scope for v1. Console and mobile are explicitly out of scope.

## 2. Design principles

1. **One audience, one workspace.** Player, Streamer, and Developer are separate pages.
2. **Simple first, depth on demand.** Summary cards appear before detailed charts.
3. **Evidence before generated ideas.** Market facts, derived scores, and generated concepts are visually separated.
4. **No required Twitch or Streams Charts credentials.** The product remains useful without them.
5. **Cached by default.** Normal page loads read normalized Postgres snapshots rather than waiting for multiple external providers.
6. **Graceful degradation.** One provider failure degrades individual metrics, not an entire page.
7. **Explainable scores.** Recommendations expose normalized factor scores and concise reasons.
8. **Image-first game presentation.** Use Steam artwork and metadata instead of spreadsheet-like rows.
9. **No login in v1.** Anyone with the Vercel link can use the product.
10. **No persistent user secrets.** User-provided API keys exist only in browser runtime memory for the active page session and are discarded when the page/tab is closed or reloaded.

## 3. Repository fusion strategy

The implementation must not perform a blind multi-branch merge.

### 3.1 Base

All production work starts from `main`.

Use `main` for the Player foundation, curated/localized content and presentation ideas, recommendation/forecasting foundations, game-detail logic, market analysis, and current prototype dataset.

### 3.2 Streamer branch inputs

Selectively port useful logic from:

`agent/gamepulse-twitch-streamer-recommendations`

Priority candidates:

- `gamepulse/growth_windows.py`
- `gamepulse/game_mapping.py`
- `gamepulse/creator_aggregation.py`
- expanded `streamer_fit.py`
- expanded `streamer_opportunity.py`
- Twitch/Steam alias mappings
- snapshot collection architecture
- provider/growth/mapping/provenance tests

This branch shares history with `main` and is the preferred source for tested streamer logic.

### 3.3 SteamSpy/developer branch inputs

Selectively port useful code and concepts from:

`codex/twitchtracker-steamspy-estimates`

Do **not** merge this branch wholesale because it has unrelated Git history and replaces the web entry point with a native desktop application.

Priority candidates:

- provider contracts/composition
- provider caching patterns
- SteamSpy integration
- Steam public-signal helpers
- developer intelligence
- developer prediction
- source/confidence metadata patterns

Do not preserve the native desktop UI, monolithic desktop architecture, credential-dependent streamer behavior, or crowded desktop presentation.

### 3.4 Conflict rule

When implementations conflict, priority is:

1. behavior required by this specification;
2. tested domain logic that can be isolated from UI;
3. compatibility with `main` data and semantics;
4. simpler implementation.

No legacy UI is retained merely because it already exists.

## 4. Information architecture

### 4.1 Landing page

The first page is intentionally simple and contains a short introduction plus three primary cards:

- **Player — Find what to play**
- **Streamer — Find what to stream**
- **Developer — Find what to build**

No dense market dashboard appears on the landing page.

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

- artwork
- title
- one primary score/status
- at most two supporting metrics
- one short explanation

Clicking a game opens the internal GamePulse detail route rather than immediately leaving for Steam.

## 5. Player mode

### 5.1 Input

Primary input is a Steam profile URL.

Steam-profile personalization uses a user-provided Steam Web API key when required by Steam. The key follows the session-secret rules in Section 15.

### 5.2 Results

#### Play Next From Your Library

Ranks games the user already owns.

#### Discover Something New

Ranks catalog games the user does not own but is likely to enjoy.

### 5.3 Ranking objective

Player ranking balances:

- personal fit from library/playtime patterns
- genre/tag similarity
- review quality
- current player activity
- trend momentum

Popularity alone must not dominate personal fit.

### 5.4 Explainability

Each recommendation exposes:

- Personal fit
- Review quality
- Current activity
- Trend momentum
- Overall recommendation score

The scoring service returns each factor normalized to 0–100 plus the final weighted score. Missing factors are omitted and remaining weights are renormalized rather than treated as zero.

Initial default weights for a fully populated recommendation are:

- personal fit: 45%
- review quality: 20%
- current activity: 15%
- trend momentum: 20%

These weights are configuration constants covered by tests, not user-facing controls in v1.

## 6. Streamer mode

### 6.1 Purpose

Streamer mode is a **cold-start simulator** for a new or empty channel. It does not require an established Twitch account or channel history.

### 6.2 Simple simulator

The default form contains optional fields for:

- preferred genres
- casual / balanced / competitive preference
- solo / multiplayer / either preference
- language
- region

Running the simulator without preferences is valid and returns general opportunities.

### 6.3 Advanced simulator

Advanced mode adds optional fields for:

- weekly streaming hours
- typical streaming time window
- hardware capability tier
- maximum game purchase price
- content style

### 6.4 Objectives

Users can switch between:

- **Discoverability**
- **Audience Potential**
- **Balanced Growth**

Default: **Balanced Growth**.

The opportunity engine uses available signals for:

- viewer demand
- competing channels
- viewer-to-channel ratio
- category growth
- Steam player momentum
- game/profile fit
- volatility/stability

A very large category may rank below a smaller category when a zero-audience creator is likely to be buried by competition.

### 6.5 Output

Streamer results contain:

- ranked games/categories
- opportunity score
- demand score
- competition/discoverability score
- momentum score
- fit score when preferences exist
- short explanation
- freshness/confidence status

The page uses a small number of focused charts rather than a dense analytics wall.

## 7. Developer mode

Developer mode follows a progressive evidence-to-concept flow.

### 7.1 Market dashboard

Show concise evidence for:

- rising genres
- rising tags/mechanics
- Steam player momentum
- streaming demand
- release saturation
- review sentiment
- ownership estimates where available
- price bands

### 7.2 Opportunity cards

Each opportunity contains:

- market-segment label
- opportunity score
- demand indicator
- competition/saturation indicator
- streaming fit
- confidence
- evidence summary

### 7.3 Explore opportunity

Opening an opportunity shows supporting games, charts, source data, risks, and the reason the segment was detected.

### 7.4 Suggest direction

GamePulse may translate the evidence into a proposed product direction. The direction must be labeled as a recommendation, not a market fact.

### 7.5 Generate mini game brief

The brief contains:

- working concept/name
- genre/subgenre
- core gameplay loop
- 3–5 key mechanics
- target players
- solo/multiplayer structure
- suggested Steam price band
- comparable Steam games
- market opportunity score
- saturation/risk summary
- evidence-backed rationale

GamePulse must generate a usable brief even when no LLM key is configured. The baseline generator is deterministic and template/rule-based from the selected opportunity and its evidence. If a server-side Mistral key or a session-only user Mistral key is available, an optional enhancement pass may improve wording/ideation without changing source facts, scores, comparable games, or confidence values.

A full production roadmap, staffing plan, or detailed commercial forecast is out of scope for v1.

## 8. Game-detail page

Route:

`/games/[steamAppId]`

### 8.1 Summary section

The top of the page contains:

- large Steam artwork/header
- title
- short description
- price when available
- review summary
- current/recent player activity
- concise trend state
- **View on Steam** button

### 8.2 Deeper analysis

Below the summary, add focused sections for:

- Steam player activity chart
- streaming trend chart
- review breakdown
- market position / ownership estimates
- genres/tags
- comparable games
- recommendation reason

When opened from Player, Streamer, or Developer, the page may show mode-specific context without changing the canonical game record.

## 9. Visual design system

The approved direction is clean and restrained rather than a dense analytics terminal.

### 9.1 Layout rules

- generous whitespace
- large cards
- clear hierarchy
- one primary chart per analytical section where practical
- responsive desktop/tablet/mobile layouts
- image-first game presentation
- subtle hover/focus states
- skeleton loaders
- no all-modes dashboard

### 9.2 Style

- modern dark-mode-first aesthetic
- restrained purple/violet accent
- high-contrast typography
- minimal decorative gradients
- consistent rounded surfaces
- restrained animation

The interface should feel like a modern game-discovery product with analytics, not a BI terminal.

## 10. Architecture

### 10.1 Frontend

Use Next.js/React for:

- routing
- forms
- cards/detail presentation
- charts
- browser-runtime session settings
- loading/error states
- responsive behavior

### 10.2 Python analytics API

Reuse Python domain intelligence behind web endpoints for:

- recommendation scoring
- trend calculations
- game mapping/normalization
- provider ingestion
- Steam-profile processing
- streamer opportunity scoring
- developer opportunity scoring
- deterministic concept generation and optional AI enhancement input preparation

The Python layer is UI-agnostic.

### 10.3 Database

Use durable cloud Postgres. Neon Postgres through the Vercel Marketplace is the preferred v1 deployment.

Migrate useful SQLite prototype data into Postgres rather than discarding it.

## 11. Data model

Minimum logical entities:

### `games`

Canonical Steam identity and normalized metadata including App ID, title, Steam URL, artwork URLs, release date, developer/publisher, genres, and tags.

### `game_prices`

Historical/current price observations.

### `steam_snapshots`

Player activity and permitted Steam-derived public signals.

### `streaming_snapshots`

Normalized streaming/category observations.

### `steamspy_snapshots`

Ownership/market estimates plus estimate range and confidence metadata.

### `review_snapshots`

Review count and sentiment observations.

### `trend_scores`

Derived trend/opportunity metrics by game and evaluation window.

### `source_status`

Latest provider health/freshness state.

### `refresh_runs`

Refresh execution history, item counts, timestamps, and errors.

No user API keys are stored in any table.

## 12. Provider policy

### 12.1 Steam

Steam is the canonical game identifier and principal metadata source. Use permitted Steam endpoints/store data for App identity, metadata, artwork, price/store links, reviews where accessible, current-player signals where accessible, and user library/profile personalization with a user key.

### 12.2 SteamSpy

SteamSpy is an estimate source, not ground truth. Ownership is presented as an estimate/range with confidence when possible and is never labeled as exact sales. SteamSpy failure must not prevent any mode from loading.

### 12.3 TwitchTracker

Use TwitchTracker only through a documented/permitted API or explicitly allowed interface. Do not scrape TwitchTracker HTML. The application must not require an end user to supply Twitch credentials. If the permitted TwitchTracker interface is unavailable or later requires credentials the deployment does not have, disable live TwitchTracker enrichment and use stored snapshots/other permitted signals.

### 12.4 SullyGnome

SullyGnome may be used only through an access method that is permitted and stable. It is optional validation/enrichment and never a single point of failure.

### 12.5 SteamDB

SteamDB may be used manually for development validation/reference. Automated SteamDB scraping/crawling is excluded unless explicit permission is obtained and documented. Production should reproduce useful SteamDB-style insights from permitted Steam sources plus GamePulse history.

### 12.6 Credentials not required

The normal product must not require:

- Twitch Client ID
- Twitch Client Secret
- Streams Charts client/token credentials

These fields are not shown in normal Settings.

## 13. Snapshot and caching policy

Normal user requests read cached normalized Postgres data.

Initial target cadence:

- Steam current-player signals for tracked/ranked games: hourly
- permitted streaming/category signals: every 6 hours
- SteamSpy estimates: daily
- review and price observations: daily
- relatively static Steam metadata/artwork: weekly, with on-demand refresh for missing records

Refresh work is processed in bounded batches and records progress in `refresh_runs` so one long provider job is not required to finish in a single serverless invocation.

If Vercel plan limits prevent a desired schedule, GitHub Actions or another signed scheduler calls the same protected refresh endpoints. Domain logic does not depend on the scheduler vendor.

Historical charts are built from GamePulse snapshots.

## 14. Freshness and confidence

Every external/derived metric exposed in a detailed view can report:

- source
- last updated timestamp
- fresh/stale state
- confidence when estimated/derived

Compact cards may hide these details, but details/analysis pages must expose them.

## 15. Settings and session secrets

### 15.1 No login

There is no account system in v1.

### 15.2 User-provided keys

Settings supports:

- **Steam Web API key** — unlocks Steam-profile personalization when required.
- **Mistral API key (optional)** — enhances generated Developer concept wording/ideation; never required for the core flow.

Each user-provided key:

- exists only in JavaScript runtime memory for the active tab/page session;
- is never written to Postgres;
- is never committed to Git;
- is never written to `localStorage` or `sessionStorage`;
- is never written to cookies;
- is sent over HTTPS only with requests that require it;
- is discarded by the server after the individual request and is not logged;
- is lost when the page is reloaded or the tab is closed.

This intentionally favors security and demo simplicity over convenience.

### 15.3 Owner/server keys

The deployment owner may configure optional server-side provider keys through Vercel environment variables. These values are never returned to clients and do not create an end-user setup requirement.

### 15.4 Source status

Settings shows simple status for:

- GamePulse database
- Steam metadata/activity
- streaming statistics
- SteamSpy
- Steam-profile personalization
- optional AI enhancement

Do not show unused Twitch/Streams Charts credential fields.

## 16. Failure and fallback behavior

### Streaming source unavailable

Use the latest stored streaming snapshot and label it stale when appropriate.

### SteamSpy unavailable

Hide/degrade ownership estimates and continue using other factors.

### Steam current-player request unavailable

Use the latest stored observation and expose staleness.

### Steam profile key missing/invalid

Keep the general application usable and explain that personalized library lookup needs a valid key.

### LLM unavailable

Use the deterministic Developer brief generator.

### Artwork unavailable

Use a branded GamePulse placeholder without layout collapse.

### Internal/API error

Render a recoverable user-facing error. Never expose Python stack traces in production.

## 17. API boundaries

Frontend/backend resources should be stable and conceptually equivalent to:

- `GET /api/games/{appid}`
- `GET /api/games/{appid}/history`
- `POST /api/player/recommend`
- `POST /api/streamer/simulate`
- `GET /api/developer/opportunities`
- `GET /api/developer/opportunities/{id}`
- `POST /api/developer/concept`
- `GET /api/sources/status`
- protected refresh endpoints for scheduled ingestion

Responses return normalized UI-ready models rather than raw provider payloads.

## 18. Deployment

### 18.1 Vercel

The public web application is deployed to Vercel. The fusion branch must produce a shareable preview deployment before production promotion.

### 18.2 Git workflow

- feature work occurs on `feature/gamepulse-fusion-web`
- preview deployment validates the branch
- production promotion occurs only after end-to-end, provider-fallback, and UI review
- `main` is not replaced by an unvalidated build

### 18.3 Environment configuration

Server-side configuration and secrets use Vercel environment variables or linked integrations. Real keys are never committed.

## 19. Testing strategy

### Python unit tests

Cover normalization, trend calculations, player weights, streamer objectives, developer opportunity scoring, mapping/aliases, deterministic concept generation, confidence, and freshness handling.

Reuse/adapt the strongest tests from the streamer branch.

### Provider tests

Mock timeouts, malformed payloads, unavailable sources, missing fields, stale caches, and rate limits.

### Frontend/component tests

Cover landing cards, forms, game cards, score breakdowns, detail sections, source/freshness labels, skeletons, and errors.

### End-to-end flows

1. Landing → Player → Steam profile → recommendations → Game Detail.
2. Landing → Streamer → cold-start simulation → ranked opportunities → Game Detail.
3. Landing → Developer → opportunity → evidence → direction → mini game brief.
4. Settings → runtime-only Steam key → Player personalization.
5. Provider failure → cached fallback with stale/freshness state.
6. LLM unavailable → deterministic Developer mini brief still succeeds.

## 20. Security and privacy

- no account collection in v1
- no persistent user API keys
- no secrets in client bundles
- protected refresh endpoints use server-side authentication
- sanitize/validate Steam profile URLs and all user inputs
- enforce outbound timeouts and allowlisted providers
- do not persist unnecessary Steam-profile data after recommendation processing
- redact secrets from logs/errors

## 21. Accessibility

Minimum v1 requirements:

- keyboard-accessible navigation/cards
- visible focus states
- semantic headings
- sufficient contrast
- labels for controls
- text summaries for charts
- no critical meaning conveyed only by color

## 22. Non-goals for v1

- console games
- mobile games
- user accounts
- permanent saved profiles
- social features
- exact sales/revenue claims
- full game-production plans
- automated SteamDB scraping
- dependence on private Twitch/Streams Charts credentials
- preservation of the native desktop UI

## 23. Implementation sequence

1. Create the fusion branch from `main`.
2. Inventory/migrate useful existing data.
3. Define Postgres schema and migration/seed tooling.
4. Isolate/port domain logic from `main`, the streamer branch, and the SteamSpy/developer branch.
5. Implement provider contracts, normalization, caching, source status, and batched scheduled ingestion.
6. Add/port Python unit/provider tests.
7. Build the Next.js design system and global navigation.
8. Build the landing page.
9. Build shared game cards and Game Detail.
10. Build Player mode.
11. Build the Streamer cold-start simulator and three objectives.
12. Build Developer evidence → opportunity → direction → mini-brief flow.
13. Build Settings and runtime-only secret handling.
14. Configure scheduled refreshes and Postgres deployment.
15. Add frontend/component and end-to-end tests.
16. Deploy a Vercel preview.
17. Perform responsive/accessibility/visual QA against the approved clean direction.
18. Fix regressions and fallback issues.
19. Promote only the validated deployment.

## 24. Acceptance criteria

Implementation is successful when:

- The Vercel URL opens without login and shows a clean three-mode landing page.
- Player, Streamer, and Developer are separate pages.
- Game cards use real artwork when available and open internal GamePulse details.
- Game Details includes a working **View on Steam** action.
- Player supports both owned-library and new-game recommendations.
- Player recommendations expose the defined compact factor breakdown.
- Streamer works for a zero-audience channel without requiring Twitch credentials.
- Streamer supports Discoverability, Audience Potential, and Balanced Growth.
- Developer presents evidence before recommendations and generates the defined mini game brief without requiring an LLM.
- Optional AI enhancement cannot alter source facts/scores without explicit recalculation by deterministic analytics logic.
- The app works without Twitch Client ID/secret and without Streams Charts credentials.
- Steam-profile personalization can use a runtime-only Steam API key.
- User-provided API keys are never persisted.
- Normal pages read cached Postgres snapshots and remain usable during provider outages.
- Source freshness/staleness is visible in detailed views.
- SteamSpy ownership is labeled as an estimate, not exact sales.
- Automated SteamDB scraping is absent unless permission is documented.
- Historical charts use stored GamePulse snapshots.
- Useful existing streamer/mapping tests are preserved or equivalently replaced.
- End-to-end tests cover all three mode flows, provider fallback, and no-LLM Developer generation.
- The final UI follows the approved clean, spacious, image-rich direction rather than the crowded desktop layout.
