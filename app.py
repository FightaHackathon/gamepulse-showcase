"""GamePulse native desktop entry point.

Run with: python app.py
"""

from pathlib import Path

from gamepulse.desktop_app import run_desktop


if __name__ == "__main__":
    raise SystemExit(run_desktop(Path(__file__).resolve().parent))
