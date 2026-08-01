# GamePulse Prototype Vertical Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a locally hosted GamePulse prototype that tells one connected story for a player, Twitch streamer, and game developer around the same selected Steam game.

**Architecture:** A Streamlit interface calls focused Python services backed by a local SQLite database built from the prepared CSV files. External Steam, Twitch, IGDB, and Mistral connections sit behind provider interfaces with demo/cached/live modes, so the prototype remains usable without credentials. The first deliverable is a polished vertical slice for one data-rich curated game, followed by catalogue-wide support.

**Tech Stack:** Python 3.12, Streamlit, SQLite, pandas, scikit-learn, statsmodels, requests, python-dotenv, Plotly, standard-library `unittest`.

## Global Constraints

- Run locally on the team's prototype computer; the app is available only while that computer is running.
- No Docker, PostgreSQL, FastAPI, user accounts, automated outreach, or deployment in version one.
- Never request or store Steam passwords, browser cookies, Twitch passwords, or user-owned API keys.
- Keep project credentials in `.env`; commit only `.env.example`.
- Label every external observation `Live`, `Cached`, or `Demo` and show its observation time.
- Label SteamSpy ownership and derived sales/revenue as estimates; never present them as Valve-verified sales.
- Keep Steam library data in memory by default; local persistence requires an explicit user choice.
- Use synthetic Twitch fixtures only in tests. Any demonstration snapshot must record its source, collection time, and reuse constraints.
- Retain raw Twitch responses only as allowed by Twitch's current developer terms; prefer short-lived raw cache and aggregate features.
- Use `data/prototype/gamepulse_prototype.sqlite3` as the clearly disposable prototype database.
- The workspace is not currently a Git repository. Do not create commits or branches unless the user separately authorizes repository initialization.

## Accepted Product Decisions

- The demo begins with a curated game and also supports catalogue search.
- The same selected game flows through Player, Streamer, and Developer modes.
- Player Mode supports a public Steam profile URL plus manual-preference fallback.
- Streamer Mode ranks games with an explainable Opportunity Score.
- Developer Mode ranks creators with an explainable Streamer Fit Score.
- Developer market analysis combines official Steam rankings with public ownership, player, review, price, and discount signals.
- Version one predicts 30-day review activity and derives a clearly labelled ownership/revenue potential range.
- Local review NLP always works; Mistral summary generation is optional.

---

### Task 1: Reproducible local runtime and configuration

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `gamepulse/__init__.py`
- Create: `gamepulse/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Settings.from_env(root: Path) -> Settings`
- Produces: `Settings.twitch_enabled`, `steam_enabled`, and `mistral_enabled` boolean properties

- [ ] **Step 1: Write tests** asserting that missing secrets select demo/manual modes and complete credential pairs enable their provider.
- [ ] **Step 2: Run** `python -m unittest tests.test_config -v` and verify the import fails.
- [ ] **Step 3: Implement** an immutable `Settings` dataclass with paths for processed data, prototype database, Twitch demo snapshot, and optional `TWITCH_CLIENT_ID`, `TWITCH_CLIENT_SECRET`, `STEAM_WEB_API_KEY`, and `MISTRAL_API_KEY` values.
- [ ] **Step 4: Add dependencies** with version floors: `streamlit>=1.40`, `pandas>=2.2`, `scikit-learn>=1.5`, `statsmodels>=0.14`, `requests>=2.32`, `python-dotenv>=1.0`, and `plotly>=5.24`.
- [ ] **Step 5: Add `.env.example`** containing empty credential names and comments explaining where each credential is created; ensure `.env` is ignored if a repository is initialized later.
- [ ] **Step 6: Run** `python -m unittest tests.test_config -v` and expect all tests to pass.

### Task 2: Build the disposable SQLite database

**Files:**
- Create: `gamepulse/database.py`
- Create: `scripts/build_prototype_database.py`
- Test: `tests/test_database.py`

**Interfaces:**
- Produces: `build_database(processed_dir: Path, database_path: Path) -> BuildReport`
- Produces: `connect_read_only(database_path: Path) -> sqlite3.Connection`

- [ ] **Step 1: Write a fixture test** with two games, tags, genres, review summaries, and reviews; assert exact row counts and foreign-key integrity.
- [ ] **Step 2: Run** `python -m unittest tests.test_database -v` and verify failure before implementation.
- [ ] **Step 3: Implement tables** `games`, `game_tags`, `game_genres`, `review_summaries`, `reviews`, `twitch_game_snapshots`, `twitch_streamer_snapshots`, and `steam_market_snapshots` with explicit primary and foreign keys.
- [ ] **Step 4: Add indexes** for case-insensitive game name search, review lookup by `steam_app_id` and creation time, and snapshot lookup by observation time.
- [ ] **Step 5: Implement chunked CSV loading** so `reviews_clean.csv` is never loaded wholly into memory; replace the disposable database atomically only after validation passes.
- [ ] **Step 6: Run** `python scripts/build_prototype_database.py --processed-dir data/processed/2026-08-01 --database data/prototype/gamepulse_prototype.sqlite3`.
- [ ] **Step 7: Run** `python -m unittest tests.test_database -v` and record database size and build duration in `data/prototype/README.md`.

### Task 3: Shared game catalogue and curated-game selection

**Files:**
- Create: `gamepulse/catalog.py`
- Create: `scripts/select_curated_game.py`
- Test: `tests/test_catalog.py`

**Interfaces:**
- Produces: `GameSummary` dataclass
- Produces: `search_games(query: str, limit: int = 20) -> list[GameSummary]`
- Produces: `get_game(steam_app_id: int) -> GameSummary`
- Produces: `rank_demo_candidates(limit: int = 20) -> list[GameSummary]`

- [ ] **Step 1: Write tests** for empty search, punctuation, duplicate names, missing IDs, and deterministic demo ranking.
- [ ] **Step 2: Rank curated candidates** by complete metadata, at least 500 dated reviews, non-empty tags/genres, price availability, and non-empty ownership/player fields.
- [ ] **Step 3: Implement parameterized SQL queries** and return typed values rather than raw SQLite rows.
- [ ] **Step 4: Run** `python scripts/select_curated_game.py --database data/prototype/gamepulse_prototype.sqlite3 --limit 20` and save the chosen AppID in `data/prototype/demo_config.json` with the selection reasons.
- [ ] **Step 5: Run** `python -m unittest tests.test_catalog -v`.

### Task 4: Streamlit shell and connected navigation state

**Files:**
- Create: `app.py`
- Create: `gamepulse/ui/__init__.py`
- Create: `gamepulse/ui/home.py`
- Create: `gamepulse/ui/shared.py`
- Test: `tests/test_demo_state.py`

**Interfaces:**
- Produces: `DemoState(selected_app_id: int, steam_profile: str | None)`
- Produces: `render_game_header(game: GameSummary, source_status: SourceStatus) -> None`

- [ ] **Step 1: Test** serialization and state transitions when the selected game changes.
- [ ] **Step 2: Implement** a Home page plus Player, Streamer, and Developer navigation using one `selected_app_id` in Streamlit session state.
- [ ] **Step 3: Show** the curated game on first launch, searchable replacement, data-source badges, observation times, and dataset limitations.
- [ ] **Step 4: Add one-command startup** documented as `streamlit run app.py`.
- [ ] **Step 5: Run** `python -m unittest tests.test_demo_state -v`, then launch the app and verify changing the game updates all three mode headers.

### Task 5: Explainable Player recommender

**Files:**
- Create: `gamepulse/recommendations.py`
- Create: `gamepulse/ui/player.py`
- Test: `tests/test_recommendations.py`

**Interfaces:**
- Produces: `recommend_similar(app_id: int, preferences: PlayerPreferences, excluded_app_ids: set[int], limit: int = 10) -> list[Recommendation]`
- `Recommendation` includes `app_id`, `score`, and `reasons: tuple[str, ...]`.

- [ ] **Step 1: Write tests** proving owned games are excluded, price/OS filters work, and every result has at least one human-readable reason.
- [ ] **Step 2: Implement** weighted tag/genre overlap, normalized review score, price compatibility, OS compatibility, and a configurable popularity penalty for hidden gems.
- [ ] **Step 3: Render** similar games, hidden gems, filters, score components, and “why recommended” explanations.
- [ ] **Step 4: Run** `python -m unittest tests.test_recommendations -v` and manually verify the curated game returns plausible results.

### Task 6: Steam profile personalization with manual fallback

**Files:**
- Create: `gamepulse/providers/steam.py`
- Create: `gamepulse/player_profile.py`
- Modify: `gamepulse/ui/player.py`
- Test: `tests/test_steam_provider.py`

**Interfaces:**
- Produces: `SteamProvider.resolve_profile(profile_url_or_id: str) -> str`
- Produces: `SteamProvider.get_library(steam_id: str) -> PlayerLibrary`
- Produces: `infer_preferences(library: PlayerLibrary, catalog: GameCatalog) -> PlayerPreferences`

- [ ] **Step 1: Write mocked HTTP tests** for numeric IDs, vanity URLs, public libraries, private libraries, rate limits, and malformed responses.
- [ ] **Step 2: Implement** SteamID/profile parsing and official owned/recently-played requests using the project-owned API key.
- [ ] **Step 3: Weight preferences** by log-scaled playtime, recent play, and tag/genre frequency; exclude already owned games.
- [ ] **Step 4: Provide manual selection** of liked games when the API key is absent or Game Details are private.
- [ ] **Step 5: Keep library data in session memory** unless the player explicitly checks “Save this profile locally.”
- [ ] **Step 6: Run** `python -m unittest tests.test_steam_provider -v` without making a live request.

### Task 7: Twitch demo/cached/live provider boundary

**Files:**
- Create: `gamepulse/providers/twitch.py`
- Create: `gamepulse/providers/models.py`
- Create: `data/demo/twitch_snapshot.json`
- Test: `tests/test_twitch_provider.py`

**Interfaces:**
- Produces: `TwitchProvider.get_game_trends() -> Snapshot[list[GameTrend]]`
- Produces: `TwitchProvider.get_streamers(game_id: str) -> Snapshot[list[StreamerObservation]]`
- `Snapshot` includes `mode`, `observed_at`, `source_name`, and `data`.

- [ ] **Step 1: Write contract tests** and run the same assertions against demo and cached providers.
- [ ] **Step 2: Create a schema-valid demonstration snapshot** with conspicuous `Demo` provenance and no claim that its values are current Twitch observations.
- [ ] **Step 3: Implement provider selection:** valid credentials prefer live, a valid permitted cache is second, and demo is the final fallback.
- [ ] **Step 4: Implement automatic app-token acquisition/refresh** without logging secrets or tokens.
- [ ] **Step 5: Respect returned rate-limit headers** and convert transport failures into a cached/demo fallback with a visible reason.
- [ ] **Step 6: Run** `python -m unittest tests.test_twitch_provider -v`.

### Task 8: Streamer Opportunity Score

**Files:**
- Create: `gamepulse/streamer_opportunity.py`
- Create: `gamepulse/ui/streamer.py`
- Test: `tests/test_streamer_opportunity.py`

**Interfaces:**
- Produces: `score_game_opportunities(trends: list[GameTrend], profile: StreamerProfile) -> list[GameOpportunity]`

- [ ] **Step 1: Write ranking tests** where strong demand with moderate competition beats both an empty category and an overcrowded category.
- [ ] **Step 2: Implement score components:** viewer demand 30%, viewer-to-channel ratio 25%, recent growth 20%, genre-history fit 15%, and channel-size suitability 10%.
- [ ] **Step 3: Return component values and explanations** with every score; mark partial Twitch crawls as observed totals.
- [ ] **Step 4: Render** trend, competition, recommendation, and evidence panels with Live/Cached/Demo labels.
- [ ] **Step 5: Run** `python -m unittest tests.test_streamer_opportunity -v`.

### Task 9: Public Steam market snapshots and Developer view

**Files:**
- Create: `gamepulse/providers/steam_market.py`
- Create: `gamepulse/market_analysis.py`
- Create: `gamepulse/ui/developer.py`
- Create: `scripts/collect_public_market_snapshot.py`
- Test: `tests/test_market_analysis.py`

**Interfaces:**
- Produces: `MarketSnapshot` containing official seller rank, current/peak players, ownership range, review count, price, and discount.
- Produces: `analyze_market(app_id: int, comparable_limit: int = 10) -> MarketAnalysis`

- [ ] **Step 1: Write fixture tests** that keep verified rank separate from estimated owners/revenue.
- [ ] **Step 2: Implement collectors** for documented/public sources chosen during implementation review; persist source URL, method, timestamp, and confidence for every field.
- [ ] **Step 3: Select comparable games** using genre/tag similarity, release-age band, price band, and audience-size band.
- [ ] **Step 4: Calculate estimated gross-revenue scenarios** from ownership bounds and observed price history, with free-to-play and missing-price branches.
- [ ] **Step 5: Render** market position, comparable games, ownership/revenue estimates, caveats, and data provenance.
- [ ] **Step 6: Run** `python -m unittest tests.test_market_analysis -v` and a single bounded collector smoke test that prints no credentials.

### Task 10: Developer Streamer Fit Score

**Files:**
- Create: `gamepulse/streamer_fit.py`
- Modify: `gamepulse/ui/developer.py`
- Test: `tests/test_streamer_fit.py`

**Interfaces:**
- Produces: `rank_streamers(game: GameSummary, streamers: list[StreamerProfile], tier: ChannelTier | None) -> list[StreamerFit]`

- [ ] **Step 1: Write tests** for genre overlap, language filtering, tier filtering, and deterministic tie-breaking.
- [ ] **Step 2: Implement score components:** game/genre history 35%, audience suitability 20%, engagement proxy 15%, similar-game evidence 15%, language 10%, and discoverability 5%.
- [ ] **Step 3: Render** emerging, mid-size, and large creator shortlists with evidence and no contact automation.
- [ ] **Step 4: Run** `python -m unittest tests.test_streamer_fit -v`.

### Task 11: Review NLP and optional Mistral summary

**Files:**
- Create: `gamepulse/review_analysis.py`
- Create: `gamepulse/providers/mistral.py`
- Modify: `gamepulse/ui/player.py`
- Modify: `gamepulse/ui/developer.py`
- Test: `tests/test_review_analysis.py`

**Interfaces:**
- Produces: `analyze_reviews(app_id: int, limit: int = 5000) -> ReviewAnalysis`
- Produces: `MistralProvider.summarize(analysis: ReviewAnalysis) -> str`

- [ ] **Step 1: Write tests** for language filtering, positive/negative theme extraction, representative excerpts, and deterministic fallback summaries.
- [ ] **Step 2: Implement local analysis** using dated English reviews, phrase frequency, recommendation labels, and bounded representative excerpts.
- [ ] **Step 3: Send only aggregate themes and short excerpts to Mistral** when configured; do not send Steam profile data.
- [ ] **Step 4: Validate generated output** and fall back locally on timeout, invalid format, or absent credentials.
- [ ] **Step 5: Run** `python -m unittest tests.test_review_analysis -v`.

### Task 12: Forecasting and honest sales-potential scenarios

**Files:**
- Create: `gamepulse/forecasting.py`
- Create: `scripts/train_forecast.py`
- Modify: `gamepulse/ui/developer.py`
- Test: `tests/test_forecasting.py`

**Interfaces:**
- Produces: `backtest_review_forecast(frame: pd.DataFrame, horizon_days: int = 30) -> BacktestReport`
- Produces: `forecast_review_activity(app_id: int, horizon_days: int = 30) -> ForecastRange`
- Produces: `derive_market_scenarios(forecast: ForecastRange, market: MarketSnapshot) -> list[MarketScenario]`

- [ ] **Step 1: Write tests** preventing future leakage, enforcing chronological splits, and checking low/expected/high bounds are ordered and non-negative.
- [ ] **Step 2: Aggregate dated reviews daily** and compare seasonal-naive, moving-average, and regularized feature models on rolling time splits.
- [ ] **Step 3: Select the trained model only when it beats the recent-activity baseline** on MAE; otherwise deploy the baseline and report that decision.
- [ ] **Step 4: Derive ownership/revenue potential as scenarios** using documented assumptions and current public market signals; never treat these derived values as training labels or verified sales.
- [ ] **Step 5: Render** a 30-day chart, confidence interval, back-test error, baseline comparison, and plain-language limitations.
- [ ] **Step 6: Run** `python -m unittest tests.test_forecasting -v`, then `python scripts/train_forecast.py --database data/prototype/gamepulse_prototype.sqlite3 --output data/prototype/models`.

### Task 13: End-to-end acceptance and demo handoff

**Files:**
- Create: `tests/test_vertical_slice.py`
- Create: `docs/prototype/demo-script.md`
- Create: `docs/prototype/setup.md`
- Modify: `data/prototype/README.md`

**Interfaces:**
- Consumes: all preceding public interfaces.
- Produces: a repeatable five-to-eight-minute demonstration and setup guide.

- [ ] **Step 1: Add an end-to-end service test** selecting the curated game and asserting non-empty Player recommendations, Streamer opportunities, Developer comparables/streamer fits, review analysis, and a forecast or baseline result.
- [ ] **Step 2: Run the complete suite:** `python -m unittest discover -s tests -v`.
- [ ] **Step 3: Run dataset verification:** `python scripts/prepare_datasets.py --verify --output-root data/processed/2026-08-01`.
- [ ] **Step 4: Rebuild the prototype database from scratch** and launch `streamlit run app.py`.
- [ ] **Step 5: Execute the demo script** in Demo mode, then simulate missing Steam/Twitch/Mistral credentials and confirm every mode remains usable.
- [ ] **Step 6: Document exact setup** for `.env`, profile privacy, Twitch verification, source labels, known model limitations, database rebuild, and application startup.

## Delivery Milestones

1. **Foundation demo:** Tasks 1–4; searchable catalogue and connected navigation.
2. **Player value:** Tasks 5–6; explainable recommendations from a public Steam profile or manual preferences.
3. **Streamer value:** Tasks 7–8; reliable demo/cached/live architecture and Opportunity Score.
4. **Developer value:** Tasks 9–10; market benchmarking, estimated revenue scenarios, and Streamer Fit.
5. **Intelligence layer:** Tasks 11–12; review themes, optional Mistral summaries, and evaluated forecasts.
6. **Showcase-ready prototype:** Task 13; repeatable setup, acceptance checks, and demo script.

## Self-Review Results

- All agreed Player, Streamer, and Developer capabilities map to at least one task.
- Twitch verification and Steam profile/API unavailability both have working fallbacks.
- Exact sales are never promised; official rankings, estimated ownership, and derived scenarios remain visibly distinct.
- Forecast training uses only time-appropriate features and must beat a baseline before adoption.
- No production deployment, Docker, account system, private financial access, or automated outreach has entered version-one scope.

