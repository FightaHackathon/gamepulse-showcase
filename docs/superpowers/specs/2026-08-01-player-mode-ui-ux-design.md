# GamePulse Player Mode UI/UX Design

**Status:** Approved design direction, ready for implementation planning  
**Audience:** Luna and the GamePulse prototype team  
**Scope:** Player Mode only; the design system may be extended to other modes later  
**Visual direction:** Polished gaming intelligence platform

## Objective

Transform Player Mode from a functional Streamlit form into a guided decision
workspace that helps a player understand three things quickly:

1. Which game is currently driving the recommendations.
2. How GamePulse personalized the result.
3. Why each recommended game is a good match.

The redesign must retain the existing local prototype architecture, public
Steam-profile option, manual fallback, source honesty, and no-Docker constraint.

## Product principles

- Make the next action obvious before showing detailed analytics.
- Keep recommendation evidence visible instead of hiding it behind tooltips.
- Use gaming character through artwork, color and motion, not excessive neon.
- Present ownership and popularity as estimates, never verified sales data.
- Keep Steam library data in session memory only unless a future explicit save
  feature is approved.
- The screen must remain fully usable without Steam credentials.

## Information architecture

### 1. Selected-game hero

The top of Player Mode uses the selected game's header artwork as a wide hero
with a dark navy gradient overlay. It contains:

- Game title and release year.
- Price or `Free` label.
- Review score.
- Windows, macOS and Linux support badges.
- A compact source badge, such as `Prepared Steam data`.
- The sentence: `Finding games for players who enjoy this title.`

The hero must not exceed approximately 280 px on desktop or 220 px on mobile.
Text must remain legible when artwork is missing; use a gradient placeholder in
that case.

### 2. Personalization workspace

Immediately below the hero, present two mutually understandable paths:

- **Steam profile:** Enter a public Steam profile URL or SteamID, then select
  `Analyze public library`.
- **Manual preferences:** Choose suggested tags and genres without requiring a
  Steam account.

The Steam path has five explicit states:

| State | User-facing treatment |
|---|---|
| Disconnected | Neutral explanation and Analyze button |
| Loading | Skeleton/progress indicator with `Reading public library…` |
| Connected | Game count, inferred preference chips and `Refresh` action |
| Private/unavailable | Amber message with privacy guidance and manual fallback |
| Rate limited | Amber message asking the player to retry later; retain manual mode |

Once loaded, the resolved SteamID, library and inferred preferences remain in
Streamlit session state. Changing price, platform or discovery mode must not
request the Steam API again. Only `Refresh` performs another request.

Manual preferences use searchable multi-select chips populated from catalogue
tags and genres. Display up to eight active chips, with a `+N more` treatment
for additional values. A `Clear preferences` action resets manual selections.

### 3. Filters and discovery mode

Place filters in one compact panel:

- Platform segmented control: `Any`, `Windows`, `macOS`, `Linux`.
- Price control: `Any price`, `Free only`, `Under $10`, `Under $30`, and
  `Custom`.
- Discovery tabs: `Best matches` and `Hidden gems`.
- `Reset filters` action visible whenever a non-default filter is active.

`Hidden gems` is a separate ranking mode rather than a small score bonus. It
must materially penalize high estimated ownership and may exclude the highest
popularity band. The interface must call ownership an estimate.

### 4. Recommendation results

Show eight recommendation cards by default. Each card contains:

- Header artwork or a designed placeholder.
- Title and release year.
- Normalized `Match` score from 0 to 100.
- Up to three reason chips.
- Price, review score and supported-platform icons.
- Estimated audience band when available.
- `View on Steam` external link using the AppID.

The first card receives slightly greater visual emphasis but uses the same data
structure as every other card. Cards must not repeat a case-insensitive game
name. Owned Steam games and the selected seed game remain excluded.

The match score must have a documented scale:

- 85–100: Excellent match
- 70–84: Strong match
- 55–69: Worth exploring
- Below 55: Do not display in the default list

Reasons should favor concrete evidence: shared tags, shared genres, selected
preferences, review quality, price fit and platform compatibility.

## Empty, loading and error states

- **Loading recommendations:** Show three skeleton cards; keep filters usable.
- **No results:** Explain which filters are restrictive and offer `Reset
  filters`.
- **Missing artwork:** Use the GamePulse gradient placeholder, not a broken
  image icon.
- **Steam unavailable:** Preserve the current recommendations and offer manual
  personalization.
- **Unexpected local error:** Show a short recovery message and keep the source
  game visible.

## Visual system

### Color tokens

| Token | Value | Usage |
|---|---|---|
| Canvas | `#080D18` | Application background |
| Surface | `#111A2B` | Primary cards and panels |
| Elevated surface | `#172338` | Hovered and emphasized cards |
| Border | `#273550` | Dividers and card outlines |
| Primary | `#4C8DFF` | Main actions and active filters |
| Personalization | `#8B7CFF` | Match and inferred-preference accents |
| Success | `#52D6A0` | Connected and strong-positive states |
| Warning | `#F2B84B` | Private/rate-limited states |
| Error | `#FF6B78` | Recoverable errors |
| Primary text | `#F4F7FC` | Headings and important values |
| Secondary text | `#9EABC0` | Explanations and metadata |

Use gradients sparingly: hero overlays and the Match score accent only. Avoid
large glowing borders or several saturated accents on the same card.

### Typography and spacing

- Use the existing application font unless Luna introduces one bundled,
  locally available family for the entire prototype.
- Page heading: 32–40 px desktop, 28–32 px mobile.
- Section heading: 22–26 px.
- Body: 15–17 px with at least 1.45 line height.
- Metadata: 13–14 px with sufficient contrast.
- Base spacing unit: 8 px.
- Panel padding: 24 px desktop, 16 px mobile.
- Card radius: 14 px; control radius: 10 px.

## Responsive behavior

- At 1024 px and above, personalization and filter summary may use two columns.
- Below 1024 px, sections stack without horizontal scrolling.
- Below 640 px, the Streamlit sidebar stays collapsed by default, hero metadata
  wraps, filter controls become full width, and cards use one column.
- Touch targets must be at least 44 px high.
- Long game titles wrap to two lines without overlapping the Match score.

## Accessibility

- Maintain WCAG AA contrast for body text and interactive controls.
- Do not communicate state through color alone; include text or icons.
- Every artwork image needs useful alt text containing the game name.
- Keyboard users must be able to operate profile input, chips, filters, tabs,
  Reset and recommendation links in logical order.
- Visible focus indicators use the primary blue token with a minimum 2 px ring.
- Loading states announce progress without repeatedly stealing focus.

## Interaction and motion

- Card hover: 2–3 px elevation and border-color transition within 160 ms.
- Filter changes: update results without page navigation.
- Steam analysis: explicit button action; never begin network requests while the
  player is still typing.
- Respect reduced-motion preferences; motion is decorative, not required to
  understand state.

## Acceptance criteria

1. A first-time user can identify the selected game, personalization choices
   and first recommendation without scrolling on a typical desktop viewport.
2. Steam library data is requested once per explicit Analyze or Refresh action,
   not on ordinary Streamlit reruns.
3. Manual personalization is discoverable and usable with no credentials.
4. Platform and price filters visibly change the results and active-filter
   summary.
5. Hidden Gems does not return the catalogue's highest-popularity tier in its
   first eight results.
6. All displayed match scores are integers between 0 and 100 and include at
   least one reason.
7. Recommendation names are unique case-insensitively.
8. Desktop and 390×844 mobile layouts have no clipping, overlap or horizontal
   page scrolling.
9. Browser console contains no application errors or relevant warnings.
10. Player Mode remains usable during missing-key, private-profile, rate-limit,
    empty-result and missing-artwork conditions.

## Out of scope

- Redesigning Home, Streamer or Developer Mode in this increment.
- User accounts, cloud profile storage or cross-device synchronization.
- Steam login, passwords, browser cookies or private-library access.
- Purchasing games or embedding the Steam checkout flow.
- Replacing Streamlit or adding a production frontend framework.

## Luna handoff summary

Design Player Mode as a polished dark-navy gaming intelligence workspace. Lead
with the selected game, offer explicit Steam/manual personalization paths, use
compact filters, separate Best Matches from Hidden Gems, and display visual game
cards with normalized 0–100 scores and concrete reasons. Preserve honest source
labels, session-only Steam data and complete no-credential fallbacks. Validate
the result on desktop and 390×844 mobile before extending the visual system to
other GamePulse modes.
