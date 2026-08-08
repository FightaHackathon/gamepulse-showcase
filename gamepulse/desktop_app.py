"""Native PySide6 application shell for GamePulse.

The desktop UI consumes source-neutral GamePulse providers and can run with
Twitch credentials completely absent. Twitch remains an optional enhancement.
"""

from __future__ import annotations

import sys
import webbrowser
from pathlib import Path

from PySide6.QtCore import QThread, Signal
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
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gamepulse.catalog import Catalog
from gamepulse.config import Settings
from gamepulse.developer_prediction import DeveloperPredictionInput, predict_developer_outcome
from gamepulse.developer_intelligence import DeveloperIntelligence
from gamepulse.desktop_models import compact_number, money, owner_range, percent
from gamepulse.desktop_theme import APP_STYLESHEET
from gamepulse.forecasting import daily_counts_for_game, forecast_review_activity
from gamepulse.market_analysis import (
    MarketSnapshot,
    analyze_developer_opportunity,
    analyze_market,
    latest_market_snapshot,
)
from gamepulse.player_profile import infer_preferences
from gamepulse.providers.composite import CompositeSignalProvider
from gamepulse.providers.steam import SteamProvider, SteamProviderError
from gamepulse.providers.steamspy import SteamSpyEstimate, SteamSpyProvider
from gamepulse.providers.twitch import TwitchProvider
from gamepulse.providers.twitchtracker import TwitchTrackerProvider, TwitchTrackerSummary
from gamepulse.recommendations import PlayerPreferences, RecommendationEngine
from gamepulse.review_analysis import analyze_reviews
from gamepulse.streamer_fit import rank_creators
from gamepulse.streamer_opportunity import (
    StreamerProfile,
    audience_metric_label,
    competition_metric_label,
    evaluate_snapshot_freshness,
    score_game_opportunities,
)


NAV_ITEMS = (
    ("Overview", "⌂"),
    ("Player", "◈"),
    ("Streamer", "◉"),
    ("Developer", "◇"),
)


NAV_ITEMS = NAV_ITEMS + (("Settings", "S"),)


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


def _signal_value(value: float | int | None) -> str:
    if value is None:
        return "Unavailable"
    return compact_number(value)


def _creator_audience(value: float | None, metric: str | None) -> str:
    if value is None:
        return "Unavailable"
    labels = {
        "avg_viewers": "reported avg viewers",
        "twitch_viewers": "observed Twitch viewers",
        "youtube_avg_viewers": "reported YouTube avg viewers",
    }
    label = labels.get(str(metric or ""), str(metric or "audience").replace("_", " "))
    return f"{compact_number(value)} {label}"


class _DeveloperMarketWorker(QThread):
    results_ready = Signal(object, object)

    def __init__(self, database_path: Path):
        super().__init__()
        self.database_path = Path(database_path)

    def run(self) -> None:
        try:
            intelligence = DeveloperIntelligence(self.database_path)
            trends = intelligence.explore_trends(limit=8)
            opportunities = list(intelligence.genre_opportunities(limit=5))
            opportunities.extend(intelligence.tag_opportunities(limit=5))
            opportunities.sort(
                key=lambda item: (-item.score, -item.demand, item.dimension, item.value.casefold())
            )
            self.results_ready.emit(trends, tuple(opportunities[:10]))
        except Exception:
            self.results_ready.emit((), ())


class _ExternalEstimateWorker(QThread):
    """Run the two bounded public estimate requests away from the UI thread."""

    results_ready = Signal(object, object)

    def __init__(self, game_name: str, app_id: int, cache_path: Path):
        super().__init__()
        self.game_name = game_name
        self.app_id = int(app_id)
        self.cache_path = Path(cache_path)

    def run(self) -> None:
        twitchtracker = TwitchTrackerProvider(cache_path=self.cache_path)
        steamspy = SteamSpyProvider(cache_path=self.cache_path)
        self.results_ready.emit(
            twitchtracker.get_game_summary(self.game_name),
            steamspy.get_app_estimate(self.app_id),
        )


class GamePulseWindow(QMainWindow):
    def __init__(self, settings: Settings, catalog: Catalog):
        super().__init__()
        self.settings = settings
        self.catalog = catalog
        self.recommendations = RecommendationEngine(settings.database_path)
        self.intelligence = DeveloperIntelligence(settings.database_path)
        self.developer_market_worker: _DeveloperMarketWorker | None = None
        self.external_estimate_worker: _ExternalEstimateWorker | None = None
        self.twitchtracker_summary: TwitchTrackerSummary | None = None
        self.steamspy_estimate: SteamSpyEstimate | None = None
        self.external_estimate_app_id: int | None = None
        self.steam = SteamProvider(settings.steam_web_api_key)
        self.streamer_preferences = PlayerPreferences()
        self.streamer_library = None

        twitch_provider = None
        if (
            settings.twitch_enabled
            or settings.game_signal_provider == "twitch"
            or settings.creator_provider == "twitch"
        ):
            twitch_provider = TwitchProvider(
                settings.twitch_snapshot_path,
                settings.twitch_client_id,
                settings.twitch_client_secret,
            )

        self.signals = CompositeSignalProvider(
            database_path=settings.database_path,
            creator_directory_path=settings.creator_directory_path,
            snapshot_path=settings.gamepulse_snapshot_path,
            twitch_provider=twitch_provider,
            game_provider_mode=settings.game_signal_provider,
            creator_provider_mode=settings.creator_provider,
        )

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
        self.settings_page = self._build_settings()
        for page in (
            self.overview_page,
            self.player_page,
            self.streamer_page,
            self.developer_page,
            self.settings_page,
        ):
            self.pages.addWidget(page)
        root.addWidget(self.pages, 1)

        self.setCentralWidget(shell)
        self.statusBar().showMessage(
            f"Local data · {settings.processed_dir.name} · {settings.database_path.name}"
        )
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
        box.addWidget(
            _label(
                "Steam/public data works without Twitch credentials. Optional credentials stay in your local .env file.",
                "muted",
                word_wrap=True,
            )
        )
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
            self.refresh_developer(background=True)

    def _page_title(
        self, layout: QVBoxLayout, eyebrow: str, title: str, subtitle: str
    ) -> None:
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
        self.statusBar().showMessage(
            f"Selected · {self.selected_game.name} · Steam AppID {app_id}"
        )

    # Overview -------------------------------------------------------------
    def _build_overview(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(
            layout,
            "GAME INTELLIGENCE WORKSPACE",
            "See the market before you make the move.",
            "Explore player fit, creator opportunity and developer signals from one local desktop app.",
        )

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

        layout.addWidget(
            section_header(
                "Three views, one dataset",
                "Use the same selected catalogue game across each decision context.",
            )
        )
        cards = QGridLayout()
        cards.setSpacing(12)
        for column, (title, copy) in enumerate(
            (
                (
                    "Player discovery",
                    "Search the catalogue and get explainable recommendations based on tags, genre, price and platform.",
                ),
                (
                    "Streamer opportunity",
                    "Compare legitimate player/activity signals, growth and available competition evidence without assuming Twitch data exists.",
                ),
                (
                    "Developer brief",
                    "Inspect comparable games, review sentiment, creator fit and a 30-day review-activity forecast.",
                ),
            )
        ):
            card = QFrame()
            card.setObjectName("card")
            box = QVBoxLayout(card)
            box.setContentsMargins(18, 17, 18, 17)
            box.addWidget(_label(title, "sectionTitle"))
            box.addWidget(_label(copy, "muted", word_wrap=True))
            box.addStretch()
            cards.addWidget(card, 0, column)
        layout.addLayout(cards)
        layout.addStretch()
        return scroll

    def refresh_overview(self) -> None:
        game = self.selected_game
        self.overview_game_name.setText(game.name)
        genres = " · ".join(game.genres[:3]) or "Uncategorized"
        self.overview_game_meta.setText(
            f"{genres}  •  {money(game.price_usd)}  •  {percent(game.review_score)} review score"
        )
        _clear(self.overview_metrics)
        values = (
            (
                "Estimated owners",
                owner_range(game.owners_low, game.owners_high),
                "Public catalogue estimate",
            ),
            ("Peak CCU", compact_number(game.peak_ccu), "Steam concurrency signal"),
            ("Reviews", compact_number(game.total_reviews), "Public review volume"),
            ("Tags", str(len(game.tags)), ", ".join(game.tags[:3]) or "No tags"),
        )
        for i, data in enumerate(values):
            self.overview_metrics.addWidget(metric_card(*data), 0, i)

    # Player ---------------------------------------------------------------
    def _build_player(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(
            layout,
            "PLAYER MODE",
            "Find your next game with reasons, not hype.",
            "Search a seed game, tune the price/platform filters, then compare explainable matches.",
        )

        controls = QFrame()
        controls.setObjectName("card")
        grid = QGridLayout(controls)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(10)
        self.player_search = QLineEdit()
        self.player_search.setPlaceholderText("Search Steam catalogue…")
        self.player_search.returnPressed.connect(self.search_player_games)
        search_button = QPushButton("Search")
        search_button.setObjectName("primaryButton")
        search_button.clicked.connect(self.search_player_games)
        self.player_seed = self._game_selector(self._player_seed_changed)
        self.player_os = QComboBox()
        self.player_os.addItems(["Any platform", "Windows", "macOS", "Linux"])
        self.player_price = QDoubleSpinBox()
        self.player_price.setRange(0, 200)
        self.player_price.setValue(60)
        self.player_price.setPrefix("$")
        self.player_price.setSuffix(" max")
        self.player_mode = QComboBox()
        self.player_mode.addItem("Best matches", "best_matches")
        self.player_mode.addItem("Hidden gems", "hidden_gems")
        refresh = QPushButton("Generate recommendations")
        refresh.setObjectName("secondaryButton")
        refresh.clicked.connect(self.refresh_player_recommendations)
        grid.addWidget(self.player_search, 0, 0, 1, 3)
        grid.addWidget(search_button, 0, 3)
        grid.addWidget(self.player_seed, 1, 0)
        grid.addWidget(self.player_os, 1, 1)
        grid.addWidget(self.player_price, 1, 2)
        grid.addWidget(self.player_mode, 1, 3)
        grid.addWidget(refresh, 2, 0, 1, 4)
        layout.addWidget(controls)

        self.player_search_results = QComboBox()
        self.player_search_results.setVisible(False)
        self.player_search_results.currentIndexChanged.connect(
            self._search_result_selected
        )
        layout.addWidget(self.player_search_results)
        layout.addWidget(
            section_header(
                "Recommended for this seed",
                "Scores combine catalogue similarity, preference fit, reviews, price and platform support.",
            )
        )
        self.player_table = QTableWidget(0, 6)
        self.player_table.setHorizontalHeaderLabels(
            ["Game", "Match", "Price", "Reviews", "Year", "Why it fits"]
        )
        self.player_table.horizontalHeader().setStretchLastSection(True)
        self.player_table.setAlternatingRowColors(True)
        self.player_table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
        self.player_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.player_table.doubleClicked.connect(self.open_selected_store)
        layout.addWidget(self.player_table)
        self.refresh_player_recommendations()
        return scroll

    def _player_seed_changed(self, app_id: int) -> None:
        self._set_selected_game(app_id)
        self.refresh_player_recommendations()

    def search_player_games(self) -> None:
        results = self.catalog.search_games(self.player_search.text(), limit=25)
        self.player_search_results.blockSignals(True)
        self.player_search_results.clear()
        for game in results:
            self.player_search_results.addItem(
                f"{game.name} · {money(game.price_usd)} · {percent(game.review_score)}",
                game.steam_app_id,
            )
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
            self.player_seed.addItem(game.name, app_id)
            existing = self.player_seed.count() - 1
        self.player_seed.setCurrentIndex(existing)

    def refresh_player_recommendations(self) -> None:
        app_id = (
            int(self.player_seed.currentData())
            if self.player_seed.currentData() is not None
            else self.selected_game.steam_app_id
        )
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
            values = (
                item.name,
                f"{item.match_score}/100",
                money(item.price_usd),
                percent(item.review_score),
                item.release_year or "—",
                reason,
            )
            for column, value in enumerate(values):
                self.player_table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )
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
        self._page_title(
            layout,
            "STREAMER MODE",
            "Find games worth streaming from your Steam interests.",
            "Analyze a public Steam profile for preference fit, then combine it with GamePulse activity and historical signals. Twitch is optional enrichment, never a requirement.",
        )

        profile = QFrame()
        profile.setObjectName("hero")
        profile_box = QVBoxLayout(profile)
        profile_box.setContentsMargins(20, 18, 20, 18)
        profile_box.setSpacing(8)
        profile_box.addWidget(_label("STEAM PROFILE", "eyebrow"))
        profile_row = QHBoxLayout()
        self.streamer_profile_url = QLineEdit()
        self.streamer_profile_url.setPlaceholderText("https://steamcommunity.com/id/example/")
        self.streamer_profile_url.returnPressed.connect(self.analyze_streamer_profile)
        analyze_profile = QPushButton("Analyze My Steam Profile")
        analyze_profile.setObjectName("primaryButton")
        analyze_profile.clicked.connect(self.analyze_streamer_profile)
        self.streamer_analyze_button = analyze_profile
        profile_row.addWidget(self.streamer_profile_url, 1)
        profile_row.addWidget(analyze_profile)
        profile_box.addLayout(profile_row)
        self.streamer_profile_status = _label(
            "Steam public data is built in. Your library must be visible to analyze it.",
            "muted",
            word_wrap=True,
        )
        profile_box.addWidget(self.streamer_profile_status)
        self.streamer_interests = _label(
            "Your strongest interests  ·  Add a profile or use the local signals below.",
            "pageSubtitle",
            word_wrap=True,
        )
        profile_box.addWidget(self.streamer_interests)
        layout.addWidget(profile)

        layout.addWidget(
            section_header(
                "Recommended games to stream",
                "Recommendations combine your inferred Steam preferences with local catalogue fit. Popularity and trend labels remain source-labelled.",
            )
        )
        self.streamer_profile_table = QTableWidget(0, 5)
        self.streamer_profile_table.setHorizontalHeaderLabels(
            ["Game", "Fit", "Popularity", "Trend", "Why it fits"]
        )
        self.streamer_profile_table.horizontalHeader().setStretchLastSection(True)
        self.streamer_profile_table.setAlternatingRowColors(True)
        self.streamer_profile_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.streamer_profile_table)

        controls = QFrame()
        controls.setObjectName("card")
        row = QHBoxLayout(controls)
        row.setContentsMargins(16, 16, 16, 16)
        self.streamer_tier = QComboBox()
        self.streamer_tier.addItems(["Emerging", "Mid-size", "Large"])
        self.streamer_strategy = QComboBox()
        self.streamer_strategy.addItems(["Balanced", "Reach", "Growth"])
        refresh = QPushButton("Refresh opportunity signals")
        refresh.setObjectName("primaryButton")
        refresh.clicked.connect(self.refresh_streamer_with_external_data)
        row.addWidget(_label("Creator size", "muted"))
        row.addWidget(self.streamer_tier)
        row.addWidget(_label("Strategy", "muted"))
        row.addWidget(self.streamer_strategy)
        row.addWidget(refresh)
        row.addStretch()
        layout.addWidget(controls)

        self.streamer_source = _label("", "muted", word_wrap=True)
        layout.addWidget(self.streamer_source)
        self.streamer_external_source = _label(
            "TwitchTracker data is available on demand for the selected focus game.",
            "muted",
            word_wrap=True,
        )
        layout.addWidget(self.streamer_external_source)
        self.streamer_metrics = QGridLayout()
        self.streamer_metrics.setSpacing(12)
        layout.addLayout(self.streamer_metrics)

        self.streamer_table = QTableWidget(0, 7)
        self.streamer_table.setHorizontalHeaderLabels(
            ["Game", "Score", "Activity", "Metric", "Growth", "Competition", "Signal"]
        )
        self.streamer_table.horizontalHeader().setStretchLastSection(True)
        self.streamer_table.setAlternatingRowColors(True)
        self.streamer_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self.streamer_table)
        return scroll

    def analyze_streamer_profile(self) -> None:
        profile = self.streamer_profile_url.text().strip()
        if not profile:
            self.streamer_profile_status.setText(
                "Enter a public Steam Community profile URL, or continue with local GamePulse signals."
            )
            return

        try:
            steam_id = self.steam.resolve_profile(profile)
            library = self.steam.get_library(steam_id)
            preferences = infer_preferences(library, self.catalog)
        except ValueError as exc:
            self.streamer_profile_status.setText(f"Steam profile URL needs attention: {exc}")
            self.streamer_interests.setText(
                "Your strongest interests  ·  Manual preferences remain available below."
            )
            self.streamer_profile_table.setRowCount(0)
            return
        except SteamProviderError as exc:
            message = str(exc)
            if any(token in message.casefold() for token in ("private", "publicly", "game details")):
                message = (
                    "Your Steam game library is not publicly available. "
                    "Make your game details public or select your preferences manually."
                )
            self.streamer_profile_status.setText(message)
            self.streamer_interests.setText(
                "Your strongest interests  ·  Manual preferences remain available below."
            )
            self.streamer_profile_table.setRowCount(0)
            return

        self.streamer_library = library
        self.streamer_preferences = preferences
        self.streamer_profile_status.setText(
            f"Steam profile analyzed  ·  {len(library.games):,} public games  ·  {library.source_name}"
        )
        interests = [
            *(value.title() for value in preferences.preferred_genres[:4]),
            *(value.title() for value in preferences.preferred_tags[:6]),
        ]
        self.streamer_interests.setText(
            "Your strongest interests  ·  " + ("  ·  ".join(interests) if interests else "Not enough catalogue matches yet")
        )
        known_ids = set()
        seed_id = self.selected_game.steam_app_id
        best_playtime = -1.0
        for item in library.games:
            try:
                app_id = int(item.get("appid"))
                self.catalog.get_game(app_id)
            except (AttributeError, TypeError, ValueError, KeyError):
                continue
            known_ids.add(app_id)
            try:
                playtime = float(item.get("playtime_forever") or 0)
            except (TypeError, ValueError):
                playtime = 0.0
            if playtime > best_playtime:
                best_playtime = playtime
                seed_id = app_id

        recommendations = self.recommendations.recommend_similar(
            seed_id,
            preferences,
            excluded_app_ids=known_ids,
            limit=12,
        )
        self.streamer_profile_table.setRowCount(len(recommendations))
        for row_index, item in enumerate(recommendations):
            popularity = owner_range(item.owners_low, item.owners_high)
            trend = "Local catalogue signal"
            values = (
                item.name,
                f"{item.match_score}/100",
                popularity,
                trend,
                " Â· ".join(item.reasons[:2]) if item.reasons else item.score_band,
            )
            for column, value in enumerate(values):
                self.streamer_profile_table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.streamer_profile_table.resizeColumnsToContents()

    def refresh_streamer(self) -> None:
        try:
            snapshot = self.signals.get_game_trends()
            profile = StreamerProfile(
                channel_size_tier=self.streamer_tier.currentText().casefold(),
                strategy=self.streamer_strategy.currentText().casefold(),
            )
            opportunities = score_game_opportunities(snapshot, profile)
        except Exception as exc:
            self.streamer_source.setText(f"Could not load game signals: {exc}")
            self.streamer_table.setRowCount(0)
            return

        freshness = evaluate_snapshot_freshness(snapshot)
        observed = snapshot.observed_at or "Unavailable"
        self.streamer_source.setText(
            f"Source · {snapshot.mode} · {snapshot.source_name}   |   "
            f"Observed · {observed}   |   Freshness · {freshness.label}   |   "
            f"Confidence · {snapshot.confidence or 'unknown'}"
        )

        _clear(self.streamer_metrics)
        top = opportunities[0] if opportunities else None
        if top is None:
            competition_value = "Unavailable"
            competition_detail = "No opportunity signals"
        elif top.competition_value is None:
            competition_value = "Unavailable"
            competition_detail = "Excluded from scoring; not treated as zero"
        else:
            competition_value = compact_number(top.competition_value)
            competition_detail = competition_metric_label(top.competition_metric)

        metrics = (
            (
                "Games observed",
                str(len(opportunities)),
                "Source-neutral opportunity signals",
            ),
            (
                "Top opportunity",
                top.name if top else "—",
                top.score_band if top else "No signal",
            ),
            (
                "Top score",
                f"{top.score * 100:.0f}/100" if top else "—",
                "Available weights are renormalized",
            ),
            ("Competition", competition_value, competition_detail),
        )
        for i, data in enumerate(metrics):
            self.streamer_metrics.addWidget(metric_card(*data), 0, i)

        shown = opportunities[:30]
        self.streamer_table.setRowCount(len(shown))
        for row_index, item in enumerate(shown):
            competition = (
                "Unavailable"
                if item.competition_value is None
                else f"{compact_number(item.competition_value)} {competition_metric_label(item.competition_metric)}"
            )
            values = (
                item.name,
                f"{item.score * 100:.0f}",
                _signal_value(item.audience_value),
                audience_metric_label(item.audience_metric),
                percent(item.components.growth),
                competition,
                " · ".join(item.reasons[:2]) if item.reasons else item.score_band,
            )
            for column, value in enumerate(values):
                self.streamer_table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )
        self.streamer_table.resizeColumnsToContents()

    def refresh_streamer_with_external_data(self) -> None:
        self.refresh_streamer()
        self.refresh_external_estimates()

    # Developer ------------------------------------------------------------
    def _build_developer(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(
            layout,
            "DEVELOPER MODE",
            "Decide what to build with market evidence.",
            "Explore trends, market gaps, game-level intelligence, competitor patterns, review themes and optional creator promotion from the same local data.",
        )

        top = QHBoxLayout()
        self.developer_section = QComboBox()
        self.developer_section.addItems(
            [
                "Overview",
                "Market Trends",
                "Market Gaps",
                "Game Analysis",
                "Competitors",
                "Review Intelligence",
                "Promotion",
            ]
        )
        self.developer_section.currentIndexChanged.connect(
            lambda _: self.refresh_developer(background=True)
        )
        self.developer_game = self._game_selector(self._developer_game_changed)
        self.developer_creator_tier = QComboBox()
        self.developer_creator_tier.addItem("Any creator size", None)
        self.developer_creator_tier.addItem("Emerging", "emerging")
        self.developer_creator_tier.addItem("Mid-size", "mid-size")
        self.developer_creator_tier.addItem("Large", "large")
        self.developer_creator_tier.currentIndexChanged.connect(
            lambda _: self.refresh_developer(background=True)
        )
        top.addWidget(_label("Developer view", "muted"))
        top.addWidget(self.developer_section)
        top.addWidget(_label("Focus game", "muted"))
        top.addWidget(self.developer_game, 1)
        top.addWidget(_label("Creator size", "muted"))
        top.addWidget(self.developer_creator_tier)
        refresh_external = QPushButton("Refresh public estimates")
        refresh_external.setObjectName("primaryButton")
        refresh_external.clicked.connect(self.refresh_external_estimates)
        top.addWidget(refresh_external)
        top.addStretch()
        layout.addLayout(top)

        self.developer_metrics = QGridLayout()
        self.developer_metrics.setSpacing(12)
        layout.addLayout(self.developer_metrics)
        self.developer_estimate_source = _label(
            "SteamSpy ownership estimates and TwitchTracker category metrics load only when you refresh them.",
            "muted",
            word_wrap=True,
        )
        layout.addWidget(self.developer_estimate_source)

        layout.addWidget(
            section_header(
                "Market trends",
                "Scores are derived from review volume, recent review momentum, ownership/player signals and relative catalogue crowding.",
            )
        )
        self.developer_trend_table = QTableWidget(0, 5)
        self.developer_trend_table.setHorizontalHeaderLabels(
            ["Game signal", "Score", "Demand", "Momentum", "Evidence"]
        )
        self.developer_trend_table.horizontalHeader().setStretchLastSection(True)
        self.developer_trend_table.setAlternatingRowColors(True)
        self.developer_trend_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.developer_trend_table)

        layout.addWidget(
            section_header(
                "Market gaps · what should I build next?",
                "Opportunity is directional: higher demand and momentum with lower relative competition/saturation. It is not a sales forecast.",
            )
        )
        self.developer_opportunity_table = QTableWidget(0, 5)
        self.developer_opportunity_table.setHorizontalHeaderLabels(
            ["Segment", "Opportunity", "Demand", "Competition", "Why it is interesting"]
        )
        self.developer_opportunity_table.horizontalHeader().setStretchLastSection(True)
        self.developer_opportunity_table.setAlternatingRowColors(True)
        self.developer_opportunity_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.developer_opportunity_table)

        self.developer_summary = QFrame()
        self.developer_summary.setObjectName("hero")
        self.developer_summary_box = QVBoxLayout(self.developer_summary)
        self.developer_summary_box.setContentsMargins(22, 20, 22, 20)
        layout.addWidget(self.developer_summary)

        layout.addWidget(
            section_header(
                "Review intelligence",
                "Deterministic topic signals show what players praise and complain about; percentages use the matching polarity subset as their denominator.",
            )
        )
        self.developer_review_intelligence = _label("", "muted", word_wrap=True)
        layout.addWidget(self.developer_review_intelligence)

        layout.addWidget(
            section_header(
                "Recommended creators",
                "Creator fit uses directory, creator-submitted, imported and optional live provider records with explicit provenance.",
            )
        )
        self.developer_creator_source = _label("", "muted", word_wrap=True)
        layout.addWidget(self.developer_creator_source)
        self.developer_creator_table = QTableWidget(0, 6)
        self.developer_creator_table.setHorizontalHeaderLabels(
            ["Creator", "Fit", "Platform", "Audience", "Source", "Why"]
        )
        self.developer_creator_table.horizontalHeader().setStretchLastSection(True)
        self.developer_creator_table.setAlternatingRowColors(True)
        self.developer_creator_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self.developer_creator_table)

        layout.addWidget(
            section_header(
                "Comparable games",
                "Ranked by overlapping tags/genres and review volume.",
            )
        )
        self.developer_table = QTableWidget(0, 5)
        self.developer_table.setHorizontalHeaderLabels(
            ["Game", "Overlap", "Price", "Review score", "Owners"]
        )
        self.developer_table.horizontalHeader().setStretchLastSection(True)
        self.developer_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        layout.addWidget(self.developer_table)
        return scroll

    def _developer_game_changed(self, app_id: int) -> None:
        self._set_selected_game(app_id)
        if self.external_estimate_app_id != app_id:
            self.twitchtracker_summary = None
            self.steamspy_estimate = None
            self.external_estimate_app_id = None
            if hasattr(self, "streamer_external_source"):
                self.streamer_external_source.setText(
                    "TwitchTracker data is available on demand for the selected focus game."
                )
            if hasattr(self, "developer_estimate_source"):
                self.developer_estimate_source.setText(
                    "Refresh public estimates for the newly selected game."
                )
        self.refresh_developer(background=True)

    def refresh_external_estimates(self) -> None:
        if self.external_estimate_worker is not None and self.external_estimate_worker.isRunning():
            self.statusBar().showMessage("Public estimates are already refreshing…")
            return
        game = self.selected_game
        self.external_estimate_app_id = game.steam_app_id
        if hasattr(self, "streamer_external_source"):
            self.streamer_external_source.setText("Refreshing TwitchTracker and SteamSpy for the selected game…")
        if hasattr(self, "developer_estimate_source"):
            self.developer_estimate_source.setText("Refreshing TwitchTracker and SteamSpy for the selected game…")
        worker = _ExternalEstimateWorker(game.name, game.steam_app_id, self.settings.external_cache_path)
        worker.results_ready.connect(self._apply_external_estimates)
        worker.finished.connect(worker.deleteLater)
        self.external_estimate_worker = worker
        worker.start()

    def _apply_external_estimates(
        self,
        twitchtracker: TwitchTrackerSummary,
        steamspy: SteamSpyEstimate,
    ) -> None:
        if self.external_estimate_app_id != self.selected_game.steam_app_id:
            return
        self.twitchtracker_summary = twitchtracker
        self.steamspy_estimate = steamspy
        game = self.selected_game
        summary_parts = [
            f"TwitchTracker · {twitchtracker.source_name} · {twitchtracker.confidence}",
            f"Observed · {twitchtracker.observed_at}",
        ]
        if twitchtracker.viewer_count is not None:
            summary_parts.append(f"Audience · {compact_number(twitchtracker.viewer_count)}")
        elif twitchtracker.average_viewers is not None:
            summary_parts.append(f"Average audience · {compact_number(twitchtracker.average_viewers)}")
        if twitchtracker.peak_viewers is not None:
            summary_parts.append(f"Peak audience · {compact_number(twitchtracker.peak_viewers)}")
        if twitchtracker.channel_count is not None:
            summary_parts.append(f"Live channels · {compact_number(twitchtracker.channel_count)}")
        if twitchtracker.hours_watched is not None:
            summary_parts.append(f"Hours watched · {compact_number(twitchtracker.hours_watched)}")
        if twitchtracker.error:
            summary_parts.append(twitchtracker.caveat)
        self.streamer_external_source.setText("   |   ".join(summary_parts))

        comparables = self.catalog.comparable_games(game.steam_app_id, limit=8)
        peer_reviews = [game.total_reviews or 0, *(item.total_reviews or 0 for item in comparables)]
        prediction = predict_developer_outcome(
            DeveloperPredictionInput(
                steamspy_owners_low=steamspy.owners_low,
                steamspy_owners_high=steamspy.owners_high,
                selected_game_price_usd=game.price_usd,
                review_count=game.total_reviews,
                review_peer_max=max(peer_reviews) if peer_reviews else None,
            )
        )
        owner_text = owner_range(steamspy.owners_low, steamspy.owners_high)
        gross_text = (
            "Unavailable"
            if prediction.scenario_gross_usd is None
            else f"{money(prediction.scenario_gross_usd[0])}–{money(prediction.scenario_gross_usd[1])}"
        )
        net_text = (
            "Unavailable"
            if prediction.scenario_net_usd is None
            else f"{money(prediction.scenario_net_usd[0])}–{money(prediction.scenario_net_usd[1])}"
        )
        competition_text = (
            "Unavailable"
            if prediction.competition_index is None
            else f"{prediction.competition_index:.0f}/100"
        )
        self.developer_estimate_source.setText(
            "\n".join(
                (
                    f"SteamSpy owners · {owner_text} · {steamspy.confidence} · {steamspy.observed_at}",
                    "TwitchTracker audience · "
                    + (
                        compact_number(twitchtracker.viewer_count)
                        if twitchtracker.viewer_count is not None
                        else compact_number(twitchtracker.average_viewers)
                    )
                    + (f" · {compact_number(twitchtracker.channel_count)} live channels" if twitchtracker.channel_count is not None else ""),
                    f"Scenario gross · {gross_text}   |   Scenario post-fee net · {net_text}   |   Competition index · {competition_text}",
                    prediction.competition_explanation,
                    prediction.source_caveat,
                    twitchtracker.caveat,
                )
            )
        )
        self.statusBar().showMessage("Public estimates refreshed; values are source-labelled scenarios, not reported sales.")

    def _apply_developer_market_results(self, trends, opportunities) -> None:
        self.developer_trend_table.setRowCount(len(trends))
        for row_index, item in enumerate(trends):
            values = (
                item.name,
                f"{item.score}/100",
                f"{item.demand:.0%}",
                f"{item.momentum:.0%}",
                item.explanation[0] if item.explanation else "Observed catalogue signals",
            )
            for column, value in enumerate(values):
                self.developer_trend_table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.developer_trend_table.resizeColumnsToContents()

        shown_opportunities = tuple(opportunities)[:10]
        self.developer_opportunity_table.setRowCount(len(shown_opportunities))
        for row_index, item in enumerate(shown_opportunities):
            values = (
                f"{item.value} ({item.dimension})",
                f"{item.score}/100",
                f"{item.demand:.0%}",
                f"{item.competition:.0%}",
                item.explanation[0] if item.explanation else "Observed catalogue signals",
            )
            for column, value in enumerate(values):
                self.developer_opportunity_table.setItem(row_index, column, QTableWidgetItem(str(value)))
        self.developer_opportunity_table.resizeColumnsToContents()

    def _start_developer_market_worker(self) -> None:
        if self.developer_market_worker is not None and self.developer_market_worker.isRunning():
            return
        worker = _DeveloperMarketWorker(self.settings.database_path)
        worker.results_ready.connect(self._apply_developer_market_results)
        worker.finished.connect(worker.deleteLater)
        self.developer_market_worker = worker
        worker.start()

    def refresh_developer(self, *, background: bool = False) -> None:
        game = self.selected_game
        if hasattr(self, "developer_game"):
            idx = self.developer_game.findData(game.steam_app_id)
            if idx >= 0 and idx != self.developer_game.currentIndex():
                self.developer_game.blockSignals(True)
                self.developer_game.setCurrentIndex(idx)
                self.developer_game.blockSignals(False)

        snapshot = latest_market_snapshot(
            self.settings.database_path, game.steam_app_id
        ) or MarketSnapshot(
            game.steam_app_id,
            None,
            game.owners_low,
            game.owners_high,
            game.price_usd,
            game.total_reviews,
            game.peak_ccu,
            "Local prepared data",
            "Steam/Kaggle prepared snapshot",
            self.settings.processed_dir.name,
        )

        comparables = self.catalog.comparable_games(game.steam_app_id, limit=8)
        comparable_records = [
            {
                "name": item.name,
                "price_usd": item.price_usd,
                "review_score": item.review_score,
                "owners_high": item.owners_high,
            }
            for item in comparables
        ]
        market = analyze_market(snapshot, comparable_records)
        reviews = analyze_reviews(self.settings.database_path, game.steam_app_id)
        forecast = forecast_review_activity(
            daily_counts_for_game(self.settings.database_path, game.steam_app_id)
        )

        try:
            creator_snapshot = self.signals.get_creators(
                game_id=str(game.steam_app_id),
                game_name=game.name,
            )
            tier = (
                self.developer_creator_tier.currentData()
                if hasattr(self, "developer_creator_tier")
                else None
            )
            creator_fits = rank_creators(
                {
                    "name": game.name,
                    "genres": set(game.genres),
                    "tags": set(game.tags),
                },
                creator_snapshot.data,
                tier=tier,
            )
        except Exception as exc:
            creator_snapshot = None
            creator_fits = []
            self.developer_creator_source.setText(
                f"Creator sources unavailable: {exc}"
            )

        opportunity = analyze_developer_opportunity(
            snapshot,
            reviews,
            forecast,
            len(creator_fits),
            len(comparables),
            creator_scores=tuple(item.score for item in creator_fits),
        )

        if background:
            self.developer_trend_table.setRowCount(0)
            self.developer_opportunity_table.setRowCount(0)
            self._start_developer_market_worker()
        else:
            try:
                trends = self.intelligence.explore_trends(limit=8)
                opportunities = list(self.intelligence.genre_opportunities(limit=5))
                opportunities.extend(self.intelligence.tag_opportunities(limit=5))
                opportunities.sort(
                    key=lambda item: (-item.score, -item.demand, item.dimension, item.value.casefold())
                )
            except Exception:
                trends = ()
                opportunities = []
            self._apply_developer_market_results(trends, opportunities)

        praise = ", ".join(
            f"{topic.name.title()} {topic.percentage:.0%}"
            for topic in getattr(reviews, "praise_topics", ())[:5]
        ) or "No evidence-backed praise topics"
        complaints = ", ".join(
            f"{topic.name.title()} {topic.percentage:.0%}"
            for topic in getattr(reviews, "complaint_topics", ())[:5]
        ) or "No evidence-backed complaint topics"
        self.developer_review_intelligence.setText(
            f"WHAT PLAYERS PRAISE  ·  {praise}\n"
            f"WHAT PLAYERS DISLIKE  ·  {complaints}\n"
            f"Observed review rows  ·  {reviews.review_count:,}  ·  "
            "Topic percentages are shares of the positive or negative review subset, not sales or survey estimates."
        )

        _clear(self.developer_metrics)
        gross = (
            "—"
            if market.estimated_gross_low is None
            or market.estimated_gross_high is None
            else f"{compact_number(market.estimated_gross_low)}–{compact_number(market.estimated_gross_high)}"
        )
        creator_metric = (
            f"{creator_fits[0].score:.0f}/100"
            if creator_fits
            else "Unavailable"
        )
        creator_detail = (
            f"{creator_fits[0].creator_name} · {creator_fits[0].score_band}"
            if creator_fits
            else "No eligible creator evidence for this game"
        )
        metrics = (
            ("Opportunity", f"{opportunity.score:.0f}/100", opportunity.score_band),
            (
                "Owners",
                owner_range(snapshot.owners_low, snapshot.owners_high),
                "Public estimate",
            ),
            (
                "Creator fit",
                creator_metric,
                creator_detail,
            ),
            (
                "30-day reviews",
                f"{forecast.low:,}–{forecast.high:,}",
                f"Central estimate {forecast.expected:,}",
            ),
        )
        metrics = (*metrics, ("Estimated gross scenario", gross, "Owners × listed price; not reported Steam revenue"))
        for i, data in enumerate(metrics):
            self.developer_metrics.addWidget(metric_card(*data), 0, i)

        _clear(self.developer_summary_box)
        self.developer_summary_box.addWidget(_label("VALIDATION BRIEF", "eyebrow"))
        self.developer_summary_box.addWidget(_label(game.name, "pageTitle"))
        self.developer_summary_box.addWidget(
            _label(
                f"{reviews.review_count:,} reviews analyzed · {reviews.positive_ratio:.0%} recommended",
                "pageSubtitle",
            )
        )
        self.developer_summary_box.addWidget(
            _label(
                "Positive themes · "
                + (", ".join(reviews.positive_themes) or "Not enough data"),
                "muted",
                word_wrap=True,
            )
        )
        self.developer_summary_box.addWidget(
            _label(
                "Negative themes · "
                + (", ".join(reviews.negative_themes) or "Not enough data"),
                "muted",
                word_wrap=True,
            )
        )
        self.developer_summary_box.addWidget(
            _label(
                f"Market source · {snapshot.source_mode} · {snapshot.source_name} · {snapshot.observed_at}",
                "muted",
                word_wrap=True,
            )
        )
        self.developer_summary_box.addWidget(
            _label(
                "Limitations · Steam player activity is not Twitch viewership. "
                "Unavailable competition is excluded from scoring rather than represented as zero.",
                "muted",
                word_wrap=True,
            )
        )

        if creator_snapshot is not None:
            creator_freshness = evaluate_snapshot_freshness(creator_snapshot)
            self.developer_creator_source.setText(
                f"Source · {creator_snapshot.mode} · {creator_snapshot.source_name}   |   "
                f"Observed · {creator_snapshot.observed_at or 'Unavailable'}   |   "
                f"Freshness · {creator_freshness.label}   |   "
                f"Confidence · {creator_snapshot.confidence or 'unknown'}"
            )

        shown_creators = creator_fits[:12]
        self.developer_creator_table.setRowCount(len(shown_creators))
        for row_index, item in enumerate(shown_creators):
            values = (
                item.creator_name or item.streamer_id,
                f"{item.score:.0f}/100",
                item.platform,
                _creator_audience(item.audience_value, item.audience_metric),
                f"{item.source_mode} · {item.source_name}",
                " · ".join(item.reasons[:2]) if item.reasons else item.score_band,
            )
            for column, value in enumerate(values):
                self.developer_creator_table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )
        self.developer_creator_table.resizeColumnsToContents()

        self.developer_table.setRowCount(len(comparables))
        for row_index, item in enumerate(comparables):
            values = (
                item.name,
                str(item.comparable_overlap),
                money(item.price_usd),
                percent(item.review_score),
                owner_range(item.owners_low, item.owners_high),
            )
            for column, value in enumerate(values):
                self.developer_table.setItem(
                    row_index, column, QTableWidgetItem(str(value))
                )
        self.developer_table.resizeColumnsToContents()

    # Settings --------------------------------------------------------------
    def _build_settings(self) -> QScrollArea:
        scroll, _, layout = page_scroll()
        self._page_title(
            layout,
            "SETTINGS / INTEGRATIONS",
            "Keep the core workflow keyless.",
            "GamePulse uses Steam/public data and the local database by default. Optional provider credentials stay outside the main user flows.",
        )

        cards = QGridLayout()
        cards.setSpacing(12)
        integrations = (
            (
                "Steam public data",
                "Built in",
                "Public profile and catalogue analysis can run without a Steam Web API key.",
            ),
            (
                "GamePulse database",
                "Connected" if self.settings.database_path.exists() else "Unavailable",
                f"Read-only local SQLite asset · {self.settings.database_path.name}",
            ),
            (
                "Twitch Helix",
                "Enabled" if self.settings.twitch_enabled else "Optional / unavailable",
                "Live creator and audience enrichment; Streamer Mode continues without it.",
            ),
            (
                "TwitchTracker + SteamSpy",
                "On-demand",
                "Public category and ownership estimates refresh only on request and are cached locally for 24 hours.",
            ),
            (
                "Streams Charts",
                "Enabled" if self.settings.streamscharts_enabled else "Optional / unavailable",
                "Optional historical creator enrichment when configured.",
            ),
        )
        for index, (name, state, detail) in enumerate(integrations):
            cards.addWidget(metric_card(name, state, detail), index // 2, index % 2)
        layout.addLayout(cards)

        note = QFrame()
        note.setObjectName("accentCard")
        note_box = QVBoxLayout(note)
        note_box.setContentsMargins(18, 16, 18, 16)
        note_box.addWidget(_label("PRIVACY AND PROVENANCE", "eyebrow"))
        note_box.addWidget(
            _label(
                "API secrets are read from the local .env file only and are never shown in the main workflow or printed to logs. Public ownership, review and activity values are estimates or observations, not private Steam sales.",
                "muted",
                word_wrap=True,
            )
        )
        layout.addWidget(note)
        layout.addStretch()
        return scroll


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
        QMessageBox.critical(
            None,
            "GamePulse database missing",
            "The local prototype database was not found.\n\n"
            "Run scripts/build_prototype_database.py first, then launch GamePulse again.",
        )
        return 2
    try:
        window = GamePulseWindow(settings, Catalog(settings.database_path))
    except Exception as exc:
        QMessageBox.critical(None, "GamePulse could not start", str(exc))
        return 3
    window.show()
    return app.exec()
