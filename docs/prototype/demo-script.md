# GamePulse prototype demo script

Use the same selected game throughout the walkthrough. The default curated game is saved in `data/prototype/demo_config.json`.

1. Start `streamlit run app.py` and open the local URL.
2. On Home, show the selected game and search for another catalogue entry to demonstrate that the story is data-driven.
3. In Player Mode, enable “Prefer hidden gems,” adjust the price limit, and open several recommendation reasons.
4. Paste a public Steam profile URL if available; otherwise use the manual filters. Explain that profile data is session-only by default.
5. In Streamer Mode, compare emerging and mid-size channel settings. Point out demand, channel count, viewer-to-channel opportunity, and the `Demo`/`Live` source label.
6. In Developer Mode, show the public-signal opportunity score, estimated owners, the source-labelled player metric, the estimated gross range, review themes, comparable-game overlap scores, and the 30-day review-activity baseline.
7. Show the streamer-fit shortlist and its evidence/fit bands. Explain that it is a recommendation list, not automated outreach.
8. Explain the limitation: exact competitor sales are private Steamworks data; public charts and ownership estimates are clearly separated from derived scenarios.

## Offline fallback check

Temporarily leave Twitch and Steam credentials blank. Restart the app and confirm Player manual mode plus Streamer Demo mode still render. This is an intentional prototype acceptance check.

## Acceptance checklist

Run these checks from the project root before a team demo:

```powershell
python -m unittest discover -s tests -q
python scripts\prepare_datasets.py --verify --output-root data\processed\2026-08-01
streamlit run app.py
```

The vertical-slice test uses the local prepared database and Twitch fixture, so this checklist remains valid while credentials are unavailable.
