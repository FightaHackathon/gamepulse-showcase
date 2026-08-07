# Dataset sources and redistribution notes

This repository includes downloaded/prepared prototype data through Git LFS plus small explicitly labelled demo/manual inputs. These notes are attribution and provenance records, not a replacement for each provider's terms. Confirm the exact revision's license before redistribution.

| Payload | Original source | Current review status |
| --- | --- | --- |
| Steam Games Dataset | [Fronkon Games on Kaggle](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) | The Kaggle revision and public mirrors show different license metadata across versions. Verify the exact downloaded revision before redistribution. |
| Steam game reviews | [Steam Game Reviews of 743 Games on Kaggle](https://www.kaggle.com/datasets/akashunikaggle/steam-game-reviews-of-743-games) | The current dataset page states CC BY-SA 4.0. Preserve attribution and share-alike terms. |
| SteamSpy catalogue | [Steam Games Dataset (SteamSpy API) on Kaggle](https://www.kaggle.com/datasets/muhammadaqeelkabir/steam-games-dataset-steamspy-api) | The current dataset page states CC0/Public Domain. Preserve the source URL and collection context. |

The raw download manifest under `data/raw/` records timestamps, archive hashes, and source URLs. The processed data report records transformation dates and source paths.

## Source-neutral desktop signals

The default Streamer/Developer opportunity path reads prepared Steam/public data from the local SQLite database. Each normalized game signal keeps an explicit metric identifier such as `steam_current_players`, `steam_peak_ccu`, or `steam_peak_ccu_prepared`.

**Steam player counts are not Twitch viewers.** The application must not relabel one metric family as another. Competition is `null`/unavailable when no legitimate competition source exists and must not be interpreted as zero channels or zero competition.

`data/demo/gamepulse_snapshot.json` is a versioned source-neutral demonstration snapshot. Values in that file are demo data and are labelled as such; they are not current live observations.

## Creator data

`data/manual/creators.csv` contains demonstration/manual creator records used to exercise the no-Twitch Developer Mode flow. Records carry source mode, observation date, and confidence. Demo records must not be presented as verified live platform observations.

Future creator records may come from creator-submitted/opt-in data or other authorized imports. Preserve platform, source, observation date, and confidence when adding them.

## Optional Twitch data

Twitch is an optional enhancement provider. The repository does not require Twitch credentials for its normal desktop path.

`data/demo/twitch_snapshot.json` is a legacy-compatible demonstration fixture, not a current live feed. `data/manual/twitch_snapshot.json` may be supplied locally only when the user has an authorized export or permitted source. Live Twitch data must retain its Twitch-specific metric identity and provenance.

Do not scrape Twitch webpages or represent Steam/public player counts as Twitch audience/competition measurements.

## Other optional providers

A Streams Charts configuration seam exists only for a future documented API integration. Do not implement guessed or undocumented endpoints. Any future provider must normalize into GamePulse's source-neutral contracts while preserving metric identity and provenance.

Do not add API keys, Steam cookies, Twitch credentials, Streams Charts tokens, or any unapproved live API cache to this repository.
