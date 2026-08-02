"""Visual tokens and responsive CSS for Developer Mode."""

from __future__ import annotations


DEVELOPER_COLORS = {
    "canvas": "#080D18",
    "surface": "#111A2B",
    "elevated_surface": "#172338",
    "border": "#273550",
    "primary": "#6EA8FF",
    "accent": "#C08BFF",
    "success": "#52D6A0",
    "warning": "#F2B84B",
    "text": "#F4F7FC",
    "muted": "#9EABC0",
}


def developer_css() -> str:
    return """
<style>
.gp-developer-shell {
  --gp-developer-surface: #111A2B;
  --gp-developer-elevated: #172338;
  --gp-developer-border: #273550;
  --gp-developer-primary: #6EA8FF;
  --gp-developer-accent: #C08BFF;
  --gp-developer-success: #52D6A0;
  --gp-developer-warning: #F2B84B;
  --gp-developer-text: #F4F7FC;
  --gp-developer-muted: #9EABC0;
  color: var(--gp-developer-text);
}
.gp-developer-hero {
  display: grid;
  grid-template-columns: minmax(180px, 28%) 1fr;
  gap: 24px;
  align-items: stretch;
  background: radial-gradient(circle at 90% 0%, rgba(110,168,255,.20), transparent 38%), linear-gradient(135deg, #111A2B 0%, #172338 100%);
  border: 1px solid var(--gp-developer-border);
  border-radius: 16px;
  overflow: hidden;
  margin: 0 0 22px;
}
.gp-developer-hero-art,
.gp-developer-art {
  width: 100%;
  height: 100%;
  min-height: 160px;
  object-fit: cover;
  background: #0C1322;
}
.gp-developer-placeholder {
  display: grid;
  place-items: center;
  min-height: 160px;
  color: var(--gp-developer-muted);
  background: #0C1322;
  font-size: .82rem;
}
.gp-developer-hero-copy { padding: 26px 26px 26px 0; }
.gp-developer-hero-title {
  margin: 0 0 8px;
  color: var(--gp-developer-text);
  font-size: clamp(1.45rem, 2.4vw, 2.1rem);
  line-height: 1.1;
}
.gp-developer-eyebrow,
.gp-developer-muted { color: var(--gp-developer-muted); font-size: .86rem; }
.gp-developer-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px; }
.gp-developer-badge {
  border: 1px solid var(--gp-developer-border);
  border-radius: 999px;
  color: var(--gp-developer-muted);
  padding: 5px 10px;
  font-size: .78rem;
}
.gp-developer-opportunity {
  display: grid;
  grid-template-columns: minmax(130px, 180px) 1fr;
  gap: 24px;
  background: linear-gradient(135deg, rgba(110,168,255,.16), rgba(192,139,255,.10));
  border: 1px solid rgba(110,168,255,.46);
  border-radius: 16px;
  padding: 22px;
  margin: 0 0 20px;
}
.gp-developer-score {
  display: grid;
  place-items: center;
  min-height: 130px;
  border: 1px solid rgba(110,168,255,.48);
  border-radius: 14px;
  background: rgba(8,13,24,.48);
  text-align: center;
}
.gp-developer-score-number { color: var(--gp-developer-primary); font-size: 2.7rem; font-weight: 800; line-height: 1; }
.gp-developer-score-label { color: var(--gp-developer-muted); font-size: .78rem; margin-top: 8px; }
.gp-developer-score-band { color: var(--gp-developer-accent); font-size: .85rem; font-weight: 700; margin-top: 5px; }
.gp-developer-opportunity-title { color: var(--gp-developer-text); font-size: 1.15rem; font-weight: 750; margin: 0 0 6px; }
.gp-developer-opportunity-copy { color: var(--gp-developer-muted); font-size: .86rem; line-height: 1.5; margin: 0; }
.gp-developer-signal-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin: 0 0 20px; }
.gp-developer-signal,
.gp-developer-card {
  background: var(--gp-developer-surface);
  border: 1px solid var(--gp-developer-border);
  border-radius: 14px;
  padding: 16px;
}
.gp-developer-signal-label { color: var(--gp-developer-muted); font-size: .78rem; }
.gp-developer-signal-value { color: var(--gp-developer-text); font-size: clamp(1.25rem, 2.2vw, 1.65rem); font-weight: 760; line-height: 1.2; margin: 8px 0 5px; overflow-wrap: anywhere; }
.gp-developer-signal-detail { color: var(--gp-developer-muted); font-size: .78rem; line-height: 1.4; }
.gp-developer-card-title { color: var(--gp-developer-text); font-size: 1rem; font-weight: 700; margin: 0 0 7px; }
.gp-developer-card-meta,
.gp-developer-card-copy { color: var(--gp-developer-muted); font-size: .82rem; line-height: 1.45; }
.gp-developer-card-copy ul,
.gp-developer-caution ul { margin: 8px 0 0; padding-left: 18px; }
.gp-developer-card-copy li,
.gp-developer-caution li { margin: 4px 0; }
.gp-developer-creator-card { padding: 18px; height: 100%; box-sizing: border-box; }
.gp-developer-creator-header { display: grid; grid-template-columns: 54px 1fr; gap: 12px; align-items: center; }
.gp-developer-creator-image,
.gp-developer-creator-placeholder { width: 54px; height: 54px; border-radius: 50%; object-fit: cover; background: #0C1322; }
.gp-developer-creator-placeholder { display: grid; place-items: center; color: var(--gp-developer-muted); font-size: .58rem; text-align: center; padding: 5px; box-sizing: border-box; }
.gp-developer-fit-score { color: var(--gp-developer-primary); font-weight: 760; }
.gp-developer-confidence { color: var(--gp-developer-text); font-size: .78rem; margin-top: 4px; }
.gp-developer-match-type {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
  margin: 16px 0 8px;
  padding: 10px 12px;
  border: 1px solid rgba(110,168,255,.32);
  border-radius: 10px;
  background: rgba(110,168,255,.08);
  color: var(--gp-developer-primary);
  font-size: .9rem;
}
.gp-developer-match-label { color: var(--gp-developer-muted); font-size: .72rem; text-transform: uppercase; letter-spacing: .06em; }
.gp-developer-top-reasons { margin-top: 12px; }
.gp-developer-top-reasons > strong { color: var(--gp-developer-text); font-size: .88rem; }
.gp-developer-top-reasons > .gp-developer-card-meta { margin-left: 8px; }
.gp-developer-details {
  margin-top: 14px;
  border-top: 1px solid var(--gp-developer-border);
  padding-top: 10px;
}
.gp-developer-details summary {
  color: var(--gp-developer-primary);
  cursor: pointer;
  font-size: .8rem;
  font-weight: 700;
  list-style-position: inside;
}
.gp-developer-details summary:hover,
.gp-developer-details summary:focus-visible { color: var(--gp-developer-text); }
.gp-developer-details-body { padding-top: 10px; }
.gp-developer-creator-metrics { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 5px 12px; margin: 13px 0; color: var(--gp-developer-muted); font-size: .78rem; }
.gp-developer-component-chips { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; }
.gp-developer-component-chip { border: 1px solid var(--gp-developer-border); border-radius: 999px; color: var(--gp-developer-muted); padding: 4px 8px; font-size: .72rem; }
.gp-developer-caution { color: #FFD78A; background: rgba(242,184,75,.10); border-left: 3px solid var(--gp-developer-warning); border-radius: 4px; padding: 8px 10px; margin: 10px 0; font-size: .78rem; }
.gp-developer-card a { color: var(--gp-developer-primary); }
.gp-developer-comparison { overflow-x: auto; padding: 15px; }
.gp-developer-comparison h3 { color: var(--gp-developer-text); margin: 0 0 12px; }
.gp-developer-comparison table { border-collapse: collapse; width: 100%; min-width: 620px; color: var(--gp-developer-muted); font-size: .78rem; }
.gp-developer-comparison th,
.gp-developer-comparison td { border-bottom: 1px solid var(--gp-developer-border); padding: 8px 10px; text-align: left; white-space: nowrap; }
.gp-developer-comparison th { color: var(--gp-developer-text); }
.gp-developer-comparison th:first-child { color: var(--gp-developer-muted); }
.gp-developer-component { margin-top: 10px; }
.gp-developer-component-row { display: flex; justify-content: space-between; gap: 12px; color: var(--gp-developer-muted); font-size: .78rem; }
.gp-developer-meter { height: 6px; background: rgba(158,171,192,.18); border-radius: 999px; margin-top: 6px; overflow: hidden; }
.gp-developer-meter-fill { height: 100%; background: linear-gradient(90deg, var(--gp-developer-primary), var(--gp-developer-accent)); border-radius: inherit; }
.gp-developer-reasons { margin: 12px 0 0; padding-left: 18px; color: var(--gp-developer-muted); font-size: .8rem; line-height: 1.5; }
.gp-developer-section-note { color: var(--gp-developer-muted); font-size: .86rem; line-height: 1.5; margin: -8px 0 16px; }
.gp-developer-limitations {
  background: rgba(242,184,75,.08);
  border: 1px solid rgba(242,184,75,.32);
  border-radius: 14px;
  color: var(--gp-developer-muted);
  padding: 16px 18px;
  line-height: 1.5;
}
.gp-developer-limitations strong { color: var(--gp-developer-text); }
.gp-developer-shell :focus-visible { outline: 2px solid var(--gp-developer-primary) !important; outline-offset: 2px; }
@media (max-width: 760px) {
  .gp-developer-hero { grid-template-columns: 1fr; gap: 0; }
  .gp-developer-hero-copy { padding: 20px; }
  .gp-developer-opportunity { grid-template-columns: 1fr; }
  .gp-developer-score { min-height: 110px; }
  .gp-developer-signal-grid { grid-template-columns: 1fr; }
  .gp-developer-creator-card { padding: 16px; }
  .gp-developer-match-type { align-items: flex-start; flex-direction: column; gap: 4px; }
}
@media (prefers-reduced-motion: reduce) {
  .gp-developer-shell *, .gp-developer-shell *::before, .gp-developer-shell *::after {
    transition-duration: .01ms !important; animation-duration: .01ms !important; animation-iteration-count: 1 !important; scroll-behavior: auto !important;
  }
}
</style>
"""


def inject_developer_theme(st) -> None:
    st.markdown(developer_css(), unsafe_allow_html=True)
