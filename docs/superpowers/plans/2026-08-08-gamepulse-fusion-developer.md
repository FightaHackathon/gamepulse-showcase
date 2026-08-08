# GamePulse Fusion Developer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Developer Mode as an evidence-first market intelligence workflow that progresses from market trends to opportunity exploration, product direction, and an explicitly generated mini game brief.

**Architecture:** Adapt useful formulas/data structures from `codex/twitchtracker-steamspy-estimates/gamepulse/developer_intelligence.py` and existing `market_analysis.py`, `forecasting.py`, and review analysis, but replace SQLite-bound queries with Postgres repositories. Evidence generation and concept generation are separate services. The concept layer optionally uses Mistral if a server-owned key exists; otherwise it produces a deterministic template-based brief from the same evidence package.

**Tech Stack:** Python analytics services, SQLAlchemy/Postgres, FastAPI/Pydantic, optional Mistral server integration, Next.js/React, Recharts, pytest, Vitest, Playwright.

## Global Constraints

- Depends on O1/O2 frozen shared contracts.
- Flow is exactly: Market dashboard -> Opportunity -> Explore opportunity -> Suggest direction -> Generate mini brief.
- Evidence and generated ideas must be visually/semantically separated.
- Never label SteamSpy ownership as exact sales.
- Do not provide sales guarantees, ROI guarantees or sponsorship pricing predictions.
- SteamDB is manual validation only unless explicit permission for automated access is obtained.
- Mini brief contains working concept/name, genre/subgenre, core loop, 3-5 mechanics, target players, solo/multiplayer structure, suggested Steam price band, comparable games, opportunity score, saturation/risk summary and evidence-backed rationale.
- Full production roadmap/team plan is out of scope.

---

### Task 1: Port Developer intelligence into repository-backed pure services

**Files:**
- Create: `gamepulse/services/developer_intelligence.py`
- Create: `gamepulse/services/developer_features.py`
- Create: `gamepulse/web_api/schemas/developer.py`
- Test: `tests/test_developer_intelligence_web.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class OpportunityFactors:
    demand: float
    momentum: float
    competition: float
    saturation: float
    streaming_fit: float | None
    review_quality: float | None

@dataclass(frozen=True)
class MarketOpportunity:
    dimension: str
    value: str
    score: int
    factors: OpportunityFactors
    matched_games: int
    comparable_app_ids: tuple[int, ...]
    reasons: tuple[str, ...]
    cautions: tuple[str, ...]
    confidence: float
```

- [ ] Write fixtures proving high demand + high momentum + lower competition/saturation can outrank a saturated segment with equal raw demand.
- [ ] Preserve the useful existing 0-100 scoring shape but make each factor separately inspectable.
- [ ] Add streaming fit only when mapped streaming evidence exists; missing streaming data lowers confidence rather than inventing a zero.
- [ ] Include genre/tag dimensions at minimum; mechanics may initially be represented by Steam tags.
- [ ] Query through Postgres repositories only.
- [ ] Run `python -m pytest tests/test_developer_intelligence_web.py -q`; expect PASS.
- [ ] Commit with `git commit -m "feat: add repository-backed Developer intelligence"`.

### Task 2: Build market summary and opportunity APIs

**Files:**
- Create: `gamepulse/web_api/routes/developer.py`
- Modify: `gamepulse/web_api/app.py`
- Test: `tests/test_developer_api.py`

**Interfaces:**
- `GET /developer/market` returns concise trend groups: rising genres, rising tags/mechanics, Steam player momentum, streaming demand, release saturation, review sentiment, ownership estimate ranges and price bands.
- `GET /developer/opportunities?dimension=genre|tag&limit=20` returns ranked `MarketOpportunity` records.
- `GET /developer/opportunities/{dimension}/{value}` returns evidence package + comparable games + chart-ready histories.

- [ ] Write API tests for populated and sparse datasets.
- [ ] Ensure each ownership value has explicit `estimate: true` and lower/upper bounds.
- [ ] Ensure evidence response carries source/freshness/confidence for each external-derived metric.
- [ ] Implement routes with no external network calls.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: expose Developer market opportunity APIs"`.

### Task 3: Add product-direction service separate from evidence

**Files:**
- Create: `gamepulse/services/developer_direction.py`
- Test: `tests/test_developer_direction.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class ProductDirection:
    headline: str
    genre: str
    subgenre: str | None
    recommended_traits: tuple[str, ...]
    avoid_traits: tuple[str, ...]
    rationale: tuple[str, ...]
    evidence_refs: tuple[str, ...]
```

- [ ] Write a deterministic fixture where a co-op + automation + survival opportunity produces those traits without inventing unsupported market numbers.
- [ ] Derive direction only from normalized opportunity dimensions, comparable games and observed evidence.
- [ ] Generated text must say `recommendation` or `direction`, never `market fact`.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: derive Developer product directions"`.

### Task 4: Add deterministic mini-brief generator

**Files:**
- Create: `gamepulse/services/concept_generator.py`
- Test: `tests/test_concept_generator.py`

**Interfaces:**

```python
@dataclass(frozen=True)
class MiniGameBrief:
    working_title: str
    genre: str
    subgenre: str | None
    core_loop: str
    mechanics: tuple[str, ...]
    target_players: str
    structure: str
    suggested_price_band_usd: tuple[float, float] | None
    comparable_app_ids: tuple[int, ...]
    opportunity_score: int
    risks: tuple[str, ...]
    rationale: tuple[str, ...]
    generation_mode: Literal["deterministic", "llm"]
```

- [ ] Write a no-Mistral test proving a complete brief is produced with 3-5 mechanics and `generation_mode="deterministic"`.
- [ ] Calculate suggested price band from comparable-game price distribution when at least three valid prices exist; otherwise return `None` rather than fabricate a price.
- [ ] Use deterministic title pattern from selected dimension/traits; do not claim title uniqueness.
- [ ] Risks must include evidence limitations when confidence is low or saturation is high.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: add deterministic Developer mini briefs"`.

### Task 5: Add optional Mistral enhancement behind server-owned key

**Files:**
- Create: `gamepulse/providers/mistral_concepts.py`
- Modify: `gamepulse/services/concept_generator.py`
- Test: `tests/test_mistral_concept_fallback.py`

**Interfaces:**
- `MistralConceptEnhancer.enhance(evidence, deterministic_brief) -> MiniGameBrief`.

- [ ] Test that no configured key performs zero network calls and returns deterministic output.
- [ ] Test provider timeout/invalid response falls back to deterministic brief with no route failure.
- [ ] Prompt must include only normalized market evidence and comparable-game metadata, not user secrets or raw provider payloads.
- [ ] Validate LLM output against strict Pydantic schema; reject extra/unexpected fields.
- [ ] Mark successful enhanced output `generation_mode="llm"` while retaining the same evidence references.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: add optional Developer concept enhancement"`.

### Task 6: Expose direction and mini-brief APIs

**Files:**
- Modify: `gamepulse/web_api/routes/developer.py`
- Test: `tests/test_developer_concept_api.py`

**Interfaces:**
- `POST /developer/direction` accepts an opportunity identifier and returns `ProductDirection`.
- `POST /developer/concept` accepts an opportunity identifier plus approved direction and returns `MiniGameBrief`.

- [ ] Write test proving concept generation cannot be invoked with an arbitrary unsupported market claim; the opportunity identifier must resolve to current stored evidence.
- [ ] Return evidence references and generation mode in responses.
- [ ] Add safe 404/422 handling for stale/deleted opportunity identifiers.
- [ ] Run tests; expect PASS.
- [ ] Commit with `git commit -m "feat: expose Developer direction and concept APIs"`.

### Task 7: Build clean Developer market page

**Files:**
- Create: `src/app/developer/page.tsx`
- Create: `src/features/developer/market-summary.tsx`
- Create: `src/features/developer/opportunity-card.tsx`
- Create: `src/features/developer/developer-api.ts`
- Test: `src/features/developer/market-summary.test.tsx`

- [ ] Write test that the initial page contains concise market sections and opportunity cards but no concept generator form before an opportunity is selected.
- [ ] Render rising genres/tags, player momentum, streaming demand, release saturation and review sentiment using compact cards and a small number of charts.
- [ ] Label ownership as `Estimated ownership` and show ranges.
- [ ] Use source/freshness/confidence components from O2.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: build Developer market intelligence page"`.

### Task 8: Build opportunity exploration and progressive generation UI

**Files:**
- Create: `src/app/developer/opportunities/[dimension]/[value]/page.tsx`
- Create: `src/features/developer/opportunity-evidence.tsx`
- Create: `src/features/developer/direction-panel.tsx`
- Create: `src/features/developer/concept-brief.tsx`
- Test: `src/features/developer/opportunity-evidence.test.tsx`
- Test: `src/features/developer/concept-brief.test.tsx`

- [ ] Render evidence first: factors, comparable games, charts, reasons, cautions and confidence.
- [ ] Add explicit `Suggest direction` action after evidence.
- [ ] Add `Generate mini game brief` only after direction is available.
- [ ] Visually label generated content with `Generated recommendation` and show deterministic/AI mode without presenting it as measured data.
- [ ] Mini brief renders only approved fields; no roadmap/team-size/ROI sections.
- [ ] Comparable game cards route internally to GamePulse details.
- [ ] Run tests/build; expect PASS.
- [ ] Commit with `git commit -m "feat: add progressive Developer opportunity workflow"`.

### Task 9: Add Developer E2E and estimate-safety regression

**Files:**
- Create: `e2e/developer.spec.ts`
- Create: `tests/test_developer_estimate_labels.py`

- [ ] Test Landing -> Developer -> select opportunity -> evidence -> direction -> mini brief.
- [ ] Test with Mistral disabled; mini brief must still complete.
- [ ] Assert rendered/backend schemas never use ownership estimate as `sales` or `revenue guaranteed`.
- [ ] Assert generation mode and evidence references remain visible.
- [ ] Run:
  - `python -m pytest tests/test_developer_intelligence_web.py tests/test_developer_api.py tests/test_developer_direction.py tests/test_concept_generator.py tests/test_mistral_concept_fallback.py tests/test_developer_concept_api.py tests/test_developer_estimate_labels.py -q`
  - `npm test -- src/features/developer`
  - `npx playwright test e2e/developer.spec.ts`
  - `npm run build`
- [ ] Commit with `git commit -m "test: verify Developer evidence-to-concept flow"`.

## Developer Acceptance Gate

Parent verifies:

1. Market evidence loads without Mistral.
2. Opportunities expose demand/momentum/competition/saturation plus confidence.
3. Ownership estimates are ranges and never sales claims.
4. Direction and concept are downstream of stored evidence, not free-form unsupported prompts.
5. Deterministic brief works with no AI key.
6. Optional Mistral failure cannot break concept generation.
7. Generated content is visually separated from evidence.
8. Comparable games route internally.
9. Python/frontend/E2E tests pass.
