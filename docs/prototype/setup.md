# GamePulse desktop prototype setup

## 1. Prepare the local data

The transformed CSV files are under `data/processed/2026-08-01`. Raw archives remain under `data/raw/2026-07-30`.

If the SQLite prototype database is missing or needs rebuilding:

```powershell
python scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
```

## 2. Install the desktop runtime

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The UI runtime is PySide6. GamePulse does not need a Streamlit server or browser window on this branch.

## 3. Optional credentials

Copy `.env.example` to `.env` and fill only the credentials you have:

```powershell
Copy-Item .env.example .env
```

The app loads `.env` from the project root automatically. Never commit the real `.env`.

- Twitch credentials enable the live Helix provider.
- A Steam Web API key enables supported public-profile personalization flows in the reusable provider layer.
- Mistral is reserved for a future optional integration; local review analysis works without it.

The desktop prototype remains usable with prepared/demo data when credentials are absent.

## 4. Launch

```powershell
python app.py
```

You can also double-click `run_gamepulse.bat`. If `.venv\Scripts\python.exe` exists, the launcher uses it automatically.

## Desktop workspaces

- **Overview** — selected-game pulse, public market signals, and navigation into the three analysis modes.
- **Player** — catalogue search, seed-game selection, platform/price filters, best-match or hidden-gem recommendation ranking, and direct Steam Store opening.
- **Streamer** — Twitch category opportunity scoring using demand, reach, growth, and competition.
- **Developer** — opportunity score, owner/gross scenarios, review sentiment, comparable games, and a 30-day review-activity forecast.

## Source labels

- `Local prepared data`: transformed Steam snapshot.
- `Demo`: local Twitch fixture, not a current Twitch observation.
- `Live`: a successful provider response with its observation time.
- `Fallback`: local snapshot used after a live-provider failure.
- Ownership and gross scenarios are estimates; they are not verified Steam sales or revenue.

## Verify

```powershell
python -m unittest discover -s tests -q
python -m compileall -q app.py gamepulse scripts tests
```

For headless CI that imports Qt:

```powershell
$env:QT_QPA_PLATFORM="offscreen"
```
