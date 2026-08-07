"""QSS theme for the native GamePulse desktop application."""

APP_STYLESHEET = r"""
QMainWindow, QWidget {
    background: #0b1020;
    color: #e8edf7;
    font-family: "Segoe UI", "Inter", sans-serif;
    font-size: 13px;
}
QWidget#shell { background: #0b1020; }
QFrame#sidebar {
    background: #0f172a;
    border-right: 1px solid #1e293b;
}
QLabel#brand {
    color: #f8fafc;
    font-size: 22px;
    font-weight: 800;
}
QLabel#brandAccent { color: #38bdf8; font-size: 22px; font-weight: 800; }
QLabel#eyebrow {
    color: #7dd3fc;
    font-size: 11px;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#pageTitle {
    color: #f8fafc;
    font-size: 28px;
    font-weight: 800;
}
QLabel#pageSubtitle { color: #94a3b8; font-size: 13px; }
QLabel#sectionTitle { color: #f8fafc; font-size: 17px; font-weight: 700; }
QLabel#muted { color: #94a3b8; }
QLabel#metricValue { color: #f8fafc; font-size: 24px; font-weight: 800; }
QLabel#metricLabel { color: #94a3b8; font-size: 11px; font-weight: 600; }
QLabel#pill {
    background: #172554;
    color: #93c5fd;
    border: 1px solid #1d4ed8;
    border-radius: 10px;
    padding: 4px 8px;
    font-size: 11px;
    font-weight: 600;
}
QFrame#hero {
    border: 1px solid #1e3a5f;
    border-radius: 20px;
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #101d3b, stop:0.55 #102a43, stop:1 #0f172a);
}
QFrame#card {
    background: #111827;
    border: 1px solid #1f2937;
    border-radius: 16px;
}
QFrame#card:hover { border: 1px solid #334155; }
QFrame#accentCard {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #12243d, stop:1 #172033);
    border: 1px solid #1e40af;
    border-radius: 16px;
}
QPushButton#navButton {
    color: #94a3b8;
    background: transparent;
    border: none;
    border-radius: 10px;
    padding: 11px 14px;
    text-align: left;
    font-weight: 600;
}
QPushButton#navButton:hover { background: #172033; color: #e2e8f0; }
QPushButton#navButton:checked {
    color: #e0f2fe;
    background: #0c4a6e;
    border: 1px solid #075985;
}
QPushButton#primaryButton {
    background: #0284c7;
    color: white;
    border: none;
    border-radius: 10px;
    padding: 10px 16px;
    font-weight: 700;
}
QPushButton#primaryButton:hover { background: #0ea5e9; }
QPushButton#secondaryButton {
    background: #172033;
    color: #dbeafe;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 9px 14px;
    font-weight: 650;
}
QPushButton#secondaryButton:hover { border-color: #475569; background: #1e293b; }
QLineEdit, QComboBox, QDoubleSpinBox {
    background: #0f172a;
    color: #e2e8f0;
    border: 1px solid #334155;
    border-radius: 10px;
    padding: 8px 10px;
    min-height: 20px;
    selection-background-color: #0369a1;
}
QLineEdit:focus, QComboBox:focus, QDoubleSpinBox:focus { border-color: #38bdf8; }
QComboBox QAbstractItemView {
    background: #0f172a;
    color: #e2e8f0;
    border: 1px solid #334155;
    selection-background-color: #0c4a6e;
}
QTableWidget {
    background: #0f172a;
    alternate-background-color: #111827;
    color: #e2e8f0;
    border: 1px solid #1f2937;
    border-radius: 12px;
    gridline-color: #1f2937;
    selection-background-color: #0c4a6e;
}
QHeaderView::section {
    background: #111827;
    color: #94a3b8;
    border: none;
    border-bottom: 1px solid #273449;
    padding: 9px;
    font-weight: 700;
}
QScrollArea { border: none; background: transparent; }
QScrollBar:vertical { background: #0f172a; width: 10px; margin: 0; }
QScrollBar::handle:vertical { background: #334155; min-height: 24px; border-radius: 5px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QStatusBar { background: #0f172a; color: #64748b; border-top: 1px solid #1e293b; }
QToolTip { color: #e2e8f0; background: #111827; border: 1px solid #334155; padding: 6px; }
"""
