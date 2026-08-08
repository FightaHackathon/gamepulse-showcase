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
.gp-developer-component { margin-top: 10px; }
.gp-developer-component-row { display: flex; justify-content: space-between; gap: 12px; color: var(--gp-developer-muted); font-size: .78rem; }
.gp-developer-meter { height: 6px; background: rgba(158,171,192,.18); border-radius: 999px; margin-top: 6px; overflow: hidden; }
.gp-developer-meter-fill { height: 100%; background: linear-gradient(90deg, var(--gp-developer-primary), var(--gp-developer-accent)); border-radius: inherit; }
.gp-developer-reasons { margin: 12px 0 0; padding-left: 18px; color: var(--gp-developer-muted); font-size: .8rem; line-height: 1.5; }
.gp-developer-shell :focus-visible { outline: 2px solid var(--gp-developer-primary) !important; outline-offset: 2px; }
@media (max-width: 760px) {
  .gp-developer-hero { grid-template-columns: 1fr; gap: 0; }
  .gp-developer-hero-copy { padding: 20px; }
  .gp-developer-opportunity { grid-template-columns: 1fr; }
  .gp-developer-score { min-height: 110px; }
  .gp-developer-signal-grid { grid-template-columns: 1fr; }
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
