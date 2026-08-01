"""Visual tokens and responsive CSS for Player Mode only."""

from __future__ import annotations


PLAYER_COLORS = {
    "canvas": "#080D18",
    "surface": "#111A2B",
    "elevated_surface": "#172338",
    "border": "#273550",
    "primary": "#4C8DFF",
    "personalization": "#8B7CFF",
    "success": "#52D6A0",
    "warning": "#F2B84B",
    "error": "#FF6B78",
    "primary_text": "#F4F7FC",
    "secondary_text": "#9EABC0",
}


def player_css() -> str:
    """Return Player Mode CSS tokens and responsive component styles."""
    return """
<style>
:root,
.gp-player-shell {
  --gp-canvas: #080D18;
  --gp-surface: #111A2B;
  --gp-elevated: #172338;
  --gp-border: #273550;
  --gp-primary: #4C8DFF;
  --gp-personalization: #8B7CFF;
  --gp-success: #52D6A0;
  --gp-warning: #F2B84B;
  --gp-error: #FF6B78;
  --gp-text: #F4F7FC;
  --gp-muted: #9EABC0;
}
.gp-player-shell {
  color: var(--gp-text);
}
.gp-player-panel {
  background: var(--gp-surface);
  border: 1px solid var(--gp-border);
  border-radius: 14px;
  padding: 24px;
}
.gp-player-hero {
  display: grid;
  grid-template-columns: minmax(180px, 28%) 1fr;
  gap: 24px;
  align-items: stretch;
  background: linear-gradient(135deg, #111A2B 0%, #172338 100%);
  border: 1px solid var(--gp-border);
  border-radius: 16px;
  overflow: hidden;
  margin: 0 0 22px;
}
.gp-player-hero-art,
.gp-game-art {
  width: 100%;
  height: 100%;
  min-height: 150px;
  object-fit: cover;
  background: #0C1322;
}
.gp-game-art-placeholder {
  display: grid;
  place-items: center;
  min-height: 150px;
  color: var(--gp-muted);
  background: #0C1322;
  font-size: 0.82rem;
}
.gp-player-hero-copy {
  padding: 26px 26px 26px 0;
}
.gp-player-hero-title {
  margin: 0 0 8px;
  color: var(--gp-text);
  font-size: clamp(1.45rem, 2.4vw, 2.1rem);
  line-height: 1.1;
}
.gp-player-eyebrow,
.gp-player-muted {
  color: var(--gp-muted);
  font-size: 0.86rem;
}
.gp-player-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 15px;
}
.gp-player-badge {
  border: 1px solid var(--gp-border);
  border-radius: 999px;
  color: var(--gp-secondary, var(--gp-muted));
  padding: 5px 10px;
  font-size: 0.78rem;
}
.gp-player-card {
  background: var(--gp-surface);
  border: 1px solid var(--gp-border);
  border-radius: 14px;
  overflow: hidden;
  padding: 0 0 14px;
  transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
}
.gp-player-card:hover {
  transform: translateY(-3px);
  border-color: var(--gp-primary);
  background: var(--gp-elevated);
}
.gp-player-card-copy {
  padding: 14px 16px 0;
}
.gp-player-card-title {
  color: var(--gp-text);
  font-size: 1.02rem;
  font-weight: 650;
  margin: 0;
}
.gp-player-card-meta,
.gp-player-reasons {
  color: var(--gp-muted);
  font-size: 0.82rem;
  line-height: 1.45;
}
.gp-player-match {
  color: var(--gp-primary);
  font-size: 0.84rem;
  font-weight: 700;
}
.gp-player-match-band {
  color: var(--gp-personalization);
  font-size: 0.75rem;
  margin-left: 6px;
}
.gp-player-card-link {
  color: var(--gp-primary);
  font-weight: 650;
  text-decoration: none;
}
.gp-player-card-link:hover,
.gp-player-card-link:focus-visible {
  text-decoration: underline;
}
.gp-player-shell button,
.gp-player-shell input,
.gp-player-shell [role="option"] {
  min-height: 44px;
}
.gp-player-shell :focus-visible {
  outline: 2px solid var(--gp-primary) !important;
  outline-offset: 2px;
}
@media (max-width: 640px) {
  .gp-player-panel { padding: 16px; }
  .gp-player-hero { grid-template-columns: 1fr; gap: 0; }
  .gp-player-hero-copy { padding: 20px; }
  .gp-player-card { width: 100%; }
}
@media (prefers-reduced-motion: reduce) {
  .gp-player-shell *,
  .gp-player-shell *::before,
  .gp-player-shell *::after {
    transition-duration: 0.01ms !important;
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    scroll-behavior: auto !important;
  }
}
</style>
"""


def inject_player_theme(st) -> None:
    st.markdown(player_css(), unsafe_allow_html=True)
