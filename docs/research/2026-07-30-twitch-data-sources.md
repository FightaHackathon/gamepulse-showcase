# Twitch data sources for the GamePulse prototype

Verified 2026-07-30. “Trending” is not a single Twitch dataset: current rank, recent growth, and long-term performance require different sources.

## Recommendation

Use this stack for the prototype:

1. **IGDB PopScore** for a daily game-trend signal: its first-party `Twitch Hours Watched` primitive measures hours watched per Twitch game category over the previous 24 hours and is updated every 24 hours.
2. **Twitch Helix API** for current top categories and live-streamer observations. Take small, scheduled snapshots; compute rank, viewer-share, and growth from the snapshots you are permitted to retain.
3. **Twitch EventSub** for category/title changes on a deliberately small tracked-streamer cohort.
4. **IGDB game metadata** to convert category IDs into genres, themes, platforms, game modes, companies, and releases. Twitch `Get Games` returns `igdb_id`, providing the join key when available.
5. If a demo needs history immediately and budget/licensing allow it, buy access to **Streams Charts API** instead of scraping public statistics sites.

Do not base the prototype on a random Kaggle/Hugging Face CSV. Such files can help test an offline UI, but they do not establish current trends unless collection date, source method, coverage, and reuse license are all explicit.

## Source comparison

| Need | Best source | Data and limitations | Auth / access | Bulk download |
|---|---|---|---|---|
| Trending games now | Twitch Helix `GET /helix/games/top` | Twitch categories ordered by current viewers; returns `id`, `name`, `box_art_url`, `igdb_id`, but **not** viewer totals. Up to 100 per page. | App or user OAuth token plus Client ID | No documented public dump |
| Trending games over 24h | IGDB `popularity_primitives` | First-party `Twitch Hours Watched` per category over the previous 24h; PopScore updates daily. Query the current `popularity_types` table rather than hard-coding an ID. | Twitch application credentials / client-credentials token | Daily CSV dumps exist only for IGDB Data Partners |
| Live / top streamers | Twitch Helix `GET /helix/streams` | Live streams sorted by `viewer_count`; fields include user and game IDs/names, title, tags, viewer count, start time, language, thumbnail, and maturity. Dynamic paging can produce duplicates or omissions. | App or user OAuth token | No documented public dump |
| Streamer profile | Helix `GET /helix/users`, `GET /helix/channels` | Display/login name, broadcaster type, description and images; current/last category, title, language, tags, classification labels. The user `view_count` field is deprecated and invalid. | App or user OAuth token | No |
| Follower count | Helix `GET /helix/channels/followers` | Public requests can receive `total`; individual follower records require `moderator:read:followers` and broadcaster/moderator authorization. Snapshot totals to measure change only if permitted. | OAuth; scoped user token for follower identities | No |
| Streamer’s game/category history | Own Helix snapshots + EventSub `channel.update` | Twitch provides no general public endpoint that returns a broadcaster’s complete historical category timeline. `channel.update` reports future title/category/language/labels changes after subscription. | EventSub authorization depends on transport; `channel.update` itself has no user scope requirement, but subscriptions have cost limits | No |
| Recent past broadcasts | Helix `GET /helix/videos?user_id=…&type=archive` | Video ID, stream ID, title, timestamps, view count, duration and language. It has no game/category field, so it cannot reconstruct category changes. Past broadcasts exist only if storage was enabled and normally expire after 7 days (ordinary), 14 (Affiliate), or 60 (Partner/Prime/Turbo). | App or user OAuth token | No |
| Historical clips by game/streamer | Helix `GET /helix/clips` | Includes broadcaster, game ID, views and creation time; lists are view-ranked and capped at approximately 1,000 results across pagination, so this is a popularity-biased sample, not stream history. | App or user OAuth token | No |
| Owned-game analytics | Twitch Game Developer Analytics / `GET /helix/analytics/games` | Strongest official history: daily CSV for the past 365 days, including hours watched, average/peak viewers, unique broadcasters, broadcast hours, chat and clip metrics. Only for games owned/claimed by the authenticated organization and only when broadcast at least five hours in the report period. | User token with `analytics:read:games` | Yes, temporary CSV URL |
| Immediate third-party history | Streams Charts API | Vendor states Twitch coverage since June 2019, one-minute collection, and a 2+ average-viewer threshold; supports channel/stream stats and filters for game, language, partnership, growth and games streamed. Paid/credit API and exports; its terms restrict publication/redistribution without written agreement. | Vendor account/token and credits | API; some paid CSV/JSON exports |
| Free historical exploration | SullyGnome website | Vendor says it polls Twitch every five minutes, aggregates hourly/daily, and has data since August 2015. Since 2022 its stated coverage is partners, Affiliates with 3+ viewers, and other channels with 10+ viewers, so low-viewer channels are incomplete. No stable licensed bulk/API offering was verified. | Website | Not verified; do not scrape |

## What the prototype can calculate

### Game trend table

At each observation time, record:

- Twitch category ID and IGDB ID
- current Twitch rank
- total live viewers (sum of `viewer_count` for collected live streams in that category)
- live channel count
- viewer concentration: top 1 / top 5 streamer share
- IGDB 24-hour Twitch Hours Watched
- change versus the previous comparable observation

Because `/streams` is a changing, viewer-ranked list, category totals based on a partial crawl must be labeled **observed totals**, not platform totals. IGDB’s 24-hour metric is preferable for the headline daily trend.

### Streamer trend and “type”

For each observed live streamer, retain or derive:

- current viewers, rank, title, language, tags, start time and category
- follower total, profile and Affiliate/Partner status
- category mix over the observation window
- IGDB genre/theme/game-mode mix for game categories
- average and peak observed viewers, hours observed live, category-switch count
- growth score based on viewer/rank/follower changes

Label streamer “type” as a computed classification, for example `FPS specialist`, `variety`, `Just Chatting/IRL`, or `indie-focused`, and expose its evidence (share of observed hours/categories). Do not imply Twitch supplied that label.

## Authentication and rate limits

Helix uses OAuth 2.0. Public endpoints above generally accept an app access token created via client credentials; private/user-authorized data requires a user token and named scopes. Twitch uses token-bucket rate limiting: most endpoints cost one point by default, buckets replenish over one minute, and responses report `Ratelimit-Limit`, `Ratelimit-Remaining`, and `Ratelimit-Reset`. Twitch’s documentation shows an 800-point example but applications should obey the returned headers rather than assume a fixed value.

IGDB also uses Twitch application credentials. Its documented limit is four requests per second with up to eight concurrent open requests; response limits default to 10 and max at 500. It permits local caching and is free for non-commercial use under the Twitch Developer Services Agreement; commercial integration requires the applicable IGDB partnership/attribution terms. IGDB daily CSV dumps are restricted to Data Partners.

## Retention, licensing, and data-quality cautions

- The current Twitch Developer Services Agreement treats API data/metadata as Program Materials, prohibits re-syndication/redistribution, requires honoring deletions and user controls, and generally limits unapproved caching to 24 hours. It also identifies research over time and firehose-scale collection as activities Twitch may authorize only through a separate agreement/approval process. Confirm the permitted retention design with Twitch before turning prototype snapshots into a long-lived/public dataset.
- Prefer aggregate trend features over publishing raw streamer records. Never collect private follower identities, subscriber data, email, or chat logs for this prototype.
- Do not scrape Twitch pages, SullyGnome, TwitchTracker, or Streams Charts. Use a documented API/export and its license.
- Static marketplace/community datasets are snapshots, not current feeds. Accept one only if it has a precise collection window, reproducible Twitch/API provenance, coverage rules, schema, and an explicit license compatible with the project. The currently discoverable Hugging Face `mrfakename/twitch_streamers` listing claims recent games/follower counts, but its search listing alone does not establish collection date, Twitch-policy compliance, or a suitable reuse license; it is therefore **not recommended as a production source**.
- VOD `view_count` is not equivalent to live concurrent viewers; clip data is heavily selection-biased; and sampled live viewers will miss short peaks.

## Minimal collection plan

1. Register one confidential Twitch application and keep the client secret server-side.
2. Once daily, query IGDB `popularity_types`, identify `Twitch Hours Watched`, then fetch the top relevant `popularity_primitives` and associated games.
3. Every 10–15 minutes during a short, approved prototype window, fetch the first 100 top games and a bounded number of `/streams` pages; deduplicate by stream ID within each snapshot.
4. Track only the top 100–500 observed streamers. Enrich IDs in batches through `/users` and `/channels`; fetch public follower totals sparingly.
5. Aggregate into daily game and streamer features. Keep raw responses ephemeral, follow the 24-hour cache rule, and seek Twitch approval before retaining historical person-level records.
6. Use a frozen, date-stamped aggregate export for the prototype demo so the UI remains repeatable.

## Primary sources

- Twitch, [API Reference: Get Top Games, Get Games, Get Streams, Users, Channels, Followers, Clips, Videos, and Game Analytics](https://dev.twitch.tv/docs/api/reference)
- Twitch, [API concepts: pagination and rate limits](https://dev.twitch.tv/docs/api/guide)
- Twitch, [Authentication](https://dev.twitch.tv/docs/authentication)
- Twitch, [EventSub subscription types](https://dev.twitch.tv/docs/eventsub/eventsub-subscription-types/)
- Twitch, [Insights & Analytics](https://dev.twitch.tv/docs/insights/)
- Twitch Help, [On-Demand Content on Twitch](https://help.twitch.tv/s/article/video-on-demand)
- Twitch, [Developer Services Agreement](https://legal.twitch.com/en/legal/developer-agreement/)
- IGDB, [API documentation: authentication, PopScore, rate limits, data dumps, and FAQ](https://api-docs.igdb.com/)

## Secondary vendor sources

- Streams Charts, [Data API overview and historical coverage](https://streamscharts.com/api)
- Streams Charts, [Terms of Use](https://streamscharts.com/terms)
- SullyGnome, [collection method, coverage, and history](https://sullygnome.com/about)
- Hugging Face, [`mrfakename/twitch_streamers` dataset listing](https://huggingface.co/datasets/mrfakename/twitch_streamers)
