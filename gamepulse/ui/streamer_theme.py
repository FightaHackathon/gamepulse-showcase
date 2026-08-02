"""Visual tokens and responsive CSS for Streamer Mode."""

from __future__ import annotations


STREAMER_COLORS = {
    "canvas": "#080D18",
    "surface": "#111A2B",
    "elevated_surface": "#172338",
    "border": "#273550",
    "primary": "#4C8DFF",
    "accent": "#B68CFF",
    "success": "#52D6A0",
    "warning": "#F2B84B",
    "text": "#F4F7FC",
    "muted": "#9EABC0",
}


def streamer_css() -> str:
    return """
<style>
.gp-streamer-shell {
  --gp-streamer-canvas: #080D18;
  --gp-streamer-surface: #111A2B;
  --gp-streamer-elevated: #172338;
  --gp-streamer-border: #273550;
  --gp-streamer-primary: #4C8DFF;
  --gp-streamer-accent: #B68CFF;
  --gp-streamer-success: #52D6A0;
  --gp-streamer-warning: #F2B84B;
  --gp-streamer-text: #F4F7FC;
  --gp-streamer-muted: #9EABC0;
  color: var(--gp-streamer-text);
}
.gp-streamer-hero {
  display: grid;
  grid-template-columns: minmax(180px, 28%) 1fr;
  gap: 24px;
  align-items: stretch;
  background: linear-gradient(135deg, #111A2B 0%, #172338 100%);
  border: 1px solid var(--gp-streamer-border);
  border-radius: 16px;
  overflow: hidden;
  margin: 0 0 22px;
}
.gp-streamer-hero-art,
.gp-streamer-art {
  width: 100%;
  height: 100%;
  min-height: 150px;
  object-fit: cover;
  background: #0C1322;
}
.gp-streamer-placeholder {
  display: grid;
  place-items: center;
  min-height: 150px;
  color: var(--gp-streamer-muted);
  background: #0C1322;
  font-size: 0.82rem;
}
.gp-streamer-hero-copy { padding: 26px 26px 26px 0; }
.gp-streamer-hero-title {
  margin: 0 0 8px;
  color: var(--gp-streamer-text);
  font-size: clamp(1.45rem, 2.4vw, 2.1rem);
  line-height: 1.1;
}
.gp-streamer-eyebrow,
.gp-streamer-muted { color: var(--gp-streamer-muted); font-size: 0.86rem; }
.gp-streamer-badges { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px; }
.gp-streamer-badge {
  border: 1px solid var(--gp-streamer-border);
  border-radius: 999px;
  color: var(--gp-streamer-muted);
  padding: 5px 10px;
  font-size: 0.78rem;
}
.gp-streamer-card {
  background: var(--gp-streamer-surface);
  border: 1px solid var(--gp-streamer-border);
  border-radius: 14px;
  overflow: hidden;
  padding: 0 0 14px;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}
.gp-streamer-card:hover {
  transform: translateY(-3px);
  border-color: var(--gp-streamer-primary);
  background: var(--gp-streamer-elevated);
}
.gp-streamer-card-copy { padding: 14px 16px 0; }
.gp-streamer-card-title { color: var(--gp-streamer-text); font-size: 1.02rem; font-weight: 650; margin: 0; }
.gp-streamer-score { color: var(--gp-streamer-primary); font-size: 1.05rem; font-weight: 750; }
.gp-streamer-band { color: var(--gp-streamer-accent); font-size: 0.78rem; margin-left: 6px; }
.gp-streamer-card-meta,
.gp-streamer-reasons { color: var(--gp-streamer-muted); font-size: 0.82rem; line-height: 1.45; }
.gp-streamer-confidence { color: var(--gp-streamer-text); font-size: 0.82rem; }
.gp-streamer-caution {
  color: #FFD78A;
  background: rgba(242, 184, 75, 0.10);
  border-left: 3px solid var(--gp-streamer-warning);
  border-radius: 4px;
  padding: 8px 10px;
  font-size: 0.80rem;
}
.gp-streamer-section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}
.gp-streamer-section-heading h3 { margin: 0; color: var(--gp-streamer-text); }
.gp-streamer-source-badge {
  border: 1px solid var(--gp-streamer-border);
  border-radius: 999px;
  color: var(--gp-streamer-muted);
  font-size: 0.75rem;
  padding: 5px 9px;
}
.gp-streamer-observed-note { color: var(--gp-streamer-muted); font-size: 0.84rem; }
.gp-streamer-metric-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
  margin: 12px 0 18px;
}
.gp-streamer-metric {
  background: var(--gp-streamer-surface);
  border: 1px solid var(--gp-streamer-border);
  border-radius: 10px;
  padding: 12px;
  min-height: 64px;
}
.gp-streamer-metric-label { display: block; color: var(--gp-streamer-muted); font-size: 0.74rem; margin-bottom: 5px; }
.gp-streamer-metric strong { color: var(--gp-streamer-text); font-size: 0.92rem; overflow-wrap: anywhere; }
.gp-streamer-steam {
  background: rgba(76, 141, 255, 0.08);
  border: 1px solid var(--gp-streamer-border);
  border-radius: 12px;
  color: var(--gp-streamer-text);
  margin: 12px 0;
  padding: 13px 15px;
}
.gp-streamer-steam span { color: var(--gp-streamer-muted); font-size: 0.82rem; }
.gp-streamer-creator {
  display: grid;
  grid-template-columns: 84px 1fr;
  gap: 14px;
  align-items: center;
  background: var(--gp-streamer-surface);
  border: 1px solid var(--gp-streamer-border);
  border-radius: 12px;
  margin: 10px 0;
  padding: 12px;
}
.gp-streamer-creator-image .gp-streamer-art,
.gp-streamer-creator-image .gp-streamer-placeholder { width: 84px; height: 84px; min-height: 84px; border-radius: 50%; }
.gp-streamer-creator a { color: var(--gp-streamer-primary); font-size: 0.82rem; }
.gp-streamer-shell :focus-visible { outline: 2px solid var(--gp-streamer-primary) !important; outline-offset: 2px; }
.gp-streamer-shell button,
.gp-streamer-shell input,
.gp-streamer-shell [role="option"] { min-height: 44px; }
@media (max-width: 640px) {
  .gp-streamer-hero { grid-template-columns: 1fr; gap: 0; }
  .gp-streamer-hero-copy { padding: 20px; }
  .gp-streamer-card { width: 100%; }
  .gp-streamer-metric-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .gp-streamer-section-heading { align-items: flex-start; flex-direction: column; }
}
@media (prefers-reduced-motion: reduce) {
  .gp-streamer-shell *,
  .gp-streamer-shell *::before,
  .gp-streamer-shell *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}
</style>
"""


def inject_streamer_theme(st) -> None:
    st.markdown(streamer_css(), unsafe_allow_html=True)
