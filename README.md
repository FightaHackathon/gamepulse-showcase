# GamePulse Desktop Prototype

GamePulse is a **local native desktop application** for exploring game-market intelligence from three perspectives: players, Twitch streamers, and game developers. The desktop branch keeps the existing prepared Steam/Twitch datasets and analysis engines, but replaces the Streamlit runtime with a polished PySide6 interface.

## Desktop experience

The application now opens as one native window with four workspaces:

- **Overview** — a fast pulse check on the currently selected game and its public catalogue signals.
- **Player** — catalogue search plus explainable recommendations using similarity, price, platform support, review quality, and hidden-gem discovery.
- **Streamer** — Twitch category opportunity ranking using observed demand, channel competition, growth, and channel-size strategy.
- **Developer** — market positioning, comparable games, review themes, directional opportunity scoring, and a 30-day review-activity forecast.

The UI uses a dark game-analytics visual system with a persistent navigation rail, metric cards, responsive tables, local-mode status, and clear source/disclaimer labels.

## Run on Windows

The dataset-inclusive repository stores large prepared assets through Git LFS. After cloning this branch:

```powershell
git lfs pull
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

If the prepared SQLite database is already present, launch GamePulse with:

```powershell
python app.py
```

Or double-click `run_gamepulse.bat` after dependencies are installed.

If the database is missing, rebuild it first:

```powershell
python scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
python app.py
```

## Optional live credentials

Copy `.env.example` to `.env` and fill only the integrations you want to enable. The application can still run from local/demo data without credentials.

```powershell
Copy-Item .env.example .env
```

Supported variables:

- `TWITCH_CLIENT_ID`
- `TWITCH_CLIENT_SECRET`
- `STEAM_WEB_API_KEY`
- `MISTRAL_API_KEY` (reserved for optional future integration)

`.env` is local-only and must never be committed.

## Architecture

- `app.py` — native desktop launcher.
- `gamepulse/desktop_app.py` — PySide6 application shell and Overview/Player/Streamer/Developer workspaces.
- `gamepulse/desktop_theme.py` — desktop QSS visual system.
- `gamepulse/desktop_models.py` — desktop presentation/formatting helpers.
- `gamepulse/` — reusable recommendation, forecasting, review, provider, catalogue, and market-analysis logic.
- `data/` — prepared/raw datasets, local demo snapshots, and the generated SQLite prototype database.
- `tests/` — domain and desktop helper tests.

Legacy Streamlit UI modules remain in `gamepulse/ui/` for reference during migration, but **`python app.py` does not start Streamlit or a web server**.

## Verify

```powershell
python -m unittest discover -s tests -q
python -m compileall -q app.py gamepulse scripts tests
```

For headless CI environments that import Qt widgets, set:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
```

## Data and privacy

Large raw archives, processed CSVs, and the local SQLite database are tracked with Git LFS. Review `DATASET_SOURCES.md` before redistribution because source licenses and terms apply to the datasets separately from the application code.

The Twitch demo fixture is a demonstration snapshot, not a current live observation. Ownership, gross scenarios, and other market values derived from public signals are estimates and are not verified Steam sales or revenue.
