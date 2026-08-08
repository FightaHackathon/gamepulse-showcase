# GamePulse Desktop Prototype

GamePulse is a **local native PySide6 desktop application** for game-market intelligence across player, creator/streamer, and developer workflows. The default desktop path is source-neutral and works without Twitch credentials.

## Desktop experience

The normal workflow is keyless: Steam public data and the local SQLite database are built in. A
Steam Community profile URL is the primary Streamer Mode input; private libraries fall back to
manual/local signals. Twitch and other creator integrations remain optional and are shown under
Settings / Integrations rather than blocking the core workflow.

The application opens as one native window with four workspaces:

- **Overview** — a fast pulse check on the selected game and its prepared public catalogue signals.
- **Player** — catalogue search plus explainable recommendations using similarity, price, platform support, review quality, and hidden-gem discovery.
- **Streamer** — opportunity ranking from legitimate activity signals such as Steam player activity, review momentum, preference fit, sentiment, promotions, freshness, and competition when a provider actually supplies it.
- **Developer** — market positioning, comparable games, review themes, directional opportunity scoring, creator-fit recommendations, and a 30-day review-activity forecast.

The UI always keeps metric identity and provenance visible. **Steam current players or Steam peak CCU are not Twitch viewers.** If competition data is unavailable, GamePulse displays it as unavailable and excludes that component from scoring instead of treating it as zero competition.

## Run on Windows

The repository stores large prepared assets through Git LFS. After cloning the desktop branch:

```powershell
git lfs pull
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If the prepared SQLite database is present, launch GamePulse with:

```powershell
python app.py
```

Or double-click `run_gamepulse.bat` after dependencies are installed.

If the database is missing, rebuild it first:

```powershell
python scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
python app.py
```

## Default no-Twitch data path

No Twitch key is required for the normal desktop experience.

Game-level signals default to the prepared Steam/public database. Creator recommendations default to the manual/opt-in creator directory plus compatible imported snapshot records. The bundled generic snapshot and demo creator records are explicitly labelled as demo data.

Key source-neutral configuration values in `.env.example` include:

```text
GAME_SIGNAL_PROVIDER=auto
CREATOR_PROVIDER=auto
GAMEPULSE_DATABASE_PATH=data/prototype/gamepulse_prototype.sqlite3
GAMEPULSE_SNAPSHOT_PATH=data/demo/gamepulse_snapshot.json
CREATOR_DIRECTORY_PATH=data/manual/creators.csv
```

`auto` prefers the legitimate local/public sources available to the application and does not require Twitch.

## Optional integrations

Copy `.env.example` to `.env` and fill only integrations you intentionally want to enable:

```powershell
Copy-Item .env.example .env
```

Optional variables include:

- `TWITCH_CLIENT_ID` and `TWITCH_CLIENT_SECRET` — optional Twitch enhancement provider.
- `TWITCH_SNAPSHOT_PATH` — optional authorized Twitch snapshot input.
- `STEAM_WEB_API_KEY` — optional Steam profile personalization; prepared opportunity signals do not require it.
- `STREAMSCHARTS_CLIENT_ID` and `STREAMSCHARTS_TOKEN` — reserved integration seam for a documented Streams Charts API only. GamePulse does not invent undocumented endpoints.
- `MISTRAL_API_KEY` — reserved for optional future integration.

`.env` is local-only and must never be committed.

## Creator directory

`data/manual/creators.csv` is the default creator source for the no-Twitch desktop path. Records include creator identity, platform, language, optional audience evidence, creator tier, tags, game history, observation date, source mode, and confidence.

Creator-fit scoring can use:

- selected-game history,
- genre/tag overlap,
- language when supplied,
- requested creator size,
- optional audience evidence,
- explicit provenance.

Missing audience data is excluded rather than fabricated.

## Optional public estimate refresh

Streamer and Developer Mode include an on-demand **Refresh public estimates** action for the selected game. It makes at most one TwitchTracker category-summary request and one SteamSpy app-detail request, then caches successful responses locally for 24 hours at `data/cache/external-provider-cache.json`.

- TwitchTracker values are source-labelled category audience/channel observations.
- SteamSpy ownership values are third-party estimates, not verified units sold.
- The Developer scenario uses the displayed equation: `owner range × USD price × realised-price fraction`; post-fee net is `gross × (1 − platform-fee rate)`. Default assumptions are 70% realised price and 30% platform fee, and are shown with every result.
- The competition index is peer-relative and only includes available factors. A single-category TwitchTracker response has no peer baseline, so its channel count is displayed but excluded from that index until a valid comparison baseline is available.

## Architecture

Developer intelligence queries are provided by gamepulse/developer_intelligence.py and the native
Settings / Integrations page keeps optional credentials out of the core workflow.

- `app.py` — native desktop launcher.
- `gamepulse/desktop_app.py` — PySide6 Overview/Player/Streamer/Developer workspaces.
- `gamepulse/providers/contracts.py` — source-neutral `GameSignal`, `CreatorSignal`, and `SignalSnapshot` contracts.
- `gamepulse/providers/composite.py` — provider routing for prepared Steam/public data, creator directory/imported snapshots, and optional Twitch.
- `gamepulse/providers/steam_signals.py` — no-credential prepared Steam/public opportunity signals.
- `gamepulse/providers/creator_directory.py` — manual/opt-in creator records.
- `gamepulse/providers/snapshot.py` — versioned generic snapshot normalization with legacy Twitch-snapshot compatibility.
- `gamepulse/providers/twitch.py` — optional Twitch adapter; no longer an application requirement.
- `gamepulse/streamer_opportunity.py` — source-neutral opportunity scoring with missing-component weight renormalization.
- `gamepulse/streamer_fit.py` — source-neutral developer-to-creator fit scoring.
- `gamepulse/desktop_theme.py` and `gamepulse/desktop_models.py` — native presentation layer.
- `data/` — prepared/raw datasets, demo/imported snapshots, creator directory, and SQLite prototype database.
- `tests/` — provider, scoring, catalogue, analysis, and desktop tests.

Legacy Streamlit UI modules remain under `gamepulse/ui/` only as migration/reference code. **`python app.py` does not start Streamlit or a web server.**

## Verify locally

```powershell
python -m unittest discover -s tests -q
python -m compileall -q app.py gamepulse gamepulse_data scripts tests
```

For a headless Linux environment that imports Qt widgets, set `QT_QPA_PLATFORM=offscreen` and install the required Qt runtime libraries (including EGL/OpenGL/XCB libraries).

The repository's desktop GitHub Actions workflow is manual-only; it does not automatically run on worker pushes.

## Data, privacy, and metric correctness

Large raw archives, processed CSVs, and the local SQLite database are tracked with Git LFS. Review `DATASET_SOURCES.md` before redistribution because source licenses and terms apply separately from the application code.

Prepared Steam/SteamSpy/Kaggle values, ownership ranges, and gross scenarios are public or derived signals, not verified sales or revenue. Twitch data, when configured, is explicitly identified as Twitch data. Demo and manually supplied creator records are labelled with their source mode and confidence.
