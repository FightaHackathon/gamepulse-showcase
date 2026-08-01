# Dataset sources and redistribution notes

This repository includes the downloaded prototype data through Git LFS. These
links and notes are attribution records, not a replacement for each provider's
terms. Confirm the exact revision's license before making the repository public.

| Payload | Original source | Current review status |
| --- | --- | --- |
| Steam Games Dataset | [Fronkon Games on Kaggle](https://www.kaggle.com/datasets/fronkongames/steam-games-dataset) | The Kaggle revision and public mirrors show different license metadata across versions. Verify the exact downloaded revision before redistribution. |
| Steam game reviews | [Steam Game Reviews of 743 Games on Kaggle](https://www.kaggle.com/datasets/akashunikaggle/steam-game-reviews-of-743-games) | The current dataset page states CC BY-SA 4.0. Preserve attribution and share-alike terms. |
| SteamSpy catalogue | [Steam Games Dataset (SteamSpy API) on Kaggle](https://www.kaggle.com/datasets/muhammadaqeelkabir/steam-games-dataset-steamspy-api) | The current dataset page states CC0/Public Domain. Preserve the source URL and collection context. |

The raw download manifest under `data/raw/` records timestamps, archive hashes
and source URLs. The processed data report records the transformation date and
source paths. Twitch data is not included here as a live feed; the checked-in
fixture is explicitly labelled as a demonstration snapshot.

Do not add API keys, Steam cookies, Twitch credentials or any unapproved live API
cache to this repository.
