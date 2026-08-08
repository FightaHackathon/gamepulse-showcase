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
