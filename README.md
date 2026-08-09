# GamePulse

GamePulse is evolving from the original local Streamlit prototype into a public
web application for three separate workflows: Player, Streamer and Developer.
The legacy prototype remains available while the Fusion Web implementation is
built on Next.js, FastAPI and Postgres.

## Runtime layout

- `src/` — Next.js App Router frontend for the Fusion Web app
- `api/` and `gamepulse/web_api/` — FastAPI boundary used by Vercel Python Functions
- `gamepulse/` — reusable GamePulse domain, provider and analytics logic
- `app.py` — legacy Streamlit prototype entrypoint
- `scripts/` — dataset preparation, migration and maintenance scripts
- `tests/` — Python and vertical-slice verification
- `data/` — local prepared/raw datasets and prototype database through Git LFS

## Fusion Web development

Install the lean production Python runtime with:

```powershell
python -m pip install -r requirements.txt
npm install
```

`requirements.txt` intentionally contains only packages required by the Vercel
Python runtime. This keeps the serverless function independent from the heavier
Streamlit/scientific prototype stack.

Start the unified local Fusion Web runtime with:

```powershell
npm run dev
```

This starts FastAPI on the local-only port `8000` and Next.js on the preferred
browser URL `http://127.0.0.1:3000`. If port `3000` is occupied, the launcher
selects the next available port in its bounded local range and prints the
actual browser URL. During development, Next.js forwards same-origin `/api/*`
requests to FastAPI; Vercel production routing is unchanged. Check the wiring
and selected port without starting either server with:

```powershell
python scripts\dev.py --check
Invoke-RestMethod http://127.0.0.1:<printed-port>/api/health
```

### Player analysis

The Player workflow accepts either a public Steam profile URL or an optional
Steam Web API key. The key is used only for the current request and is never
stored in Postgres, browser persistent storage, logs or committed files.

Without a key, GamePulse reads the public Steam profile page first and uses the
public games tab only when recent-game cards are not available. With a key, it
uses Steam's owned-games API. In both modes, recommendations exclude owned
games, use the catalog and cached signals available through `DATABASE_URL`,
and rank results by transparent personal-fit, review, activity and momentum
signals. The Player page can load additional bounded pages of recommendations
when more results are requested.

For local database-backed analysis, create an ignored `.env` file in the
repository root and add your own connection string without committing it:

```dotenv
DATABASE_URL=postgresql://user:password@host/database?sslmode=require
```

The development launcher loads this value for FastAPI. Verify the local proxy
before testing Player analysis:

```powershell
Invoke-RestMethod http://127.0.0.1:<printed-port>/api/health
```

If Player analysis reports a request failure, check the FastAPI terminal/log
first. A slow or unavailable Steam profile source is reported as a recoverable
provider error; the local `/api/player/analyze` request should not be allowed
to hang behind the Next.js proxy.

## Run the legacy Streamlit prototype

The dataset-inclusive repository stores the large raw archives, processed CSVs
and generated SQLite database through Git LFS. After cloning, make sure Git LFS
is installed and run `git lfs pull`. Install the prototype dependencies with:

```powershell
python -m pip install -r requirements-prototype.txt
python scripts\prepare_datasets.py --output-root data\processed\2026-08-01
python scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
streamlit run app.py
```

See [docs/prototype/setup.md](docs/prototype/setup.md) for the legacy setup,
credentials and source-label rules.

## Verify the checkout

For the full Python development/test environment:

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests -q
python -m compileall -q app.py api gamepulse scripts tests
```

The Fusion Web frontend is verified separately with:

```powershell
npm test
npm run build
```

## Catalog restore and intelligence refresh

The bounded provider seed is an explicit smoke-test path:

```powershell
python -m gamepulse.jobs.bootstrap_catalog --smoke-test
```

The production path reads the recovered Git-LFS SQLite catalog and batch-upserts
the full catalog, raw reviews, historical snapshots and multi-signal trend
scores into the database configured by `DATABASE_URL`:

```powershell
python -m gamepulse.jobs.import_full_database
```

When the target database has a constrained storage quota, omit raw review text
while retaining review summaries and derived trends:

```powershell
python -m gamepulse.jobs.import_full_database --skip-raw-reviews
```

If the catalog is already loaded and only derived trends need rebuilding, use
the compact trend refresh so the catalog tables are not rewritten:

```powershell
python -m gamepulse.jobs.refresh_trends --observed-at 2026-08-01T18:32:17Z
```

The import commits in batches, preserves source timestamps/provenance, and is
safe to rerun after an interrupted run. Missing provider signals remain
unavailable; they are not written as zero-valued observations.

## Data and privacy

Large raw archives, processed CSVs and the local SQLite database are tracked with
Git LFS for the prototype, but they are excluded from the Vercel deployment.
Production web reads come from Postgres snapshots instead of the local SQLite
asset.

Review [DATASET_SOURCES.md](DATASET_SOURCES.md) before redistributing the
repository: source licenses and terms apply to the data, not just the code.
Never commit `.env`, API keys, Steam cookies or Twitch secrets.

Visitor-provided Steam Web API keys are request/session-scoped credentials and
must not be stored in Postgres, browser persistent storage, logs or committed
configuration.

Ownership and purchase-related values from third-party sources are estimates or
public signals, not verified Steam sales.

## Hosting

Fusion Web targets Vercel with a Next.js frontend, FastAPI Python functions and
remote Postgres storage. The old Streamlit UI is retained only as a local
prototype/reference implementation and is not part of the Vercel runtime bundle.
