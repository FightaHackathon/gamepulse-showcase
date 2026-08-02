# GamePulse prototype demo script

Use the same selected game throughout the walkthrough. The default curated game is saved in `data/prototype/demo_config.json`.

## Fixed two-minute Developer Mode flow

Use the existing curated selection: Steam app id `10`, **Counter-Strike**.

1. **0:00-0:20 - Open the slice.** Start `streamlit run app.py`, keep Counter-Strike selected, and open Developer Mode.
2. **0:20-0:55 - Set campaign context.** Choose **Awareness**, target language **en**, preferred creator tier **mid-size**, keep similar-game specialists **included**, and turn on **Require selected-game history**. Leave budget positioning as context (for example, **Flexible**).
3. **0:55-1:35 - Read the output.** Show the separate Campaign summary fields, then the public-signal opportunity score, market evidence, comparable games, review themes, and 30-day review-activity baseline. Scroll to the recommendation cards and point out their evidence, source, confidence, and limitations.
4. **1:35-2:00 - Close with the decision.** Explain that this is a directional shortlist for validating creator fit; it does not contact creators or estimate sponsorship prices.

Expected output is a Counter-Strike campaign summary followed by the existing public-signal and creator-fit sections. With the local demo fixture, the selected-game-history and mid-size/en filters should surface the matching Counter-Strike creator evidence when those observations are available.

Limitations: the demo uses prepared public-signal data rather than guaranteed live observations; scores are directional, not verified sales, reach, or conversion forecasts; budget positioning is context only; and similar-game specialists depend on available catalog/category overlap.

1. Start `streamlit run app.py` and open the local URL.
2. On Home, show the selected game and search for another catalogue entry to demonstrate that the story is data-driven.
3. In Player Mode, enable “Prefer hidden gems,” adjust the price limit, and open several recommendation reasons.
4. Use the recommendation page control to move through the ranked catalogue (up to 400 results), then click **View details** on a game. Show its tags, genres, platforms, review aggregates, themes, and newest review catalogue entries.
5. Paste a public Steam profile URL if available; expand the profile game table to show every returned owned game, recorded hours, and most-played signals. Explain that profile data is session-only by default.
6. In Streamer Mode, compare emerging and mid-size channel settings. Point out demand, channel count, viewer-to-channel opportunity, and the `Demo`/`Live` source label.
7. In Developer Mode, show the public-signal opportunity score, estimated owners, the source-labelled player metric, the estimated gross range, review themes, comparable-game overlap scores, and the 30-day review-activity baseline.
8. Show the streamer-fit shortlist and its evidence/fit bands. Explain that it is a recommendation list, not automated outreach.
9. Explain the limitation: exact competitor sales are private Steamworks data; public charts and ownership estimates are clearly separated from derived scenarios.

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
