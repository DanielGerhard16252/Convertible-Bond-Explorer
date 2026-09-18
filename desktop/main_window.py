from shared.errors import short_error
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTableWidget, 
    QGroupBox,
)
from PySide6.QtCore import QLocale, Qt, Slot, QThreadPool, QStandardPaths
from PySide6.QtGui import (
    QDoubleValidator,
    QStandardItem,
    QStandardItemModel,
)

import pandas as pd
from datetime import date, datetime

from server.ai_interpreter import interpret_request_with_ai
from desktop.background import BackgroundJob
from server.ai_analysis import run_post_analysis
from server.bql_search import search_bql
from server.bql_compiler import compile_query
from shared.models import (
    BondSearchQuery,
    CouponRange,
    CreditRating,
    DateRange,
    PriceRange,
    SearchField,
    SearchFilter,
    SearchOperator,
)


from desktop.analysis_window import AnalysisWindow
from desktop.styles import APP_STYLESHEET
from desktop.widgets import CheckableComboBox, RequestInput
from desktop.filter_controls import set_checked_items, set_range_inputs
from desktop.results import (
    ResultsWindow, configure_results_table, populate_results_table,
)
from shared.countries import EUROPE_COUNTRY_CODES
from shared.search_choices import categorical_filters, configured_options


def retrieve_search_results(query, include_benchmarks):
    """Retrieve live Bloomberg results without accessing UI widgets."""
    results = search_bql(query, include_benchmarks=include_benchmarks)
    results.attrs["bond_universe"] = query.universe
    results.attrs["include_benchmarks"] = include_benchmarks and query.universe == "convertible"
    return results


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.results = pd.DataFrame()
        self._interpret_job = None
        self._search_job = None
        self._analysis_job = None
        self._analysis_question = ""
        self._closing = False
        self.results_window: ResultsWindow | None = None
        self.analysis_window: AnalysisWindow | None = None
        self._analysis_windows = set()
        self.bql_query = ""
        self.post_analysis_request: str | None = None
        self.setWindowTitle("Convertible Bond Explorer")
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(APP_STYLESHEET)

        self.get_benchmarks = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Construct and connect the search controls."""
        self.request_input = RequestInput()
        self.request_input.setPlaceholderText(
            "Example: Show me BBB-rated convertible bonds"
        )
        self.request_input.setFixedHeight(40)

        self.interpret_button = QPushButton(
            "Interpret request"
        )
        self.interpret_button.clicked.connect(
            self.interpret_request
        )
        self.request_input.submitted.connect(
            self.interpret_request
        )
        self.post_analysis = RequestInput()
        self.post_analysis.submitted.connect(self.run_analysis)
        self.post_analysis.setFixedHeight(44)
        self.post_analysis.setPlaceholderText(
            "Enter post-analysis instructions or use AI assisted search"
        )
        self.post_analysis.setToolTip(
            "Edit the analysis instructions before running them on filtered results."
        )
        self.post_analysis.textChanged.connect(
            self.post_analysis_changed
        )
        self.run_analysis_button = QPushButton("Run analysis")
        self.run_analysis_button.setEnabled(False)
        self.run_analysis_button.clicked.connect(self.run_analysis)

        self.results_table = QTableWidget()
        configure_results_table(self.results_table)

        self.open_results_button = QPushButton("Open in new window")
        self.open_results_button.setEnabled(False)
        self.open_results_button.clicked.connect(self.open_results_window)

        self.export_csv = QPushButton(
            "Export to CSV"
        )
        self.export_csv.setObjectName("primaryButton")
        self.export_csv.clicked.connect(
            self.export_to_csv
        )

        self.rating_items: dict[CreditRating, QStandardItem] = {}
        self.rating_group = QGroupBox("Credit rating")
        rating_layout = QVBoxLayout()
        self.rating_dropdown = CheckableComboBox()
        self.rating_dropdown.activated.connect(
            self.update_rating_summary
        )
        self.rating_model = QStandardItemModel()
        self.rating_dropdown.setModel(self.rating_model)

        self.select_all_item = self.create_rating_item("Select all")
        self.rating_model.appendRow(self.select_all_item)

        for rating in CreditRating:
            item = self.create_rating_item(rating.value)
            self.rating_model.appendRow(item)
            self.rating_items[rating] = item

        self.rating_model.itemChanged.connect(
            self.rating_selection_changed
        )
        rating_layout.addWidget(self.rating_dropdown)
        self.rating_group.setLayout(rating_layout)

        self.price_group = QGroupBox("Price")
        price_layout = QHBoxLayout()
        self.minimum_price = QLineEdit()
        self.minimum_price.setPlaceholderText("Min")
        self.maximum_price = QLineEdit()
        self.maximum_price.setPlaceholderText("Max")

        price_validator = QDoubleValidator(0.0, float("inf"), 6, self)
        price_validator.setNotation(
            QDoubleValidator.Notation.StandardNotation
        )
        self.minimum_price.setValidator(price_validator)
        self.maximum_price.setValidator(price_validator)

        price_layout.addWidget(QLabel("Min"))
        price_layout.addWidget(self.minimum_price)
        price_layout.addWidget(QLabel("Max"))
        price_layout.addWidget(self.maximum_price)
        self.price_group.setLayout(price_layout)

        self.coupon_group = QGroupBox("Coupon")
        coupon_layout = QHBoxLayout()
        self.minimum_coupon = QLineEdit()
        self.minimum_coupon.setPlaceholderText("Min")
        self.maximum_coupon = QLineEdit()
        self.maximum_coupon.setPlaceholderText("Max")

        coupon_validator = QDoubleValidator(0.0, float("inf"), 6, self)
        coupon_validator.setNotation(
            QDoubleValidator.Notation.StandardNotation
        )
        self.minimum_coupon.setValidator(coupon_validator)
        self.maximum_coupon.setValidator(coupon_validator)

        coupon_layout.addWidget(QLabel("Min"))
        coupon_layout.addWidget(self.minimum_coupon)
        coupon_layout.addWidget(QLabel("Max"))
        coupon_layout.addWidget(self.maximum_coupon)
        self.coupon_group.setLayout(coupon_layout)

        self.issuer_group = QGroupBox("Issuer")
        issuer_layout = QHBoxLayout()
        self.issuer_input = QLineEdit()
        self.issuer_input.setPlaceholderText("Issuer name")
        issuer_layout.addWidget(self.issuer_input)
        self.issuer_group.setLayout(issuer_layout)
        self.isin_group = QGroupBox("ISIN")
        isin_layout = QHBoxLayout(self.isin_group)
        self.isin_input = QLineEdit()
        self.isin_input.setPlaceholderText("12-character ISIN")
        isin_layout.addWidget(self.isin_input)
        self.max_number_group = QGroupBox("Max number of bonds")
        max_number_layout = QHBoxLayout(self.max_number_group)
        self.max_number_input = QLineEdit("100")
        self.max_number_input.setPlaceholderText("No limit")
        max_number_layout.addWidget(self.max_number_input)

        self.maturity_group = QGroupBox("Maturity (MM-DD-YYYY)")
        maturity_layout = QHBoxLayout()
        self.minimum_maturity = QLineEdit()
        self.minimum_maturity.setPlaceholderText("Min")
        self.maximum_maturity = QLineEdit()
        self.maximum_maturity.setPlaceholderText("Max")
        maturity_layout.addWidget(self.minimum_maturity)
        maturity_layout.addWidget(self.maximum_maturity)
        self.maturity_group.setLayout(maturity_layout)

        self.currency_group = QGroupBox("Currency")
        currency_layout = QHBoxLayout()
        self.currency_input = QLineEdit()
        self.currency_input.setPlaceholderText("GBP, EUR, USD")
        currency_layout.addWidget(self.currency_input)
        self.currency_group.setLayout(currency_layout)

        self.universe_group = QGroupBox("Bond universe")
        universe_layout = QHBoxLayout()
        self.universe_dropdown = QComboBox()
        self.universe_dropdown.addItem("Convertible", "convertible")
        self.universe_dropdown.addItem("High Yield", "high_yield")
        self.universe_dropdown.setCurrentIndex(self.universe_dropdown.findData("high_yield"))
        universe_layout.addWidget(self.universe_dropdown)
        self.universe_group.setLayout(universe_layout)

        self.get_benchmarks_checkbox = QCheckBox(
            "Include benchmark options"
        )
        self.get_benchmarks_checkbox.toggled.connect(
            self.update_get_benchmarks
        )

        self.high_yield_type_group = QGroupBox("High Yield bond type")
        high_yield_type_layout = QHBoxLayout()
        asset_class_row = QHBoxLayout()
        self.asset_class_checkboxes = {}
        for asset_class in ("Corporates", "Governments"):
            checkbox = QCheckBox(asset_class)
            checkbox.setChecked(asset_class == "Corporates")
            asset_class_row.addWidget(checkbox)
            self.asset_class_checkboxes[asset_class] = checkbox
        high_yield_type_layout.addLayout(asset_class_row)
        self.high_yield_type_group.setLayout(high_yield_type_layout)

        self.country_group = QGroupBox("Country")
        country_layout = QHBoxLayout()
        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("e.g. France, Germany, GB")
        country_layout.addWidget(self.country_input)
        self.country_group.setLayout(country_layout)

        self.amount_outstanding_group = QGroupBox(
            "Amount outstanding · USD MM"
        )
        amount_outstanding_layout = QHBoxLayout()
        self.minimum_amount_outstanding = QLineEdit("50")
        self.minimum_amount_outstanding.setPlaceholderText("Min")
        self.maximum_amount_outstanding = QLineEdit()
        self.maximum_amount_outstanding.setPlaceholderText("Max")
        amount_validator = QDoubleValidator(0.0, float("inf"), 6, self)
        amount_validator.setNotation(
            QDoubleValidator.Notation.StandardNotation
        )
        self.minimum_amount_outstanding.setValidator(amount_validator)
        self.maximum_amount_outstanding.setValidator(amount_validator)
        amount_outstanding_layout.addWidget(
            self.minimum_amount_outstanding
        )
        amount_outstanding_layout.addWidget(
            self.maximum_amount_outstanding
        )
        self.amount_outstanding_group.setLayout(amount_outstanding_layout)

        self.categorical_groups = {}
        self.categorical_dropdowns = {}
        self.categorical_items = {}
        for field, config in categorical_filters().items():
            group = QGroupBox(config["label"])
            group_layout = QHBoxLayout(group)
            dropdown = CheckableComboBox()
            options = configured_options(field)
            dropdown.setPlaceholderText("All (no filter)" if options else "Options not configured")
            dropdown.setEnabled(bool(options))
            model = QStandardItemModel(dropdown)
            items = {}
            for option in options:
                item = QStandardItem(option)
                item.setCheckable(True)
                item.setCheckState(Qt.CheckState.Unchecked)
                model.appendRow(item)
                items[option] = item
            dropdown.setModel(model)
            dropdown.setCurrentIndex(-1)
            model.itemChanged.connect(
                lambda _item, field=field: self.update_categorical_summary(field)
            )
            group_layout.addWidget(dropdown)
            self.categorical_groups[field] = group
            self.categorical_dropdowns[field] = dropdown
            self.categorical_items[field] = items

        self.analytics_inputs = {}
        for key, title in (
            ("conversion_premium", "Conversion premium"),
            ("yield_to_maturity", "Yield to maturity"),
            ("yield_to_worst", "Yield to worst"),
        ):
            group = QGroupBox(title)
            group_layout = QHBoxLayout()
            minimum_input = QLineEdit()
            maximum_input = QLineEdit()
            minimum_input.setPlaceholderText("Min")
            maximum_input.setPlaceholderText("Max")
            validator = QDoubleValidator(-float("inf"), float("inf"), 6, self)
            minimum_input.setValidator(validator)
            maximum_input.setValidator(validator)
            group_layout.addWidget(minimum_input)
            group_layout.addWidget(maximum_input)
            group.setLayout(group_layout)
            self.analytics_inputs[key] = (group, minimum_input, maximum_input)
        self.universe_dropdown.currentIndexChanged.connect(
            self.update_universe_dependent_filters
        )
        self.update_universe_dependent_filters()

        self.submit_button = QPushButton("Submit")
        self.submit_button.setObjectName("primaryButton")
        self.submit_button.clicked.connect(self.submit_search)
        self.reset_filters_button = QPushButton("Reset filters")
        self.reset_filters_button.setToolTip(
            "Restore default filters (High Yield, minimum USD 50 MM outstanding)."
        )
        self.reset_filters_button.clicked.connect(self.reset_filters)

        layout = QVBoxLayout()
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(6)
        title = QLabel("Convertible Bond Explorer")
        title.setObjectName("pageTitle")
        subtitle = QLabel(
            "Screen the convertible universe using natural language or precise filters."
        )
        subtitle.setObjectName("pageSubtitle")
        layout.addWidget(title)
        layout.addWidget(subtitle)

        request_card = QFrame()
        request_card.setObjectName("card")
        request_layout = QVBoxLayout(request_card)
        request_layout.setContentsMargins(10, 6, 10, 6)
        request_layout.setSpacing(4)
        request_layout.addWidget(self.section_label("AI assisted search"))
        request_row = QHBoxLayout()
        request_row.setSpacing(10)
        request_row.addWidget(self.request_input, 1)
        request_row.addWidget(self.interpret_button)
        request_layout.addLayout(request_row)
        layout.addWidget(request_card)

        layout.addWidget(self.section_label("Filters"))
        filter_grid = QGridLayout()
        filter_grid.setHorizontalSpacing(7)
        filter_grid.setVerticalSpacing(4)

        # Read left to right: universe and classification, issuer and credit,
        # numeric terms, then convertible analytics and the result limit.
        filter_rows = (
            (self.universe_group, self.high_yield_type_group,
             self.categorical_groups["fi_bics_level_2"],
             self.country_group, self.currency_group),
            (self.issuer_group, self.isin_group, self.rating_group,
             self.categorical_groups["payment_rank"], self.maturity_group),
            (self.amount_outstanding_group, self.price_group, self.coupon_group,
             self.analytics_inputs["yield_to_maturity"][0],
             self.analytics_inputs["yield_to_worst"][0]),
            (self.analytics_inputs["conversion_premium"][0], self.max_number_group),
        )
        for row, groups in enumerate(filter_rows):
            for column, group in enumerate(groups):
                group.layout().setContentsMargins(6, 4, 6, 4)
                group.layout().setSpacing(4)
                filter_grid.addWidget(group, row, column)
        for column in range(5):
            filter_grid.setColumnStretch(column, 1)
        layout.addLayout(filter_grid)

        submit_row = QHBoxLayout()
        submit_row.addWidget(self.get_benchmarks_checkbox)
        submit_row.addStretch()
        submit_row.addWidget(self.reset_filters_button)
        submit_row.addWidget(self.submit_button)
        layout.addLayout(submit_row)

        self.results_count = QLabel("No results yet")
        self.results_count.setObjectName("mutedLabel")

        layout.addWidget(self.section_label("Search results"))
        layout.addWidget(self.results_table, 1)

        export_row = QHBoxLayout()
        export_row.addStretch()
        export_row.addWidget(self.results_count)
        export_row.addWidget(self.open_results_button)
        export_row.addWidget(self.export_csv)
        layout.addLayout(export_row)

        layout.addWidget(self.section_label("AI analysis"))
        analysis_row = QHBoxLayout()
        analysis_row.addWidget(self.post_analysis, 1)
        analysis_row.addWidget(self.run_analysis_button)
        layout.addLayout(analysis_row)

        container = QWidget()
        container.setObjectName("mainPage")
        container.setStyleSheet("""
            QWidget#mainPage QGroupBox {
                margin-top: 6px;
                padding: 4px 3px 3px 3px;
            }
            QWidget#mainPage QLineEdit, QWidget#mainPage QComboBox,
            QWidget#mainPage QPlainTextEdit {
                padding: 3px 6px;
            }
            QWidget#mainPage QPushButton {
                padding: 4px 10px;
            }
        """)
        container.setLayout(layout)

        self.setCentralWidget(container)

    @staticmethod
    def section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

    def reset_filters(self) -> None:
        self.display_query_in_controls(BondSearchQuery(
            filters=[], max_number=100, post_analysis=self.post_analysis.toPlainText(),
        ))
        self.get_benchmarks_checkbox.setChecked(False)

    def update_categorical_summary(self, field: str) -> None:
        selected = [label for label, item in self.categorical_items[field].items()
                    if item.checkState() == Qt.CheckState.Checked]
        dropdown = self.categorical_dropdowns[field]
        summary = ", ".join(selected) if selected else (
            "All (no filter)" if dropdown.isEnabled() else "Options not configured"
        )
        dropdown.setPlaceholderText(summary)
        dropdown.setToolTip(summary)
        dropdown.setCurrentIndex(-1)

    def update_universe_dependent_filters(
        self,
        _index: int | None = None,
    ) -> None:
        convertible_selected = (
            self.universe_dropdown.currentData() == "convertible"
        )
        high_yield_only = not convertible_selected

        if not convertible_selected:
            self.get_benchmarks_checkbox.setChecked(False)
        self.get_benchmarks_checkbox.setEnabled(convertible_selected)
        self.get_benchmarks_checkbox.setToolTip(
            "Available for convertible bonds only."
            if high_yield_only
            else ""
        )

        group, minimum_input, maximum_input = self.analytics_inputs[
            "conversion_premium"
        ]
        if high_yield_only:
            minimum_input.clear()
            maximum_input.clear()
        group.setEnabled(not high_yield_only)
        group.setToolTip(
            "Available for convertible universes only."
            if high_yield_only
            else ""
        )
        self.high_yield_type_group.setEnabled(high_yield_only)
        self.high_yield_type_group.setToolTip(
            "Applies to the High Yield branch only."
            if high_yield_only
            else "Convertible bonds are restricted to Corporates."
        )

    def update_get_benchmarks(self, checked: bool) -> None:
        self.get_benchmarks = checked

    def create_rating_item(self, text: str) -> QStandardItem:
        item = QStandardItem(text)
        item.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        item.setData(Qt.CheckState.Unchecked, Qt.ItemDataRole.CheckStateRole)
        return item

    def rating_selection_changed(self, changed_item: QStandardItem) -> None:
        self.rating_model.blockSignals(True)

        if changed_item is self.select_all_item:
            state = changed_item.checkState()
            for item in self.rating_items.values():
                item.setCheckState(state)
        else:
            all_selected = all(
                item.checkState() == Qt.CheckState.Checked
                for item in self.rating_items.values()
            )
            self.select_all_item.setCheckState(
                Qt.CheckState.Checked
                if all_selected
                else Qt.CheckState.Unchecked
            )

        self.rating_model.blockSignals(False)
        self.update_rating_summary()

    def update_rating_summary(self, _index: int | None = None) -> None:
        selected = [
            rating.value
            for rating, item in self.rating_items.items()
            if item.checkState() == Qt.CheckState.Checked
        ]
        summary = (
            "All ratings"
            if len(selected) == len(self.rating_items)
            else ", ".join(selected)
        )
        self.rating_dropdown.setCurrentIndex(0)
        self.rating_dropdown.setPlaceholderText(
            summary or "Select credit ratings"
        )

    def interpret_request(self) -> None:
        if self._interpret_job is not None or self._closing:
            return
        request = self.request_input.toPlainText().strip()

        if not request:
            QMessageBox.warning(
                self,
                "Missing request",
                "Enter a convertible-bond search request.",
            )
            return

        self.interpret_button.setEnabled(False)
        self.interpret_button.setText("Interpreting...")

        self._interpret_job = BackgroundJob(interpret_request_with_ai, request)
        self._interpret_job.signals.completed.connect(self._interpret_finished)
        QThreadPool.globalInstance().start(self._interpret_job)

    @Slot(object, object)
    def _interpret_finished(self, query, error) -> None:
        self._interpret_job = None
        if self._closing:
            return
        self.interpret_button.setEnabled(True)
        self.interpret_button.setText("Interpret request")
        if error is not None:
            QMessageBox.critical(
                self,
                "Interpretation failed",
                short_error(error),
            )

        else:
            self.display_query_in_controls(query)

    def query_from_controls(self) -> BondSearchQuery | None:
        try:
            return self._query_from_controls()
        except ValueError as error:
            QMessageBox.warning(self, "Invalid search filters", short_error(error))
            return None

    def _query_from_controls(self) -> BondSearchQuery | None:
        """Validate the search form and construct its typed query."""
        limit_text = self.max_number_input.text().strip()
        if limit_text and (not limit_text.isascii() or not limit_text.isdecimal()
                           or int(limit_text) <= 0):
            QMessageBox.warning(self, "Invalid maximum number of bonds",
                                "Enter a positive whole number or leave blank for no limit.")
            return None
        max_number = int(limit_text) if limit_text else None
        selected_ratings = [
            rating
            for rating, item in self.rating_items.items()
            if item.checkState() == Qt.CheckState.Checked
        ]
        try:
            minimum = self.parse_price(self.minimum_price.text())
            maximum = self.parse_price(self.maximum_price.text())
            minimum_coupon = self.parse_price(self.minimum_coupon.text())
            maximum_coupon = self.parse_price(self.maximum_coupon.text())
            minimum_amount_outstanding = self.parse_price(
                self.minimum_amount_outstanding.text()
            )
            maximum_amount_outstanding = self.parse_price(
                self.maximum_amount_outstanding.text()
            )
            analytics_values = {
                key: (self.parse_price(inputs[1].text()),
                      self.parse_price(inputs[2].text()))
                for key, inputs in self.analytics_inputs.items()
            }
            minimum_maturity = self.parse_date(self.minimum_maturity.text())
            maximum_maturity = self.parse_date(self.maximum_maturity.text())
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid range value",
                "Enter valid numbers and MM-DD-YYYY maturity dates.",
            )
            return

        price_range = (
            PriceRange(minimum=minimum, maximum=maximum)
            if minimum is not None or maximum is not None
            else None
        )
        coupon_range = (
            CouponRange(
                minimum=minimum_coupon,
                maximum=maximum_coupon,
            )
            if minimum_coupon is not None or maximum_coupon is not None
            else None
        )
        issuer = self.issuer_input.text().strip() or None
        try:
            isin_filter = SearchFilter(field=SearchField.ISIN,
                                       operator=SearchOperator.EQUALS,
                                       value=self.isin_input.text().strip() or None)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid ISIN", short_error(error))
            return
        currency = self.currency_input.text().strip().upper() or None
        try:
            currency = SearchFilter(field=SearchField.CURRENCY,
                                    operator=SearchOperator.IN, value=currency).value
        except ValueError as error:
            QMessageBox.warning(self, "Invalid currency", short_error(error))
            return
        country_name = self.country_input.text().strip()
        try:
            countries = self.countries_to_iso_codes(country_name)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid country", short_error(error))
            return
        bond_universe = self.universe_dropdown.currentData()
        asset_classes = [
            asset_class
            for asset_class, checkbox in self.asset_class_checkboxes.items()
            if checkbox.isChecked()
        ]
        if bond_universe != "convertible" and not asset_classes:
            QMessageBox.warning(
                self,
                "Missing asset class",
                "Select at least one High Yield asset class.",
            )
            return
        if bond_universe == "high_yield":
            analytics_values["conversion_premium"] = (None, None)
        maturity_range = (
            DateRange(minimum=minimum_maturity, maximum=maximum_maturity)
            if minimum_maturity is not None or maximum_maturity is not None
            else None
        )
        analytics_ranges = {
            key: (PriceRange(minimum=values[0], maximum=values[1])
                  if values[0] is not None or values[1] is not None else None)
            for key, values in analytics_values.items()
        }
        amount_outstanding_range = (
            PriceRange(
                minimum=minimum_amount_outstanding,
                maximum=maximum_amount_outstanding,
            )
            if minimum_amount_outstanding is not None
            or maximum_amount_outstanding is not None
            else None
        )

        all_ranges = [
            ("price", minimum, maximum),
            ("coupon", minimum_coupon, maximum_coupon),
            ("maturity", minimum_maturity, maximum_maturity),
            (
                "amount_outstanding",
                minimum_amount_outstanding,
                maximum_amount_outstanding,
            ),
            *[(key, values[0], values[1])
              for key, values in analytics_values.items()],
        ]
        if any(low is not None and high is not None and low > high
               for _, low, high in all_ranges):
            QMessageBox.warning(self, "Invalid range", "A minimum exceeds its maximum.")
            return
        query = BondSearchQuery(
            max_number=max_number,
            post_analysis=self.post_analysis_request,
            filters=[
                *[SearchFilter(
                    field=SearchField(field),
                    operator=SearchOperator.IN,
                    value=[label for label, item in items.items()
                           if item.checkState() == Qt.CheckState.Checked] or None,
                ) for field, items in self.categorical_items.items()],
                isin_filter,
                SearchFilter(
                    field=SearchField.CREDIT_RATING,
                    operator=SearchOperator.IN,
                    value=selected_ratings or None,
                ),
                SearchFilter(
                    field=SearchField.PRICE,
                    operator=SearchOperator.BETWEEN,
                    value=price_range,
                ),
                SearchFilter(
                    field=SearchField.COUPON,
                    operator=SearchOperator.BETWEEN,
                    value=coupon_range,
                ),
                SearchFilter(
                    field=SearchField.ISSUER,
                    operator=SearchOperator.EQUALS,
                    value=issuer,
                ),
                SearchFilter(field=SearchField.MATURITY,
                             operator=SearchOperator.BETWEEN,
                             value=maturity_range),
                SearchFilter(field=SearchField.CURRENCY,
                             operator=SearchOperator.IN,
                             value=currency),
                SearchFilter(field=SearchField.CONVERSION_PREMIUM,
                             operator=SearchOperator.BETWEEN,
                             value=analytics_ranges["conversion_premium"]),
                SearchFilter(field=SearchField.YIELD_TO_MATURITY,
                             operator=SearchOperator.BETWEEN,
                             value=analytics_ranges["yield_to_maturity"]),
                SearchFilter(field=SearchField.YIELD_TO_WORST,
                             operator=SearchOperator.BETWEEN,
                             value=analytics_ranges["yield_to_worst"]),
                SearchFilter(field=SearchField.COUNTRY,
                             operator=SearchOperator.IN,
                             value=countries),
                SearchFilter(field=SearchField.BOND_UNIVERSE,
                             operator=SearchOperator.EQUALS,
                             value=bond_universe),
                SearchFilter(field=SearchField.ASSET_CLASSES,
                             operator=SearchOperator.IN,
                             value=asset_classes),
                SearchFilter(field=SearchField.AMOUNT_OUTSTANDING,
                             operator=SearchOperator.BETWEEN,
                             value=amount_outstanding_range),
            ]
        )

        return query

    def submit_search(self) -> None:
        if self._search_job is not None or self._closing:
            return
        query = self.query_from_controls()
        if query is None:
            return
        try:
            self._pending_bql = compile_query(query)
        except Exception as error:
            QMessageBox.critical(self, "Search failed", short_error(error))
            return
        self._search_job = BackgroundJob(
            retrieve_search_results, query, self.get_benchmarks,
        )
        self._search_job.signals.completed.connect(self._search_finished)
        self.submit_button.setEnabled(False)
        self.submit_button.setText("Submitting...")
        QThreadPool.globalInstance().start(self._search_job)

    @Slot(object, object)
    def _search_finished(self, results, error) -> None:
        self._search_job = None
        if self._closing:
            return
        try:
            if error is not None:
                raise RuntimeError(error)
            self.display_results(results)
            self.results = results
            self.bql_query = self._pending_bql
            self.update_analysis_button()
            if results.empty:
                QMessageBox.warning(self, "No results", "No results")
        except Exception as error:
            QMessageBox.critical(self, "Search failed", short_error(error))
        finally:
            self.submit_button.setEnabled(True)
            self.submit_button.setText("Submit")

    @staticmethod
    def parse_price(value: str) -> float | None:
        value = value.strip()
        return float(value) if value else None

    @staticmethod
    def country_to_iso_code(value: str) -> str:
        normalized_value = value.strip().casefold()
        if len(normalized_value) == 2 and normalized_value.isalpha():
            return normalized_value.upper()
        for country in QLocale.Country:
            country_name = QLocale.territoryToString(country)
            country_code = QLocale.territoryToCode(country)
            if (
                country_code
                and country_name.casefold() == normalized_value
            ):
                return country_code.upper()

        raise ValueError(
            f"Unknown country '{value}'. Enter a country name or two-letter ISO code."
        )

    @classmethod
    def countries_to_iso_codes(cls, value: str) -> list[str] | None:
        entries = [entry.strip() for entry in value.split(",") if entry.strip()]
        if not entries:
            return None

        codes = []
        for entry in entries:
            entry_codes = (
                EUROPE_COUNTRY_CODES
                if entry.casefold() == "europe"
                else [cls.country_to_iso_code(entry)]
            )
            for code in entry_codes:
                if code not in codes:
                    codes.append(code)
        return codes

    @staticmethod
    def parse_date(value: str) -> date | None:
        value = value.strip()
        return datetime.strptime(value, "%m-%d-%Y").date() if value else None

    def display_results(self, dataframe) -> None:
        populate_results_table(self.results_table, dataframe)
        count = len(dataframe)
        self.results_count.setText(
            f"{count:,} {'result' if count == 1 else 'results'}"
        )
        self.open_results_button.setEnabled(not dataframe.empty)
        self.update_analysis_button()

    def open_results_window(self) -> None:
        self.results_window = ResultsWindow(self.results)
        self.results_window.show()
        self.results_window.raise_()
        self.results_window.activateWindow()

    def update_analysis_button(self) -> None:
        self.run_analysis_button.setEnabled(
            bool(self.post_analysis_request) and not self.results.empty
            and self._analysis_job is None
        )

    def post_analysis_changed(self) -> None:
        self.post_analysis_request = (
            self.post_analysis.toPlainText().strip() or None
        )
        self.update_analysis_button()

    def run_analysis(self) -> None:
        if self._analysis_job is not None or self._closing:
            return
        if not self.post_analysis_request or self.results.empty:
            return

        self.run_analysis_button.setEnabled(False)
        self.run_analysis_button.setText("Analysing...")
        self._analysis_question = self.post_analysis_request
        self._analysis_dataset = self.results.copy(deep=True)
        self._analysis_bql = self.bql_query
        self._analysis_job = BackgroundJob(
            run_post_analysis,
            self._analysis_question,
            self._analysis_dataset,
            self._analysis_bql,
        )
        self._analysis_job.signals.completed.connect(self._analysis_finished)
        QThreadPool.globalInstance().start(self._analysis_job)

    @Slot(object, object)
    def _analysis_finished(self, analysis, error) -> None:
        self._analysis_job = None
        if self._closing:
            return
        self.run_analysis_button.setText("Run analysis")
        self.update_analysis_button()
        if error is None:
            self.analysis_window = AnalysisWindow(
                question=self._analysis_question,
                result=analysis,
                dataset=self._analysis_dataset,
                bql_query=self._analysis_bql,
            )
            self._analysis_windows.add(self.analysis_window)
            self.analysis_window.closed.connect(self._analysis_windows.discard)
            self.analysis_window.show()
            self.analysis_window.raise_()
            self.analysis_window.activateWindow()
        else:
            QMessageBox.critical(
                self,
                "Analysis failed",
                short_error(error),
            )
        self._analysis_dataset = None
        self._analysis_bql = ""
        self._analysis_question = ""

    def closeEvent(self, event) -> None:
        # Let in-flight calls finish without opening windows or dialogs on close.
        self._closing = True
        super().closeEvent(event)

    def export_to_csv(self) -> None:
        if self.results.empty:
            QMessageBox.warning(
                self,
                "No results to export",
                "There are no search results to export.",
            )
            return
        downloads = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DownloadLocation)
        dialog = QFileDialog(self, "Export to CSV", downloads, "CSV files (*.csv)")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setDefaultSuffix("csv")
        dialog.selectFile("bond_results.csv")
        if dialog.exec() != QFileDialog.DialogCode.Accepted:
            return
        csv_name = dialog.selectedFiles()[0]

        try:
            self.results.to_csv(csv_name, index=False)
            QMessageBox.information(
                self,
                "Export successful",
                f"Search results exported to {csv_name}.",
            )
        except Exception as error:
            QMessageBox.critical(
                self,
                "Export failed",
                short_error(error),
            )

    def display_query_in_controls(
        self,
        query: BondSearchQuery,
    ) -> None:
        self.post_analysis.setPlainText(query.post_analysis or "")

        # Clear the previous selection.
        for items in self.categorical_items.values():
            for item in items.values():
                item.setCheckState(Qt.CheckState.Unchecked)
        for item in self.rating_items.values():
            item.setCheckState(Qt.CheckState.Unchecked)
        self.minimum_price.clear()
        self.maximum_price.clear()
        self.minimum_coupon.clear()
        self.maximum_coupon.clear()
        self.issuer_input.clear()
        self.isin_input.clear()
        self.max_number_input.setText(str(query.max_number) if query.max_number is not None else "")
        self.minimum_maturity.clear()
        self.maximum_maturity.clear()
        self.currency_input.clear()
        self.country_input.clear()
        self.universe_dropdown.setCurrentIndex(self.universe_dropdown.findData(query.universe))
        for asset_class, checkbox in self.asset_class_checkboxes.items():
            checkbox.setChecked(asset_class == "Corporates")
        self.minimum_amount_outstanding.setText("50")
        self.maximum_amount_outstanding.clear()
        for _, minimum_input, maximum_input in self.analytics_inputs.values():
            minimum_input.clear()
            maximum_input.clear()

        range_controls = {
            SearchField.PRICE: (self.minimum_price, self.maximum_price),
            SearchField.COUPON: (self.minimum_coupon, self.maximum_coupon),
            SearchField.AMOUNT_OUTSTANDING: (
                self.minimum_amount_outstanding, self.maximum_amount_outstanding),
            SearchField.MATURITY: (self.minimum_maturity, self.maximum_maturity),
            **{SearchField(key): (minimum, maximum)
               for key, (_, minimum, maximum) in self.analytics_inputs.items()},
        }
        text_controls = {
            SearchField.ISSUER: self.issuer_input,
            SearchField.ISIN: self.isin_input,
            SearchField.COUNTRY: self.country_input,
            SearchField.CURRENCY: self.currency_input,
        }
        for search_filter in query.filters:
            field, value = search_filter.field, search_filter.value
            if field.value in self.categorical_items:
                set_checked_items(self.categorical_items[field.value], value)
            elif field == SearchField.CREDIT_RATING:
                set_checked_items(self.rating_items, value)
            elif field == SearchField.BOND_UNIVERSE:
                index = self.universe_dropdown.findData(value)
                if index >= 0:
                    self.universe_dropdown.setCurrentIndex(index)
            elif field == SearchField.ASSET_CLASSES:
                for asset_class, checkbox in self.asset_class_checkboxes.items():
                    checkbox.setChecked(asset_class in (value or []))
            elif field in range_controls:
                set_range_inputs(*range_controls[field], value,
                                 date_values=field == SearchField.MATURITY)
            elif field in text_controls:
                if isinstance(value, list):
                    text_controls[field].setText(", ".join(value))
                elif isinstance(value, str):
                    text_controls[field].setText(value)

        self.update_universe_dependent_filters()
