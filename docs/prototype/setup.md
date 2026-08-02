# GamePulse prototype setup

## Start from the prepared datasets

The transformed CSV files are under `data/processed/2026-08-01`. Raw archives remain under `data/raw/2026-07-30`.

Build or rebuild the disposable local database:

```powershell
python scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
```

If the `python` command is not the bundled runtime, use:

```powershell
C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
```

Install dependencies and start the local app:

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

The app is local-only and is available while the prototype computer is running.

## Optional credentials

Copy `.env.example` to `.env` and fill only the credentials you have. The prototype works in Demo mode without them.

The app loads `.env` from the project root automatically; never paste secrets
into source files or commit the real `.env`.

- Twitch credentials enable the live Helix provider; keep the secret private.
- A project-owned Steam Web API key enables the official full-library public-profile path. Without a key, the app first reads all visible rows from a public Steam games page and records their playtime, then falls back to recent profile cards if the games page is private or unavailable. Keep Game Details public; never provide a Steam password or cookie.
- Mistral is not wired into the current prototype; local review analysis remains available without it.

### Streamlit Community Cloud secrets

For the deployed app, open **Manage app → Settings → Secrets** and add the
following TOML entry (replace the placeholder locally; do not commit it):

```toml
STEAM_WEB_API_KEY = "your-steam-web-api-key"
```

The app reads Streamlit Cloud secrets as well as local `.env` values. After
saving the secret, restart the app and Player Mode will enable **Analyze public
library**. The profile must expose public Game Details; no Steam password or
cookie is requested.

Without a key, **Analyze public profile** reads the public
`/games/?tab=all` page for every game row and recorded hours it exposes. The UI
shows the complete returned profile table, total tracked hours, and most-played
games; preference inference uses the whole returned list. If that page is
private or unavailable, GamePulse falls back to the recent-game cards already
visible on the profile. It does not use cookies or login sessions, and Steam can
change page markup or rate-limit requests, so this remains a prototype fallback
rather than a replacement for the official API.

## Data labels

- `Local prepared data`: transformed Steam snapshot.
- `Demo`: local Twitch fixture, not a current Twitch observation.
- `Live`: a successful provider response with its observation time.
- `Cached`: a permitted recent local snapshot.
- Ownership and revenue ranges are estimates; they are not verified Steam sales.

## Prototype acceptance

The complete Player, Streamer, and Developer service story is covered by the
vertical-slice acceptance test. From the project root, run:

```powershell
python -m unittest tests\test_vertical_slice.py -v
python -m unittest discover -s tests -q
python scripts\prepare_datasets.py --verify --output-root data\processed\2026-08-01
```

The local demo remains usable without Steam, Twitch, or Mistral credentials.
