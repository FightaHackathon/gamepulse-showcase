# GamePulse Player Mode UI/UX Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Player Mode into a polished dark-navy gaming intelligence workspace with explicit Steam/manual personalization, meaningful Best Matches and Hidden Gems modes, normalized recommendation scores, and responsive visual game cards.

**Architecture:** Keep Streamlit as the UI shell and SQLite as the catalogue. Separate recommendation policy, Steam profile session state, presentation models, and rendering helpers so each can be tested independently. The page orchestrator reads session state and calls these focused services; it never performs a Steam request unless the player submits Analyze or Refresh.

**Tech Stack:** Python 3.12, Streamlit 1.40+, SQLite, standard-library `unittest`, existing GamePulse providers and prepared datasets.

## Global Constraints

- Implement only Player Mode; do not redesign Home, Streamer or Developer Mode in this increment.
- Keep the prototype local-only, available while the prototype computer is running.
- Do not add Docker, a production frontend framework, cloud storage or user accounts.
- Never request or persist Steam passwords, cookies or private-library data.
- Keep a loaded Steam library in Streamlit session memory only.
- Do not claim ownership estimates are verified purchases or downloads.
- Preserve manual Player Mode when Steam credentials are absent or requests fail.
- Use the approved design specification at `docs/superpowers/specs/2026-08-01-player-mode-ui-ux-design.md` as the visual and UX source of truth.
- Use the existing dependency versions in `requirements.txt`; do not add a UI package for this redesign.
- Follow test-driven development: add one failing behavioral test, confirm the expected failure, implement the smallest behavior, then rerun the focused and full suites.
- The workspace is not a Git repository. Do not initialize Git or add commit steps; record each completed task by checking its boxes in this document.

---

## File responsibility map

| File | Responsibility |
|---|---|
| `gamepulse/recommendations.py` | Recommendation inputs, normalized score components, discovery policy and result model |
| `gamepulse/player_session.py` | Session-only Steam profile analysis state and transitions |
| `gamepulse/catalog.py` | Searchable tag/genre options used by manual personalization |
| `gamepulse/ui/player_theme.py` | Player-specific design tokens and scoped responsive CSS |
| `gamepulse/ui/player_components.py` | Hero, personalization, filters, status and recommendation-card renderers |
| `gamepulse/ui/player.py` | Thin page orchestrator connecting session state, services and components |
| `tests/test_recommendations.py` | Score, filter, ownership, deduplication and discovery-mode behavior |
| `tests/test_player_session.py` | Analyze/Refresh state, failures and no-repeat provider behavior |
| `tests/test_catalog.py` | Manual tag/genre option behavior |
| `tests/test_player_theme.py` | Required design tokens, accessibility and responsive CSS contracts |
| `tests/test_player_ui.py` | Streamlit page interactions and rendered Player Mode states |

---

### Task 1: Define Player presentation contracts and theme

**Files:**
- Create: `gamepulse/ui/player_theme.py`
- Test: `tests/test_player_theme.py`

**Interfaces:**
- Produces: `PLAYER_COLORS: dict[str, str]`
- Produces: `player_css() -> str`
- Produces: `inject_player_theme(st) -> None`

- [ ] **Step 1: Write the failing theme-contract tests**

Create `tests/test_player_theme.py` with assertions for every approved token and the two responsive/accessibility rules:

```python
import unittest

from gamepulse.ui.player_theme import PLAYER_COLORS, player_css


class PlayerThemeTests(unittest.TestCase):
    def test_approved_color_tokens_are_present(self):
        self.assertEqual(PLAYER_COLORS["canvas"], "#080D18")
        self.assertEqual(PLAYER_COLORS["surface"], "#111A2B")
        self.assertEqual(PLAYER_COLORS["primary"], "#4C8DFF")
        self.assertEqual(PLAYER_COLORS["personalization"], "#8B7CFF")
        self.assertEqual(PLAYER_COLORS["primary_text"], "#F4F7FC")

    def test_css_contains_mobile_and_reduced_motion_rules(self):
        css = player_css()
        self.assertIn("@media (max-width: 640px)", css)
        self.assertIn("@media (prefers-reduced-motion: reduce)", css)
        self.assertIn("min-height: 44px", css)
        self.assertIn(":focus-visible", css)
```

- [ ] **Step 2: Run the test and confirm the expected failure**

Run:

```powershell
python -m unittest tests.test_player_theme -v
```

Expected: import failure for `gamepulse.ui.player_theme`.

- [ ] **Step 3: Implement the approved token map and scoped CSS**

Create `gamepulse/ui/player_theme.py`. `player_css()` must return one `<style>` payload scoped to Streamlit keys beginning with `gp_player_`. It must include:

```python
PLAYER_COLORS = {
    "canvas": "#080D18",
    "surface": "#111A2B",
    "elevated_surface": "#172338",
    "border": "#273550",
    "primary": "#4C8DFF",
    "personalization": "#8B7CFF",
    "success": "#52D6A0",
    "warning": "#F2B84B",
    "error": "#FF6B78",
    "primary_text": "#F4F7FC",
    "secondary_text": "#9EABC0",
}


def inject_player_theme(st) -> None:
    st.markdown(player_css(), unsafe_allow_html=True)
```

CSS requirements:

- 14 px panel/card radius and 10 px control radius.
- 24 px desktop and 16 px mobile panel padding.
- A 2 px `#4C8DFF` `:focus-visible` ring.
- Minimum 44 px interactive-control height.
- A 160 ms card hover transition with at most 3 px vertical movement.
- One-column layout below 640 px and no horizontal page overflow.
- Motion disabled inside `prefers-reduced-motion: reduce`.
- No unscoped selectors that restyle Streamer or Developer Mode.

- [ ] **Step 4: Run the focused test**

Run: `python -m unittest tests.test_player_theme -v`  
Expected: two tests pass.

- [ ] **Step 5: Run the complete suite**

Run: `python -m unittest discover -s tests -q`  
Expected: all existing tests plus the two new tests pass.

---

### Task 2: Normalize recommendation scoring and split discovery modes

**Files:**
- Modify: `gamepulse/recommendations.py:10-106`
- Modify: `tests/test_recommendations.py`

**Interfaces:**
- Produces: `DiscoveryMode = Literal["best_matches", "hidden_gems"]`
- Produces: `ScoreComponents`
- Modifies: `PlayerPreferences.discovery_mode: DiscoveryMode`
- Modifies: `Recommendation.match_score: int`
- Produces: `Recommendation.score_band: str`
- Adds presentation fields to `Recommendation`: `release_year`, `header_image_url`, `owners_low`, `owners_high`, `windows`, `mac`, `linux`

- [ ] **Step 1: Replace the hidden-gem bonus test with policy tests**

Add tests proving:

```python
def test_match_scores_are_normalized_and_have_three_or_fewer_reasons(self):
    results = engine.recommend_similar(10, PlayerPreferences(), limit=10)
    self.assertTrue(all(55 <= item.match_score <= 100 for item in results))
    self.assertTrue(all(1 <= len(item.reasons) <= 3 for item in results))

def test_hidden_gems_exclude_the_highest_popularity_tier(self):
    results = engine.recommend_similar(
        10,
        PlayerPreferences(discovery_mode="hidden_gems"),
        limit=10,
    )
    self.assertTrue(results)
    self.assertTrue(all((item.owners_high or 0) < 5_000_000 for item in results))

def test_best_matches_can_include_a_popular_high_similarity_game(self):
    results = engine.recommend_similar(
        10,
        PlayerPreferences(discovery_mode="best_matches"),
        limit=10,
    )
    self.assertIn(20, [item.app_id for item in results])
```

Extend the fixture `games` table so it includes `windows`, `mac`, `linux`, and one candidate with `owners_high >= 5_000_000`.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `python -m unittest tests.test_recommendations -v`  
Expected: failures because `discovery_mode`, `match_score` and the ownership cutoff are not implemented.

- [ ] **Step 3: Introduce exact score components**

Implement:

```python
@dataclass(frozen=True)
class ScoreComponents:
    tag_match: float
    genre_match: float
    preference_match: float
    review_quality: float
    price_fit: float
    platform_fit: float

    @property
    def total(self) -> int:
        raw = (
            self.tag_match * 30
            + self.genre_match * 20
            + self.preference_match * 20
            + self.review_quality * 15
            + self.price_fit * 5
            + self.platform_fit * 10
        )
        return max(0, min(100, round(raw)))
```

Each component must be clamped to `0.0..1.0`. Use:

- `tag_match`: seed-tag intersection divided by seed-tag count.
- `genre_match`: seed-genre intersection divided by seed-genre count.
- `preference_match`: candidate intersection divided by the number of selected manual/inferred preferences; use `0.0` when no preferences exist.
- `review_quality`: existing normalized review score.
- `price_fit`: `1.0` after satisfying an active price ceiling, `0.7` when no ceiling exists.
- `platform_fit`: `1.0` after satisfying an active platform filter, `0.7` when no platform filter exists.

Map score bands exactly:

```python
def score_band(score: int) -> str:
    if score >= 85:
        return "Excellent match"
    if score >= 70:
        return "Strong match"
    return "Worth exploring"
```

Do not display candidates below 55.

- [ ] **Step 4: Implement Hidden Gems as a policy**

Replace `prefer_hidden_gems` with `discovery_mode`. For `hidden_gems`:

- Exclude candidates with `owners_high >= 5_000_000`.
- Add 10 score points after normalization when `owners_high <= 250_000`.
- Add 5 score points when `250_000 < owners_high <= 1_000_000`.
- Subtract 10 points when `1_000_000 < owners_high < 5_000_000`.
- Treat missing ownership as unknown: do not add a bonus, and add the reason `audience size is not available` only when fewer than three stronger reasons exist.

Clamp again to `0..100`. Continue excluding owned games, the seed game and duplicate case-insensitive names.

- [ ] **Step 5: Populate the enriched recommendation model**

Use values already present in the `games` row. The external link is deterministic:

```python
steam_store_url = f"https://store.steampowered.com/app/{candidate_id}"
release_year = str(row["release_date"])[:4] if row["release_date"] else None
```

Generate a maximum of three reasons in this priority order: selected preference, tag/genre similarity, review quality, platform, price, estimated audience.

- [ ] **Step 6: Run focused and complete tests**

Run:

```powershell
python -m unittest tests.test_recommendations -v
python -m unittest discover -s tests -q
```

Expected: all tests pass and no old reference to `prefer_hidden_gems` remains.

---

### Task 3: Supply searchable manual-preference options

**Files:**
- Modify: `gamepulse/catalog.py:15-58`
- Modify: `tests/test_catalog.py`

**Interfaces:**
- Produces: `PreferenceOptions(tags: tuple[str, ...], genres: tuple[str, ...])`
- Produces: `Catalog.preference_options(limit_per_group: int = 500) -> PreferenceOptions`

- [ ] **Step 1: Write the failing catalogue-options test**

Add a fixture with repeated and differently cased tag/genre values, then assert:

```python
options = catalog.preference_options(limit_per_group=20)
self.assertEqual(options.tags, ("Fantasy", "FPS"))
self.assertEqual(options.genres, ("Action", "Role-Playing"))
```

The expected behavior is case-insensitive deduplication and alphabetical display labels.

- [ ] **Step 2: Run the test and confirm the expected failure**

Run: `python -m unittest tests.test_catalog -v`  
Expected: `Catalog` has no `preference_options` method.

- [ ] **Step 3: Implement one bounded query per option group**

Use parameterized limits and return typed tuples. Do not issue one SQL query per game. Limit each group to `1..1000` values after deduplicating in SQL.

```python
@dataclass(frozen=True)
class PreferenceOptions:
    tags: tuple[str, ...]
    genres: tuple[str, ...]
```

Order values with `ORDER BY value COLLATE NOCASE`; deduplicate with a casefolded key while preserving the first display value.

- [ ] **Step 4: Verify catalogue and full suites**

Run:

```powershell
python -m unittest tests.test_catalog -v
python -m unittest discover -s tests -q
```

Expected: all tests pass.

---

### Task 4: Add explicit session-only Steam analysis state

**Files:**
- Create: `gamepulse/player_session.py`
- Create: `tests/test_player_session.py`
- Consume existing: `gamepulse/providers/steam.py`
- Consume existing: `gamepulse/player_profile.py`

**Interfaces:**
- Produces: `ProfileStatus = Literal["disconnected", "loading", "connected", "private", "rate_limited", "unavailable"]`
- Produces: `PlayerProfileSession`
- Produces: `empty_profile_session() -> PlayerProfileSession`
- Produces: `analyze_public_profile(profile_input: str, provider: SteamProvider, catalog: Catalog) -> PlayerProfileSession`

- [ ] **Step 1: Write state-transition tests before production code**

Use a fake provider that counts `resolve_profile` and `get_library` calls. Cover:

```python
def test_successful_analysis_returns_session_only_library_and_preferences():
    result = analyze_public_profile(profile, provider, catalog)
    self.assertEqual(result.status, "connected")
    self.assertEqual(result.owned_app_ids, frozenset({10, 20}))
    self.assertTrue(result.preferences.preferred_tags)
    self.assertEqual(provider.library_calls, 1)

def test_private_and_rate_limited_failures_have_distinct_states():
    self.assertEqual(private_result.status, "private")
    self.assertEqual(rate_limited_result.status, "rate_limited")

def test_empty_state_contains_no_library_or_profile_identifier():
    state = empty_profile_session()
    self.assertEqual(state.status, "disconnected")
    self.assertFalse(state.owned_app_ids)
    self.assertIsNone(state.steam_id)
```

- [ ] **Step 2: Run tests and confirm import failure**

Run: `python -m unittest tests.test_player_session -v`  
Expected: import failure for `gamepulse.player_session`.

- [ ] **Step 3: Implement the state model**

Use an immutable dataclass:

```python
@dataclass(frozen=True)
class PlayerProfileSession:
    status: ProfileStatus
    profile_input: str = ""
    steam_id: str | None = None
    library: PlayerLibrary | None = None
    owned_app_ids: frozenset[int] = frozenset()
    preferences: PlayerPreferences = PlayerPreferences()
    message: str = ""
```

`analyze_public_profile` must call resolve once, library once, infer preferences once and map failures as follows:

- Error message contains `private` → `private`.
- Error message contains `rate limit` → `rate_limited`.
- Other `SteamProviderError`, `RuntimeError` or `ValueError` → `unavailable`.
- Never place the API key, request URL or raw response in `message`.

- [ ] **Step 4: Verify focused and complete suites**

Run:

```powershell
python -m unittest tests.test_player_session -v
python -m unittest discover -s tests -q
```

Expected: all tests pass.

---

### Task 5: Build focused Player Mode rendering components

**Files:**
- Create: `gamepulse/ui/player_components.py`
- Modify: `gamepulse/ui/player.py:1-57`
- Modify: `gamepulse/ui/shared.py:24-33` only if the hero replaces the shared header for Player Mode
- Create: `tests/test_player_ui.py`

**Interfaces:**
- Produces: `render_player_hero(st, game, source_label: str) -> None`
- Produces: `render_personalization(st, profile_state, settings, options) -> PersonalizationAction`
- Produces: `render_player_filters(st) -> PlayerPreferences`
- Produces: `render_recommendation_card(st, recommendation, featured: bool = False) -> None`
- Produces: `render_recommendation_empty_state(st, preferences) -> None`
- Keeps: `gamepulse.ui.player.render(st, settings, catalog, state) -> DemoState`

- [ ] **Step 1: Write a Streamlit interaction test for manual mode**

Use `streamlit.testing.v1.AppTest` and the real disposable database. Assert that Player Mode contains:

- Heading `Player Mode`.
- Button `Analyze public library`.
- Manual tag and genre multiselects.
- Discovery selector with `Best matches` and `Hidden gems`.
- Platform selector with all four values.
- At least one `Match` label and one `View on Steam` link.

Set Linux and one available tag, rerun, then assert every visible recommendation reason includes the active platform or selected preference evidence.

- [ ] **Step 2: Run the UI test and confirm it fails on the old controls**

Run: `python -m unittest tests.test_player_ui -v`  
Expected: failure because the current page uses text inputs, a checkbox and raw scores.

- [ ] **Step 3: Implement the hero**

In `render_player_hero`:

- Escape all text inserted into HTML with `html.escape`.
- Use `game.header_image_url` only when non-empty; otherwise render `.gp-player-hero--placeholder`.
- Show title, release year, price, review score, platform badges, source label and the approved one-sentence purpose.
- Use a keyed container such as `st.container(key="gp_player_hero")` so theme selectors remain scoped.
- Keep maximum visual height at 280 px desktop and 220 px mobile.

- [ ] **Step 4: Implement explicit Steam actions and session storage**

In `gamepulse/ui/player.py`, initialize once:

```python
if "player_profile_session" not in st.session_state:
    st.session_state.player_profile_session = empty_profile_session()
```

Render the profile input inside `st.form("gp_player_steam_form")`. Only call `analyze_public_profile` when the Analyze submit button is true. When connected, render Refresh and Clear buttons; Refresh explicitly repeats analysis, while Clear restores `empty_profile_session()`.

Do not call `SteamProvider.resolve_profile` or `get_library` from the ordinary render path. Price, platform, manual chips and discovery changes must reuse `st.session_state.player_profile_session`.

- [ ] **Step 5: Replace comma-separated preferences with catalogue multiselects**

Use `Catalog.preference_options()` values:

```python
manual_tags = tuple(st.multiselect("Preferred tags", options.tags, key="gp_player_tags"))
manual_genres = tuple(st.multiselect("Preferred genres", options.genres, key="gp_player_genres"))
```

Merge inferred and manual values case-insensitively. Render at most eight visible chips and a `+N more` summary. Provide a `Clear preferences` button that clears both widget keys.

- [ ] **Step 6: Implement compact filters and Reset**

- Discovery: horizontal `Best matches` / `Hidden gems` selector mapped to `best_matches` / `hidden_gems`.
- Platform: `Any`, `Windows`, `macOS`, `Linux`.
- Price: `Any price`, `Free only`, `Under $10`, `Under $30`, `Custom`.
- Show the numeric custom input only for `Custom`.
- Translate `Free only` to `max_price_usd=0.0`; `Any price` to `None`.
- Render an active-filter summary and `Reset filters` whenever state differs from Best Matches + Any platform + Any price.

- [ ] **Step 7: Render visual recommendation cards**

For each result:

- Use artwork or the gradient placeholder.
- Show `Match {match_score}` and `score_band`.
- Show at most three reason chips.
- Show release year, price, review score, platform icons and `Estimated audience` bounds.
- Use `st.link_button("View on Steam", recommendation.steam_store_url)`.
- Mark only index zero as featured.
- Never use unsafe raw game text in HTML without `html.escape`.

When there are no results, name the restrictive active filters and show a Reset action. Wrap recommendation loading in `st.spinner("Finding strong matches…")`; do not simulate loading with a fixed sleep.

- [ ] **Step 8: Verify UI and full suites**

Run:

```powershell
python -m unittest tests.test_player_ui -v
python -m unittest discover -s tests -q
```

Expected: all tests pass. Confirm that the fake provider call count remains unchanged when only a filter widget changes.

---

### Task 6: Add explicit error, empty and missing-artwork coverage

**Files:**
- Modify: `tests/test_player_ui.py`
- Modify: `gamepulse/ui/player_components.py`
- Modify: `gamepulse/ui/player.py`

**Interfaces:**
- Consumes: `PlayerProfileSession.status`
- Produces: complete UI treatment for every approved state

- [ ] **Step 1: Add failing tests for each state**

Test these exact visible outcomes:

| State | Required visible copy/action |
|---|---|
| Missing API key | Public-profile fallback is available for recent public games; manual mode remains ready. |
| Private profile | `Game Details are private.` plus manual-preference controls |
| Rate limited | `Steam is temporarily rate limited.` plus retained recommendations |
| Empty results | `No games match all active filters.` plus `Reset filters` |
| Missing artwork | `.gp-game-art-placeholder` exists; no broken image element |
| Connected | game count, inferred chips, Refresh and Clear actions |

Use injected fake state/provider objects; do not make network calls.

- [ ] **Step 2: Run and confirm the state tests fail**

Run: `python -m unittest tests.test_player_ui -v`  
Expected: failures for state-specific copy or controls not yet rendered.

- [ ] **Step 3: Implement state renderers with text and icons**

Use color plus a visible text label for every state. Preserve existing recommendation cards during Steam errors by computing recommendations from manual/default preferences and the last successful session state when available.

Do not expose exception reprs, keys, request URLs or raw response bodies.

- [ ] **Step 4: Verify Player and provider suites**

Run:

```powershell
python -m unittest tests.test_player_ui tests.test_player_session tests.test_steam_provider -v
python -m unittest discover -s tests -q
```

Expected: all tests pass.

---

### Task 7: Complete rendered accessibility and responsive QA

**Files:**
- Modify: `gamepulse/ui/player_theme.py`
- Modify: `gamepulse/ui/player_components.py`
- Modify: `tests/test_player_ui.py`
- Modify: `docs/prototype/demo-script.md`

**Interfaces:**
- Consumes: the completed Player Mode page
- Produces: repeatable desktop/mobile QA evidence and demo steps

- [ ] **Step 1: Add structural accessibility assertions**

Extend `tests/test_player_ui.py` to assert:

- Each interactive control has a visible label.
- Every artwork image has alt text containing its game title.
- The external Steam action includes the game title in adjacent card content.
- Loading/error states include text, not color alone.
- Headings follow hero → personalization → filters → recommendations order.

- [ ] **Step 2: Run the focused test and fix only demonstrated failures**

Run: `python -m unittest tests.test_player_ui -v`.

- [ ] **Step 3: Run the complete automated verification**

Run:

```powershell
python -m unittest discover -s tests -v
python scripts\prepare_datasets.py --verify --output-root data\processed\2026-08-01
```

Expected: zero failed tests and all four dataset validations true.

- [ ] **Step 4: Run the rendered desktop acceptance flow**

Start:

```powershell
streamlit run app.py
```

In the in-app Browser at `http://127.0.0.1:8501/`, verify:

1. Home → Player navigation.
2. Selected-game hero and first recommendation visible without scrolling at a normal desktop viewport.
3. Manual tag selection changes visible evidence.
4. Linux selection removes unsupported games.
5. Hidden Gems removes the highest-popularity tier.
6. Reset restores Best Matches + Any platform + Any price.
7. Missing-key/manual mode remains usable.
8. Browser console has no application errors or relevant warnings.

- [ ] **Step 5: Run the 390×844 mobile acceptance flow**

Set the browser viewport to exactly `390×844`. Verify:

- Sidebar is collapsed by default.
- Hero metadata wraps without overlap.
- Controls and cards use one column.
- No horizontal page scrolling.
- Touch controls are at least 44 px high.
- Long titles do not overlap Match scores.

Reset the viewport after the check.

- [ ] **Step 6: Update the demo script**

Add a two-minute Player Mode segment to `docs/prototype/demo-script.md`:

1. Open the curated Counter-Strike game.
2. Show Best Matches and explain one 0–100 score.
3. Select Linux and show platform evidence.
4. Switch to Hidden Gems and explain estimated audience limits.
5. Show manual preference chips.
6. Explain that public Steam analysis is optional and session-only.

- [ ] **Step 7: Record final evidence**

Record in the task handoff:

- Exact test count and zero-failure output.
- Dataset verification result.
- Desktop and mobile screenshots.
- Browser console result.
- Untested live-Steam cases when credentials are unavailable.

---

## Acceptance checklist for Luna

- [ ] Player Mode matches the approved dark-navy visual tokens.
- [ ] Hero, personalization, filters and results follow the approved information hierarchy.
- [ ] Steam is called only on Analyze or Refresh.
- [ ] Manual mode works with no API key.
- [ ] Best Matches and Hidden Gems are distinct ranking policies.
- [ ] Match scores are integers from 0 to 100 with documented bands.
- [ ] Every recommendation has one to three concrete reasons.
- [ ] Owned, seed and duplicate-name games are excluded.
- [ ] All approved loading, empty and error states are visible and recoverable.
- [ ] Desktop and 390×844 mobile browser checks pass without relevant console errors.
- [ ] Home, Streamer and Developer behavior remains unchanged.

## Copy/paste handoff prompt for Luna

> Implement `docs/superpowers/plans/2026-08-01-player-mode-ui-ux-redesign.md` task by task, using `docs/superpowers/specs/2026-08-01-player-mode-ui-ux-design.md` as the visual source of truth. Use test-driven development and confirm each focused test fails for the expected reason before implementation. Do not redesign Home, Streamer or Developer Mode, do not add Docker or a new frontend framework, and do not persist Steam library data. After every task, run the focused tests and the full unit suite. Finish with in-app Browser verification at desktop and 390×844 mobile sizes, reporting screenshots, console health and any live-Steam flows that remain untested.

## Self-review result

- Spec coverage: all information architecture, visual system, state, responsive, accessibility and acceptance requirements map to Tasks 1–7.
- Scope: Player Mode only; no unrelated frontend migration or cross-mode redesign.
- Type consistency: `PlayerPreferences.discovery_mode`, `Recommendation.match_score`, `PlayerProfileSession` and all rendering interfaces are defined before consumption.
- Credential safety: no task stores secrets or library data outside Streamlit session memory.
- Git handling: no commit or repository-initialization steps are included because the workspace is not a Git repository.
