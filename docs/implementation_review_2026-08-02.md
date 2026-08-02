# GamePulse Implementation Review

Date: 2026-08-02
Purpose: review the completed Twitch, scoring, mapping, persistence, and UI work with Sol before selecting the next implementation step.

## Executive summary

The prototype now has an end-to-end, labelled Twitch data path:

`Demo/live Twitch provider → normalized observations → SQLite snapshots → Steam mapping → streamer opportunity score → developer promotion fit → Streamlit UI`

The two recommendation decisions remain separate:

1. **Streamer Mode:** which game or Twitch category should this streamer broadcast?
2. **Developer Mode:** which streamer is a suitable public-signal fit for promoting this game?

The implementation preserves Streamlit, SQLite, Demo mode without credentials, shared selected-game state, existing source labels, Player Mode, and the rule against Twitch webpage scraping. Mistral is still not integrated.

## Completed work

### 1. Twitch provider

Implemented in `gamepulse/providers/twitch.py` and `tests/test_twitch_provider.py`:

- Expanded `GameTrend` with rank, concentration, age, language, coverage, partial-coverage, and observed-total fields.
- Expanded `StreamerObservation` with stream, login, title, timing, image, broadcaster, and category-rank fields.
- Added bounded `/helix/streams` pagination with 100 rows per page, cursor handling, a configurable page limit, deduplication, empty-page termination, and partial-result labels.
- Added rate-limit header tracking, one token refresh after `401`, safe `429` handling, low-capacity request stopping, and Demo fallback on transport failure.
- Added configuration for `TWITCH_MAX_STREAM_PAGES` and `TWITCH_REQUEST_TIMEOUT_SECONDS`.
- Derived observed viewers, observed channels, viewer/channel ratio, concentration, stream age, language counts, and coverage counts.

These values are explicitly treated as **observed totals**, not complete Twitch totals.

### 2. Twitch snapshot persistence and collection

Implemented in `gamepulse/database.py`, `scripts/collect_twitch_snapshot.py`, and related tests:

- Added normalized `twitch_game_snapshots` persistence.
- Added normalized `twitch_streamer_snapshots` persistence.
- Added indexes for observation time, game/category history, streamer history, and rank lookup.
- Added duplicate-safe upserts and rebuild-compatible schema migration helpers.
- Added Demo collection support without credentials.
- Collection reports source mode, observation time, pages, streams, categories, streamers, and partial coverage.
- Raw API payloads are not persisted as application data.

### 3. Steam-to-Twitch mapping

Implemented in `gamepulse/game_mapping.py`, `data/manual/twitch_steam_aliases.json`, and `tests/test_game_mapping.py`:

- Added normalized name matching for case, punctuation, symbols, spaces, hyphens, and colons.
- Added exact matching, explicit aliases, conservative fuzzy candidates, and manual verification flags.
- Excluded obvious demos and playtests unless explicitly mapped.
- Preserved weak or ambiguous matches as unverified.
- Prevented automatic mappings from overwriting manual mappings.
- Added the `twitch_game_mappings` table and idempotent persistence.

Twitch-only categories remain usable; Steam genres, tags, reviews, and ownership data are only joined when the mapping is reliable enough.

### 4. Streamer Opportunity Score

Implemented in `gamepulse/streamer_opportunity.py` and `tests/test_streamer_opportunity.py`:

- Added normalized Demand, Reachability, Momentum, Competition, Stability, Preference Fit, and Tier Suitability components.
- Added Balanced, Reach, Growth, and Community strategies with explicit weight changes.
- Added log-scaled demand, capped reachability, minimum viable demand, non-empty competition handling, trend availability reweighting, concentration cautions, freshness cautions, and confidence separate from score.
- Expanded `GameOpportunity` with score band, reasons, cautions, component values, observed metrics, trend direction, confidence, source mode, observation time, and Steam App ID.
- Scores remain bounded from 0 to 100 with deterministic sorting.

### 5. Developer-to-streamer fit score

Implemented in `gamepulse/streamer_fit.py` and `tests/test_streamer_fit.py`:

- Added typed `PromotionCampaignProfile` with objective, languages, preferred tiers, similar games, and context-only budget positioning.
- Added category-history, similar-game, audience suitability, consistency, momentum, language, discoverability, and data-confidence components.
- Missing components are unavailable, reweighted, and called out in cautions.
- Added aggregate viewer metrics, primary-category share, source mode, observation time, profile image, channel URL, and confidence metadata to fit results.
- No sponsorship prices, conversion rates, sales forecasts, or guaranteed outcomes are estimated.

### 6. Streamer Mode UI

Implemented in `gamepulse/ui/streamer.py`, `gamepulse/ui/streamer_components.py`, `gamepulse/ui/streamer_theme.py`, and `tests/test_streamer_ui.py`:

- Added Game Opportunities, Category Deep Dive, and Creator Landscape tabs.
- Added channel tier, strategy, language, Steam genre/tag, Twitch tag, minimum-viewer, competition, and Twitch-only controls.
- Added current observed metrics, historical display, concentration, language distribution, Plotly trend output when history exists, Steam metadata, provenance labels, cautions, and confidence separation.
- Added caching for provider calls and read-only database queries.
- Escaped Twitch-derived HTML text and validated URLs.
- Kept Creator Landscape informational and separate from Developer Mode promotion ranking.

### 7. Developer Mode UI

Implemented in `gamepulse/ui/developer.py`, `gamepulse/ui/developer_components.py`, `gamepulse/ui/developer_theme.py`, and `tests/test_developer_components.py` / `tests/test_developer_ui.py`:

- Added campaign objective, target-language, preferred-tier, budget-positioning, recommendation-count, selected-game-history, and similar-specialist controls.
- Replaced the minimal streamer shortlist with detailed Promotion Fit cards.
- Cards show score, score band, confidence, audience metrics, category history, language, tier, growth, reasons, cautions, component breakdown, source mode, observation time, profile image, and Twitch link.
- Added comparison of two or three selected recommendations across the requested measures.
- Added a downloadable CSV containing derived recommendation fields only.
- Preserved Market Signals, Comparable Games, Review Themes, Forecast, and Opportunity Score sections.
- Preserved the Opportunity Score’s selected-game creator input even when similar-game specialists are included in the shortlist.

## Preserved constraints

- Streamlit remains the application framework.
- SQLite remains the disposable persistence layer.
- Demo mode works without Twitch credentials.
- Player Mode and shared selected-game state remain intact.
- Existing source labels remain visible across Demo, Live, Cached, and Fallback paths.
- No scraping of TwitchTracker, SullyGnome, or Twitch webpages was added.
- No Mistral integration was added.
- No tokens, credentials, raw API responses, private data, sponsorship prices, or conversion predictions are exported.

## Verification evidence

Final integrated verification in the current workspace:

- `python -m unittest discover -s tests -q` — 190 passed.
- `python -m compileall -q app.py gamepulse scripts tests` — passed.
- Focused Twitch, provenance, creator-tier, aggregation, growth-window, confidence, and batched-read tests — 91 passed.
- Named mocked complete-live, rate-limited-partial, transport-fallback, bounded-collection, and persisted-coverage subset — 9 passed (included in the focused suite above).
- Pre-fix Twitch schema migration harness — passed; existing rows were preserved and required columns/indexes were added.
- Headless `streamlit run app.py` health endpoint — HTTP 200; Home, Player, Streamer, and Developer AppTest loads — passed.
- Creator CSV audit — 34 derived recommendation columns; no credential, raw-payload, pricing, conversion, sales, or revenue fields.

## Known limitations

1. Twitch API observations are bounded samples, not full market totals. Partial coverage and concentration can materially affect rankings.
2. Demo data contains very limited historical depth, so growth, volatility, and median/peak metrics may be unavailable or directional.
3. Historical aggregates are currently derived from persisted snapshot rows at read time; there is not yet a dedicated long-term aggregate table or scheduled retention policy.
4. Similar-game specialists depend on overlap between catalog comparables and Twitch category names. A comparable game absent from the current Twitch snapshot cannot contribute a creator.
5. Campaign objectives are captured and shown as campaign context, but the current fit formula does not assign separate objective-specific weights.
6. Budget positioning is intentionally a qualitative filter/context field and is not a price or reach-cost model.
7. Live operation still needs repeated observation collection, credential rotation practices, monitoring, and production-scale rate-limit validation.

## Recommended next step

The next step should be **historical Twitch evidence hardening and live acceptance validation**, before adding more recommendation sophistication:

1. Define the observation retention window and collection cadence.
2. Add a dedicated aggregate/read-model layer for streamer and category history, with explicit freshness and observation-count rules.
3. Run several authorized live collection cycles and compare Demo, Cached, Fallback, and Live labels.
4. Validate score stability, partial-coverage behavior, and mapping reliability on categories outside the Demo fixture.
5. Review whether campaign objectives should change weights or remain context-only.
6. Add a small operator report for rate-limit capacity, stale data, unmapped categories, and failed collection runs.

## Questions for review with Sol

- Should campaign objectives remain context-only, or should each objective receive approved fit-weight adjustments?
- What historical retention window is sufficient for one-day and seven-day growth without overstating confidence?
- Should similar-game specialists be included by default in Developer Mode, or only after explicit opt-in?
- What threshold should qualify a fuzzy Steam mapping for Steam-derived evidence?
- Which live collection cadence and freshness labels are acceptable for the next demo milestone?
