# Authorized Twitch snapshot input

Place a JSON snapshot exported from a permitted source/API at
`data/manual/twitch_snapshot.json`, or set `TWITCH_SNAPSHOT_PATH` to another
file. The app prefers this file over the demo fixture and displays its
provenance.

Do not use a Twitch webpage scraper or redistribute Twitch API data. Until
Helix credentials are available, use the bundled demo fixture or an export you
are authorized to use. Import and validate a file with:

```powershell
python scripts/import_twitch_snapshot.py path\to\authorized_snapshot.json
```
