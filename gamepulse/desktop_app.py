"""Native PySide6 application shell for GamePulse.

This module intentionally contains no Streamlit dependency.  It reuses the
existing catalogue, recommendation, Twitch and developer-analysis modules.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDoubleSpinBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gamepulse.catalog import Catalog, GameSummary
from gamepulse.config import Settings
from gamepulse.desktop_models import compact_number, money, owner_range, percent
from gamepulse.desktop_theme import APP_STYLESHEET
from gamepulse.forecasting import daily_counts_for_game, forecast_review_activity
from gamepulse.market_analysis import MarketSnapshot, analyze_developer_opportunity, analyze_market, latest_market_snapshot
from gamepulse.providers.twitch import TwitchProvider
from gamepulse.recommendations import PlayerPreferences, RecommendationEngine
from gamepulse.review_analysis import analyze_reviews
from gamepulse.streamer_opportunity import StreamerProfile, score_game_opportunities


NAV_ITEMS = (
    ("Overview", "⌂"),
    ("Player", "◈"),
    ("Streamer", "◉"),
    ("Developer", "◇"),
)


def _label(text: str, object_name: str | None = None, *, word_wrap: bool = False) -> QLabel:
    widget = QLabel(text)
    if object_name:
        widget.setObjectName(object_name)
    widget.setWordWrap(word_wrap)
    return widget


def _clear(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        widget = item.widget()
        child = item.layout()
        if widget is not None:
            widget.deleteLater()
        elif child is not None:
            _clear(child)


def metric_card(label: str, value: str, detail: str = "") -> QFrame:
    card = QFrame()
    card.setObjectName("card")
    box = QVBoxLayout(card)
    box.setContentsMargins(16, 14, 16, 14)
    box.setSpacing(4)
    box.addWidget(_label(label.upper(), "metricLabel"))
    box.addWidget(_label(value, "metricValue"))
    if detail:
        box.addWidget(_label(detail, "muted", word_wrap=True))
    return card


def section_header(title: str, subtitle: str = "") -> QWidget:
    root = QWidget()
    layout = QVBoxLayout(root)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(3)
    layout.addWidget(_label(title, "sectionTitle"))
    if subtitle:
        layout.addWidget(_label(subtitle, "muted"))
    return root


def page_scroll() -> tuple[QScrollArea, QWidget, QVBoxLayout]:
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    host = QWidget()
    layout = QVBoxLayout(host)
    layout.setContentsMargins(28, 24, 28, 32)
    layout.setSpacing(18)
    scroll.setWidget(host)
    return scroll, host, layout


class GamePulseWindow(QMainWindow):
    def __init__(self, settings: Settings, catalog: Catalog):
        super().__init__()
        self.settings = settings
        self.catalog = catalog
        self.recommendations = RecommendationEngine(settings.database_path)
        self.demo_games = catalog.rank_demo_candidates(30)
        if not self.demo_games:
            raise RuntimeError("No curated games are available in the local database.")
        self.selected_game = self.demo_games[0]

        self.setWindowTitle("GamePulse — Game Intelligence Workspace")
        self.resize(1360, 860)
        self.setMinimumSize(1050, 680)

        shell = QWidget()
        shell.setObjectName("shell")
        root = QHBoxLayout(shell)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_sidebar())

        self.pages = QStackedWidget()
        self.overview_page = self._build_overview()
        self.player_page = self._build_player()
        self.streamer_page = self._build_streamer()
        self.developer_page = self._build_developer()
        for page in (self.overview_page, self.player_page, self.streamer_page, self.developer_page):
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)

        self.setCentralWidget(shell)
        self.statusBar().showMessage(f"Local data · {settings.processed_dir.name} · {settings.database_path.name}")
        self._select_nav(0)

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(18, 22, 18, 18)
        layout.setSpacing(8)

        brand_row = QHBoxLayout()
        brand_row.setSpacing(0)
        brand_row.addWidget(_label("Game", "brand"))
        brand_row.addWidget(_label("Pulse", "brandAccent"))
        brand_row.addStretch()
        layout.addLayout(brand_row)
        layout.addWidget(_label("LOCAL INTELLIGENCE LAB", "eyebrow"))
        layout.addSpacing(20)

        self.nav_buttons: list[QPushButton] = []
        for index, (name, icon) in enumerate(NAV_ITEMS):
            button = QPushButton(f"{icon}   {name}")
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.clicked.connect(lambda checked=False, i=index: self._select_nav(i))
            self.nav_buttons.append(button)
            layout.addWidget(button)
        layout.addStretch()

        local = QFrame()
        local.setObjectName("accentCard")
        box = QVBoxLayout(local)
        box.setContentsMargins(13, 12, 13, 12)
        box.addWidget(_label("LOCAL MODE", "eyebrow"))
        box.addWidget(_label("No hosted UI server", "sectionTitle"))
        box.addWidget(_label("Credentials stay in your local .env file.", "muted", word_wrap=True))
        layout.addWidget(local)
        return sidebar

    def _select_nav(self, index: int) -> None:
        self.pages.setCurrentIndex(index)
        for i, button in enumerate(self.nav_buttons):
            button.setChecked(i == index)
        if index == 0:
            self.refresh_overview()
        elif index == 2:
            self.refresh_streamer()
        elif index == 3:
            self.refresh_developer()

    def _page_title(self, layout: QVBoxLayout, eyebrow: str, title: str, subtitle: str) -> None:
        layout.addWidget(_label(eyebrow, "eyebrow"))
        layout.addWidget(_label(title, "pageTitle"))
        layout.addWidget(_label(subtitle, "pageSubtitle", word_wrap=True))

    def _game_selector(self, on_change) -> QComboBox:
        combo = QComboBox()
        for game in self.demo_games:
            combo.addItem(game.name, game.steam_app_id)
        combo.currentIndexChanged.connect(lambda _: on_change(int(combo.currentData())))
        return combo

    def _set_selected_game(self, app_id: int) -> None:
        self.selected_game = self.catalog.get_game(app_id)
        self.statusBar().showMessage(f"Selected · {self.selected_game.name} · Steam AppID {app_id}")

    # Overview -------------------------------------------------------------
    def _build_overview(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(layout, "GAME INTELLIGENCE WORKSPACE", "See the market before you make the move.", "Explore player fit, creator opportunity and developer signals from one local desktop app.")

        hero = QFrame()
        hero.setObjectName("hero")
        hero_box = QVBoxLayout(hero)
        hero_box.setContentsMargins(24, 22, 24, 22)
        hero_box.setSpacing(9)
        hero_box.addWidget(_label("TODAY'S SIGNAL", "eyebrow"))
        self.overview_game_name = _label("", "pageTitle")
        hero_box.addWidget(self.overview_game_name)
        self.overview_game_meta = _label("", "pageSubtitle", word_wrap=True)
        hero_box.addWidget(self.overview_game_meta)
        hero_actions = QHBoxLayout()
        explore = QPushButton("Explore as Player")
        explore.setObjectName("primaryButton")
        explore.clicked.connect(lambda: self._select_nav(1))
        dev = QPushButton("Open Developer Brief")
        dev.setObjectName("secondaryButton")
        dev.clicked.connect(lambda: self._select_nav(3))
        hero_actions.addWidget(explore)
        hero_actions.addWidget(dev)
        hero_actions.addStretch()
        hero_box.addLayout(hero_actions)
        layout.addWidget(hero)

        self.overview_metrics = QGridLayout()
        self.overview_metrics.setSpacing(12)
        layout.addLayout(self.overview_metrics)

        layout.addWidget(section_header("Three views, one dataset", "Use the same selected catalogue game across each decision context."))
        cards = QGridLayout()
        cards.setSpacing(12)
        for column, (title, copy) in enumerate((
            ("Player discovery", "Search the catalogue and get explainable recommendations based on tags, genre, price and platform."),
            ("Streamer opportunity", "Compare observed Twitch demand against channel competition and creator reach."),
            ("Developer brief", "Inspect comparable games, review sentiment and a 30-day review-activity forecast."),
        )):
            card = QFrame(); card.setObjectName("card")
            box = QVBoxLayout(card); box.setContentsMargins(18, 17, 18, 17)
            box.addWidget(_label(title, "sectionTitle")); box.addWidget(_label(copy, "muted", word_wrap=True)); box.addStretch()
            cards.addWidget(card, 0, column)
        layout.addLayout(cards)
        layout.addStretch()
        return scroll

    def refresh_overview(self) -> None:
        game = self.selected_game
        self.overview_game_name.setText(game.name)
        genres = " · ".join(game.genres[:3]) or "Uncategorized"
        self.overview_game_meta.setText(f"{genres}  •  {money(game.price_usd)}  •  {percent(game.review_score)} review score")
        _clear(self.overview_metrics)
        values = (
            ("Estimated owners", owner_range(game.owners_low, game.owners_high), "Public catalogue estimate"),
            ("Peak CCU", compact_number(game.peak_ccu), "Observed concurrency signal"),
            ("Reviews", compact_number(game.total_reviews), "Public review volume"),
            ("Tags", str(len(game.tags)), ", ".join(game.tags[:3]) or "No tags"),
        )
        for i, data in enumerate(values):
            self.overview_metrics.addWidget(metric_card(*data), 0, i)

    # Player ---------------------------------------------------------------
    def _build_player(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(layout, "PLAYER MODE", "Find your next game with reasons, not hype.", "Search a seed game, tune the price/platform filters, then compare explainable matches.")

        controls = QFrame(); controls.setObjectName("card")
        grid = QGridLayout(controls); grid.setContentsMargins(16, 16, 16, 16); grid.setHorizontalSpacing(12); grid.setVerticalSpacing(10)
        self.player_search = QLineEdit(); self.player_search.setPlaceholderText("Search Steam catalogue…")
        self.player_search.returnPressed.connect(self.search_player_games)
        search_button = QPushButton("Search"); search_button.setObjectName("primaryButton"); search_button.clicked.connect(self.search_player_games)
        self.player_seed = self._game_selector(self._player_seed_changed)
        self.player_os = QComboBox(); self.player_os.addItems(["Any platform", "Windows", "macOS", "Linux"])
        self.player_price = QDoubleSpinBox(); self.player_price.setRange(0, 200); self.player_price.setValue(60); self.player_price.setPrefix("$"); self.player_price.setSuffix(" max")
        self.player_mode = QComboBox(); self.player_mode.addItem("Best matches", "best_matches"); self.player_mode.addItem("Hidden gems", "hidden_gems")
        refresh = QPushButton("Generate recommendations"); refresh.setObjectName("secondaryButton"); refresh.clicked.connect(self.refresh_player_recommendations)
        grid.addWidget(self.player_search, 0, 0, 1, 3); grid.addWidget(search_button, 0, 3)
        grid.addWidget(self.player_seed, 1, 0); grid.addWidget(self.player_os, 1, 1); grid.addWidget(self.player_price, 1, 2); grid.addWidget(self.player_mode, 1, 3); grid.addWidget(refresh, 2, 0, 1, 4)
        layout.addWidget(controls)

        self.player_search_results = QComboBox(); self.player_search_results.setVisible(False); self.player_search_results.currentIndexChanged.connect(self._search_result_selected)
        layout.addWidget(self.player_search_results)
        layout.addWidget(section_header("Recommended for this seed", "Scores combine catalogue similarity, preference fit, reviews, price and platform support."))
        self.player_table = QTableWidget(0, 6)
        self.player_table.setHorizontalHeaderLabels(["Game", "Match", "Price", "Reviews", "Year", "Why it fits"])
        self.player_table.horizontalHeader().setStretchLastSection(True)
        self.player_table.setAlternatingRowColors(True); self.player_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.player_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.player_table.doubleClicked.connect(self.open_selected_store)
        layout.addWidget(self.player_table)
        self.refresh_player_recommendations()
        return scroll

    def _player_seed_changed(self, app_id: int) -> None:
        self._set_selected_game(app_id)
        self.refresh_player_recommendations()

    def search_player_games(self) -> None:
        results = self.catalog.search_games(self.player_search.text(), limit=25)
        self.player_search_results.blockSignals(True); self.player_search_results.clear()
        for game in results:
            self.player_search_results.addItem(f"{game.name} · {money(game.price_usd)} · {percent(game.review_score)}", game.steam_app_id)
        self.player_search_results.blockSignals(False)
        self.player_search_results.setVisible(bool(results))
        if results:
            self.player_search_results.setCurrentIndex(0)

    def _search_result_selected(self, index: int) -> None:
        if index < 0 or self.player_search_results.currentData() is None:
            return
        app_id = int(self.player_search_results.currentData())
        game = self.catalog.get_game(app_id)
        existing = self.player_seed.findData(app_id)
        if existing < 0:
            self.player_seed.addItem(game.name, app_id); existing = self.player_seed.count() - 1
        self.player_seed.setCurrentIndex(existing)

    def refresh_player_recommendations(self) -> None:
        app_id = int(self.player_seed.currentData()) if self.player_seed.currentData() is not None else self.selected_game.steam_app_id
        self._set_selected_game(app_id)
        os_value = self.player_os.currentText()
        preferences = PlayerPreferences(
            max_price_usd=float(self.player_price.value()),
            operating_system=None if os_value == "Any platform" else os_value,
            discovery_mode=str(self.player_mode.currentData()),
        )
        rows = self.recommendations.recommend_similar(app_id, preferences, limit=20)
        self.player_table.setRowCount(len(rows))
        self._player_store_urls: dict[int, str] = {}
        for row_index, item in enumerate(rows):
            reason = " · ".join(item.reasons)
            values = (item.name, f"{item.match_score}/100", money(item.price_usd), percent(item.review_score), item.release_year or "—", reason)
            for column, value in enumerate(values):
                self.player_table.setItem(row_index, column, QTableWidgetItem(str(value)))
            self._player_store_urls[row_index] = item.steam_store_url
        self.player_table.resizeColumnsToContents()

    def open_selected_store(self) -> None:
        row = self.player_table.currentRow()
        url = getattr(self, "_player_store_urls", {}).get(row)
        if url:
            webbrowser.open(url)

    # Streamer -------------------------------------------------------------
    def _build_streamer(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(layout, "STREAMER MODE", "Spot categories where attention has room to breathe.", "GamePulse compares observed viewers, channel density, growth and your channel strategy.")
        controls = QFrame(); controls.setObjectName("card")
        row = QHBoxLayout(controls); row.setContentsMargins(16, 16, 16, 16)
        self.streamer_tier = QComboBox(); self.streamer_tier.addItems(["Emerging", "Mid-size", "Large"])
        self.streamer_strategy = QComboBox(); self.streamer_strategy.addItems(["Balanced", "Reach", "Growth"])
        refresh = QPushButton("Refresh opportunity snapshot"); refresh.setObjectName("primaryButton"); refresh.clicked.connect(self.refresh_streamer)
        row.addWidget(_label("Channel size", "muted")); row.addWidget(self.streamer_tier); row.addWidget(_label("Strategy", "muted")); row.addWidget(self.streamer_strategy); row.addWidget(refresh); row.addStretch()
        layout.addWidget(controls)
        self.streamer_source = _label("", "muted", word_wrap=True); layout.addWidget(self.streamer_source)
        self.streamer_metrics = QGridLayout(); self.streamer_metrics.setSpacing(12); layout.addLayout(self.streamer_metrics)
        self.streamer_table = QTableWidget(0, 6); self.streamer_table.setHorizontalHeaderLabels(["Category", "Score", "Viewers", "Channels", "Viewers / channel", "Signal"]); self.streamer_table.horizontalHeader().setStretchLastSection(True); self.streamer_table.setAlternatingRowColors(True); self.streamer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.streamer_table)
        return scroll

    def refresh_streamer(self) -> None:
        provider = TwitchProvider(self.settings.twitch_snapshot_path, self.settings.twitch_client_id, self.settings.twitch_client_secret)
        try:
            snapshot = provider.get_game_trends()
            profile = StreamerProfile(channel_size_tier=self.streamer_tier.currentText().casefold(), strategy=self.streamer_strategy.currentText().casefold())
            opportunities = score_game_opportunities(snapshot.data, profile)
        except Exception as exc:
            self.streamer_source.setText(f"Could not load Twitch snapshot: {exc}")
            self.streamer_table.setRowCount(0)
            return
        self.streamer_source.setText(f"{snapshot.mode} · {snapshot.source_name} · observed {snapshot.observed_at}")
        _clear(self.streamer_metrics)
        top = opportunities[0] if opportunities else None
        metrics = (
            ("Categories observed", str(len(opportunities)), "Bounded Twitch snapshot"),
            ("Top opportunity", top.name if top else "—", top.score_band if top else "No signal"),
            ("Top score", f"{top.score * 100:.0f}/100" if top else "—", "Demand vs competition"),
            ("Top reach", f"{top.viewer_to_channel:.1f}" if top else "—", "Viewers per observed channel"),
        )
        for i, data in enumerate(metrics): self.streamer_metrics.addWidget(metric_card(*data), 0, i)
        shown = opportunities[:30]; self.streamer_table.setRowCount(len(shown))
        for r, item in enumerate(shown):
            values = (item.name, f"{item.score * 100:.0f}", compact_number(item.viewer_count), compact_number(item.channel_count), f"{item.viewer_to_channel:.1f}", item.reasons[0] if item.reasons else item.score_band)
            for c, value in enumerate(values): self.streamer_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.streamer_table.resizeColumnsToContents()

    # Developer ------------------------------------------------------------
    def _build_developer(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(layout, "DEVELOPER MODE", "Turn public signals into a validation brief.", "Compare market position, review themes and near-term review activity without pretending public estimates are verified sales.")
        top = QHBoxLayout(); self.developer_game = self._game_selector(self._developer_game_changed); top.addWidget(_label("Focus game", "muted")); top.addWidget(self.developer_game, 1); top.addStretch(); layout.addLayout(top)
        self.developer_metrics = QGridLayout(); self.developer_metrics.setSpacing(12); layout.addLayout(self.developer_metrics)
        self.developer_summary = QFrame(); self.developer_summary.setObjectName("hero"); self.developer_summary_box = QVBoxLayout(self.developer_summary); self.developer_summary_box.setContentsMargins(22, 20, 22, 20); layout.addWidget(self.developer_summary)
        layout.addWidget(section_header("Comparable games", "Ranked by overlapping tags/genres and review volume."))
        self.developer_table = QTableWidget(0, 5); self.developer_table.setHorizontalHeaderLabels(["Game", "Overlap", "Price", "Review score", "Owners"]); self.developer_table.horizontalHeader().setStretchLastSection(True); self.developer_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); layout.addWidget(self.developer_table)
        return scroll

    def _developer_game_changed(self, app_id: int) -> None:
        self._set_selected_game(app_id); self.refresh_developer()

    def refresh_developer(self) -> None:
        game = self.selected_game
        if hasattr(self, "developer_game"):
            idx = self.developer_game.findData(game.steam_app_id)
            if idx >= 0 and idx != self.developer_game.currentIndex():
                self.developer_game.blockSignals(True); self.developer_game.setCurrentIndex(idx); self.developer_game.blockSignals(False)
        snapshot = latest_market_snapshot(self.settings.database_path, game.steam_app_id) or MarketSnapshot(game.steam_app_id, None, game.owners_low, game.owners_high, game.price_usd, game.total_reviews, game.peak_ccu, "Local prepared data", "Steam/Kaggle prepared snapshot", self.settings.processed_dir.name)
        comparables = self.catalog.comparable_games(game.steam_app_id, limit=8)
        comparable_records = [{"name": item.name, "price_usd": item.price_usd, "review_score": item.review_score, "owners_high": item.owners_high} for item in comparables]
        market = analyze_market(snapshot, comparable_records)
        reviews = analyze_reviews(self.settings.database_path, game.steam_app_id)
        forecast = forecast_review_activity(daily_counts_for_game(self.settings.database_path, game.steam_app_id))
        opportunity = analyze_developer_opportunity(snapshot, reviews, forecast, 0, len(comparables), creator_scores=())

        _clear(self.developer_metrics)
        gross = "—" if market.estimated_gross_low is None or market.estimated_gross_high is None else f"{compact_number(market.estimated_gross_low)}–{compact_number(market.estimated_gross_high)}"
        metrics = (
            ("Opportunity", f"{opportunity.score:.0f}/100", opportunity.score_band),
            ("Owners", owner_range(snapshot.owners_low, snapshot.owners_high), "Public estimate"),
            ("Gross scenario", gross, "Owners × current price; not verified revenue"),
            ("30-day reviews", f"{forecast.low:,}–{forecast.high:,}", f"Central estimate {forecast.expected:,}"),
        )
        for i, data in enumerate(metrics): self.developer_metrics.addWidget(metric_card(*data), 0, i)

        _clear(self.developer_summary_box)
        self.developer_summary_box.addWidget(_label("VALIDATION BRIEF", "eyebrow"))
        self.developer_summary_box.addWidget(_label(game.name, "pageTitle"))
        self.developer_summary_box.addWidget(_label(f"{reviews.review_count:,} reviews analyzed · {reviews.positive_ratio:.0%} recommended", "pageSubtitle"))
        self.developer_summary_box.addWidget(_label("Positive themes · " + (", ".join(reviews.positive_themes) or "Not enough data"), "muted", word_wrap=True))
        self.developer_summary_box.addWidget(_label("Negative themes · " + (", ".join(reviews.negative_themes) or "Not enough data"), "muted", word_wrap=True))
        self.developer_summary_box.addWidget(_label(f"Source · {snapshot.source_mode} · {snapshot.source_name} · {snapshot.observed_at}", "muted", word_wrap=True))

        self.developer_table.setRowCount(len(comparables))
        for r, item in enumerate(comparables):
            values = (item.name, str(item.comparable_overlap), money(item.price_usd), percent(item.review_score), owner_range(item.owners_low, item.owners_high))
            for c, value in enumerate(values): self.developer_table.setItem(r, c, QTableWidgetItem(str(value)))
        self.developer_table.resizeColumnsToContents()


def run_desktop(root: Path | None = None) -> int:
    root = root or Path(__file__).resolve().parents[1]
    settings = Settings.from_env(root)
    app = QApplication.instance() or QApplication(sys.argv)
    app.setApplicationName("GamePulse")
    app.setOrganizationName("GamePulse")
    app.setStyle("Fusion")
    app.setFont(QFont("Segoe UI", 10))
    app.setStyleSheet(APP_STYLESHEET)

    if not settings.database_path.exists():
        QMessageBox.critical(None, "GamePulse database missing", "The local prototype database was not found.\n\nRun scripts/build_prototype_database.py first, then launch GamePulse again.")
        return 2
    try:
        window = GamePulseWindow(settings, Catalog(settings.database_path))
    except Exception as exc:
        QMessageBox.critical(None, "GamePulse could not start", str(exc))
        return 3
    window.show()
    return app.exec()
