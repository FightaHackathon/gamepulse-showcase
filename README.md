# GamePulse prototype

GamePulse is a local Streamlit prototype that demonstrates one connected product
story for players, Twitch streamers and game developers. It combines prepared
Steam catalogue/review signals with clearly labelled demo or live-source
observations.

## What is included

- Player, Streamer and Developer modes in `app.py`
- Reusable domain logic under `gamepulse/`
- Dataset preparation and database-build scripts under `scripts/`
- Unit and vertical-slice tests under `tests/`
- A small, non-live Twitch demonstration fixture under `data/demo/`
- The prepared/raw Steam datasets and prototype database through Git LFS
- Product, data-source and prototype documentation under `docs/`

## Run locally

The dataset-inclusive repository stores the large raw archives, processed CSVs
and generated SQLite database through Git LFS. After cloning, make sure Git LFS
is installed and run `git lfs pull` before starting the app. To rebuild the
derived data from the raw archives:

```powershell
python -m pip install -r requirements.txt
python scripts\prepare_datasets.py --output-root data\processed\2026-08-01
python scripts\build_prototype_database.py --processed-dir data\processed\2026-08-01 --database data\prototype\gamepulse_prototype.sqlite3
streamlit run app.py
```

See [docs/prototype/setup.md](docs/prototype/setup.md) for the complete setup,
credentials and source-label rules. The app runs in Demo mode without Twitch,
Steam or Mistral credentials.

## Verify the checkout

```powershell
python -m unittest discover -s tests -q
python -m compileall -q app.py gamepulse scripts tests
```

## Data and privacy

Large raw archives, processed CSVs and the local SQLite database are tracked with
Git LFS. Review [DATASET_SOURCES.md](DATASET_SOURCES.md) before redistributing
the repository: source licenses and terms apply to the data, not just the code.
Never commit `.env`, API keys, Steam cookies or Twitch secrets.

The Twitch fixture is explicitly a demonstration snapshot, not a live observation.
Ownership, revenue and purchase-related values are estimates or public signals,
not verified Steam sales.

## Hosting

This checkout is designed for local Streamlit execution. Streamlit Community
Cloud is the natural next hosting target because it runs a Streamlit entrypoint
from GitHub. Vercel cannot run this Streamlit server unchanged: a Vercel version
would require a separate frontend/API architecture and remote database storage.

## Current prototype status

The local test suite covers the combined Player, Streamer and Developer showcase.
Live Twitch and Steam integrations remain optional and depend on credentials and
the relevant provider policies.
