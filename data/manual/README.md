# Manual and opt-in signal inputs

GamePulse's default desktop flow does not require Twitch. This directory holds small manual/opt-in inputs that keep provenance explicit.

## Creator directory

`creators.csv` is the default creator source for Developer Mode when `CREATOR_PROVIDER=auto` or `directory`. Keep the CSV header and provide source/observation metadata for every record. Demo rows are intentionally labelled `competition_demo`/`demo`; replace them with creator-submitted or otherwise authorized records when available.

Do not fabricate audience sizes. Leave optional audience fields blank when unknown so the fit scorer excludes them.

## Optional Twitch snapshot

An authorized Twitch JSON export may be placed at `data/manual/twitch_snapshot.json`, or `TWITCH_SNAPSHOT_PATH` may point elsewhere. Twitch remains an optional enhancement provider and is not needed for the Steam/public desktop path.

Do not use a Twitch webpage scraper or redistribute Twitch API data without permission. When using an authorized legacy Twitch snapshot, import and validate it with:

```powershell
python scripts/import_twitch_snapshot.py path\to\authorized_snapshot.json
```

All imported data must preserve metric identity and provenance. Steam player activity must never be represented as Twitch viewers or live-channel competition.
