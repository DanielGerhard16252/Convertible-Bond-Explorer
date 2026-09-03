from PySide6.QtWidgets import (
    QComboBox,
    QAbstractItemView,
    QFrame,
    QGridLayout,
    QHeaderView,
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
    QTableWidgetItem,
    QGroupBox,
)
from PySide6.QtCore import QLocale, Qt, Signal
from PySide6.QtGui import (
    QDoubleValidator,
    QKeyEvent,
    QStandardItem,
    QStandardItemModel,
)

import pandas as pd
from datetime import date, datetime
from numbers import Real

from server.ai_interpreter import interpret_request_with_ai
from server.bql_compiler import compile_query
from server.csv_provider import load_bond_data

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


APP_STYLESHEET = """
QMainWindow, QWidget {
    background-color: #f3f6fb;
    color: #172033;
    font-family: "Segoe UI";
    font-size: 12px;
}

QLabel#pageTitle {
    color: #102a56;
    font-size: 21px;
    font-weight: 700;
}

QLabel#pageSubtitle, QLabel#mutedLabel {
    color: #64748b;
}

QLabel#pageSubtitle {
    font-size: 12px;
    margin-bottom: 2px;
}

QLabel#sectionLabel {
    color: #173c78;
    font-size: 13px;
    font-weight: 650;
}

QFrame#card {
    background-color: #ffffff;
    border: 1px solid #dce5f2;
    border-radius: 12px;
}

QGroupBox {
    background-color: #ffffff;
    border: 1px solid #dce5f2;
    border-radius: 9px;
    font-weight: 600;
    margin-top: 7px;
    padding: 8px 6px 5px 6px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 11px;
    padding: 0 5px;
    color: #334e75;
    background-color: #f3f6fb;
}

QLineEdit, QPlainTextEdit, QComboBox {
    background-color: #f8fafc;
    border: 1px solid #cbd7e6;
    border-radius: 7px;
    padding: 4px 7px;
    selection-background-color: #2f6fed;
    selection-color: #ffffff;
}

QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    background-color: #ffffff;
    border: 2px solid #4381ee;
}

QPushButton {
    min-height: 18px;
    background-color: #e8eef8;
    color: #214578;
    border: 1px solid #c9d7eb;
    border-radius: 7px;
    padding: 5px 12px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #dbe7f8;
    border-color: #9fb9df;
}

QPushButton:pressed {
    background-color: #c9daf3;
}

QPushButton:disabled {
    color: #94a3b8;
    background-color: #edf1f6;
    border-color: #dce3eb;
}

QPushButton#primaryButton {
    min-width: 130px;
    background-color: #2563d8;
    color: #ffffff;
    border-color: #2563d8;
}

QPushButton#primaryButton:hover {
    background-color: #1d55bf;
    border-color: #1d55bf;
}

QTableWidget {
    background-color: #ffffff;
    alternate-background-color: #f7f9fc;
    border: 1px solid #dce5f2;
    border-radius: 9px;
    gridline-color: transparent;
    selection-background-color: #dbeafe;
    selection-color: #153868;
    outline: none;
}

QTableWidget::item {
    padding: 4px 7px;
    border-bottom: 1px solid #edf2f7;
}

QHeaderView::section {
    background-color: #173c78;
    color: #ffffff;
    border: none;
    border-right: 1px solid #31558d;
    padding: 6px;
    font-weight: 600;
}

QScrollBar:vertical {
    background: #edf2f7;
    width: 11px;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #a9bad0;
    border-radius: 5px;
    min-height: 28px;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0;
}
"""


class CheckableComboBox(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setEditable(False)
        self.setPlaceholderText("Select credit ratings")
        self.setCurrentIndex(-1)
        self.view().pressed.connect(self.toggle_item)

    def toggle_item(self, index) -> None:
        item = self.model().itemFromIndex(index)
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(
            Qt.CheckState.Unchecked
            if checked
            else Qt.CheckState.Checked
        )
        self.setCurrentIndex(-1)


class RequestInput(QPlainTextEdit):
    submitted = Signal()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        is_enter = event.key() in (
            Qt.Key.Key_Return,
            Qt.Key.Key_Enter,
        )
        is_multiline = bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )

        if is_enter and not is_multiline:
            self.submitted.emit()
            event.accept()
            return

        super().keyPressEvent(event)


class SortableTableItem(QTableWidgetItem):
    def __init__(self, value) -> None:
        super().__init__(str(value))
        self.sort_value = self.normalized_sort_value(value)

    @staticmethod
    def normalized_sort_value(value) -> tuple[int, object]:
        if isinstance(value, Real) and not isinstance(value, bool):
            return (0, float(value))
        if isinstance(value, (date, datetime, pd.Timestamp)):
            return (1, pd.Timestamp(value).value)
        return (2, str(value).casefold())

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class ResultsWindow(QMainWindow):
    def __init__(self, dataframe: pd.DataFrame) -> None:
        super().__init__()
        self.setWindowTitle("Convertible Bond Search Results")
        self.resize(1200, 700)
        self.setStyleSheet(APP_STYLESHEET)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("Search results")
        title.setObjectName("pageTitle")
        count = len(dataframe)
        summary = QLabel(
            f"{count:,} {'result' if count == 1 else 'results'}"
        )
        summary.setObjectName("mutedLabel")

        table = QTableWidget()
        configure_results_table(table)
        populate_results_table(table, dataframe)

        layout.addWidget(title)
        layout.addWidget(summary)
        layout.addWidget(table, 1)
        self.setCentralWidget(container)


def configure_results_table(table: QTableWidget) -> None:
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setShowGrid(False)
    table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectRows
    )
    table.setSelectionMode(
        QAbstractItemView.SelectionMode.SingleSelection
    )
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.ResizeToContents
    )
    table.horizontalHeader().setStretchLastSection(True)


def populate_results_table(
    table: QTableWidget,
    dataframe: pd.DataFrame,
) -> None:
    table.setSortingEnabled(False)
    table.clear()
    table.setRowCount(len(dataframe))
    table.setColumnCount(len(dataframe.columns))
    table.setHorizontalHeaderLabels(
        [column.replace("_", " ").title() for column in dataframe.columns]
    )

    for row_number, row in dataframe.iterrows():
        for column_number, column in enumerate(dataframe.columns):
            table.setItem(
                row_number,
                column_number,
                SortableTableItem(row[column]),
            )

    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.results = pd.DataFrame()
        self.results_window: ResultsWindow | None = None
        self.bql_query = ""
        self.setWindowTitle("Convertible Bond Explorer")
        self.resize(1180, 800)
        self.setMinimumSize(900, 650)
        self.setStyleSheet(APP_STYLESHEET)

        self.request_input = RequestInput()
        self.request_input.setPlaceholderText(
            "Example: Show me BBB-rated convertible bonds"
        )
        self.request_input.setMaximumHeight(44)

        self.interpret_button = QPushButton(
            "Interpret request"
        )
        self.interpret_button.clicked.connect(
            self.interpret_request
        )
        self.request_input.submitted.connect(
            self.interpret_request
        )
        self.bql = QPlainTextEdit()
        self.bql.setReadOnly(True)
        self.bql.setMaximumHeight(58)
        self.bql.setPlaceholderText("BQL will appear after submitting a search")
        self.bql.setToolTip(
            "Generated for Bloomberg inspection; results currently come from CSV."
        )
        self.bql.setStyleSheet('font-family: Consolas, "Courier New";')

        self.results_table = QTableWidget()
        configure_results_table(self.results_table)

        self.open_results_button = QPushButton("Open in new window")
        self.open_results_button.setEnabled(False)
        self.open_results_button.clicked.connect(self.open_results_window)

        self.csv_name = QPlainTextEdit()
        self.csv_name.setPlaceholderText("Enter CSV file name")
        self.csv_name.setMaximumHeight(42)
        self.export_csv = QPushButton(
            "Export to CSV"
        )
        self.export_csv.clicked.connect(
            self.export_to_csv
        )

        self.rating_items: dict[CreditRating, QStandardItem] = {}
        self.rating_group = QGroupBox("Credit rating")
        self.rating_layout = QVBoxLayout()
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
        self.rating_layout.addWidget(self.rating_dropdown)

        self.rating_group.setLayout(self.rating_layout)

        self.price_group = QGroupBox("Price")
        self.price_layout = QHBoxLayout()
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

        self.price_layout.addWidget(QLabel("Min"))
        self.price_layout.addWidget(self.minimum_price)
        self.price_layout.addWidget(QLabel("Max"))
        self.price_layout.addWidget(self.maximum_price)
        self.price_group.setLayout(self.price_layout)

        self.coupon_group = QGroupBox("Coupon")
        self.coupon_layout = QHBoxLayout()
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

        self.coupon_layout.addWidget(QLabel("Min"))
        self.coupon_layout.addWidget(self.minimum_coupon)
        self.coupon_layout.addWidget(QLabel("Max"))
        self.coupon_layout.addWidget(self.maximum_coupon)
        self.coupon_group.setLayout(self.coupon_layout)

        self.issuer_group = QGroupBox("Issuer")
        self.issuer_layout = QHBoxLayout()
        self.issuer_input = QLineEdit()
        self.issuer_input.setPlaceholderText("Issuer name")
        self.issuer_layout.addWidget(self.issuer_input)
        self.issuer_group.setLayout(self.issuer_layout)

        self.maturity_group = QGroupBox("Maturity (YYYY-MM-DD)")
        self.maturity_layout = QHBoxLayout()
        self.minimum_maturity = QLineEdit()
        self.minimum_maturity.setPlaceholderText("Min")
        self.maximum_maturity = QLineEdit()
        self.maximum_maturity.setPlaceholderText("Max")
        self.maturity_layout.addWidget(self.minimum_maturity)
        self.maturity_layout.addWidget(self.maximum_maturity)
        self.maturity_group.setLayout(self.maturity_layout)

        self.currency_group = QGroupBox("Currency")
        self.currency_layout = QHBoxLayout()
        self.currency_input = QLineEdit()
        self.currency_input.setPlaceholderText("USD")
        self.currency_layout.addWidget(self.currency_input)
        self.currency_group.setLayout(self.currency_layout)

        self.universe_group = QGroupBox("Bond universe · BQL only")
        self.universe_layout = QHBoxLayout()
        self.universe_dropdown = QComboBox()
        self.universe_dropdown.addItem("Convertible", "convertible")
        self.universe_dropdown.addItem("High Yield", "high_yield")
        self.universe_dropdown.addItem(
            "Convertible or High Yield",
            "convertible_or_high_yield",
        )
        self.universe_layout.addWidget(self.universe_dropdown)
        self.universe_group.setLayout(self.universe_layout)

        self.country_group = QGroupBox("Country · BQL only")
        self.country_layout = QHBoxLayout()
        self.country_input = QLineEdit()
        self.country_input.setPlaceholderText("e.g. United States")
        self.country_layout.addWidget(self.country_input)
        self.country_group.setLayout(self.country_layout)

        self.amount_outstanding_group = QGroupBox(
            "Amount outstanding · USD MM · BQL only"
        )
        self.amount_outstanding_layout = QHBoxLayout()
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
        self.amount_outstanding_layout.addWidget(
            self.minimum_amount_outstanding
        )
        self.amount_outstanding_layout.addWidget(
            self.maximum_amount_outstanding
        )
        self.amount_outstanding_group.setLayout(
            self.amount_outstanding_layout
        )

        self.analytics_inputs = {}
        for key, title in (
            ("conversion_premium", "Conversion premium"),
            ("delta", "Delta"),
            ("yield_to_maturity", "Yield to maturity"),
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

        self.submit_button = QPushButton("Submit")
        self.submit_button.setObjectName("primaryButton")
        self.submit_button.clicked.connect(self.submit_search)

        layout = QVBoxLayout()
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(8)


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
        request_layout.setContentsMargins(12, 9, 12, 9)
        request_layout.setSpacing(6)
        request_layout.addWidget(self.section_label("AI assisted search"))
        request_row = QHBoxLayout()
        request_row.setSpacing(10)
        request_row.addWidget(self.request_input, 1)
        request_row.addWidget(self.interpret_button)
        request_layout.addLayout(request_row)
        layout.addWidget(request_card)

        layout.addWidget(self.section_label("Filters"))
        filter_grid = QGridLayout()
        filter_grid.setHorizontalSpacing(8)
        filter_grid.setVerticalSpacing(6)

        # Start with issuer identity and credit, move through bond terms,
        # then finish with convertible-specific analytics.
        filter_grid.addWidget(self.universe_group, 0, 0)
        filter_grid.addWidget(self.country_group, 0, 1)
        filter_grid.addWidget(self.currency_group, 0, 2)
        filter_grid.addWidget(self.amount_outstanding_group, 0, 3)
        filter_grid.addWidget(self.issuer_group, 1, 0)
        filter_grid.addWidget(self.rating_group, 1, 1)
        filter_grid.addWidget(self.maturity_group, 1, 2)
        filter_grid.addWidget(self.coupon_group, 1, 3)
        filter_grid.addWidget(self.price_group, 2, 0)
        for column, key in enumerate(
            ("conversion_premium", "delta", "yield_to_maturity")
        ):
            filter_grid.addWidget(self.analytics_inputs[key][0], 2, column + 1)
        for column in range(4):
            filter_grid.setColumnStretch(column, 1)
        layout.addLayout(filter_grid)

        submit_row = QHBoxLayout()
        submit_row.addStretch()
        submit_row.addWidget(self.submit_button)
        layout.addLayout(submit_row)

        layout.addWidget(self.section_label("Generated BQL"))
        layout.addWidget(self.bql)

        results_header = QHBoxLayout()
        results_header.addWidget(self.section_label("Search results"))
        results_header.addStretch()
        self.results_count = QLabel("No results yet")
        self.results_count.setObjectName("mutedLabel")
        results_header.addWidget(self.results_count)
        results_header.addWidget(self.open_results_button)
        layout.addLayout(results_header)
        layout.addWidget(self.results_table, 1)

        export_row = QHBoxLayout()
        export_row.addWidget(self.section_label("Export"))
        export_row.addWidget(self.csv_name, 1)
        export_row.addWidget(self.export_csv)
        layout.addLayout(export_row)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

    @staticmethod
    def section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("sectionLabel")
        return label

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
        self.rating_dropdown.setCurrentIndex(-1)
        self.rating_dropdown.setPlaceholderText(
            summary or "Select credit ratings"
        )

    def interpret_request(self) -> None:
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

        try:
            query = interpret_request_with_ai(request)
            self.display_query_in_controls(query)

        except Exception as error:
            QMessageBox.critical(
                self,
                "Interpretation failed",
                str(error),
            )

        finally:
            self.interpret_button.setEnabled(True)
            self.interpret_button.setText(
                "Interpret request"
            )

    def submit_search(self) -> None:
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
                "Enter valid numbers and YYYY-MM-DD maturity dates.",
            )
            return

        if minimum is not None and maximum is not None and minimum > maximum:
            QMessageBox.warning(
                self,
                "Invalid price range",
                "Minimum price cannot be greater than maximum price.",
            )
            return

        if (
            minimum_coupon is not None
            and maximum_coupon is not None
            and minimum_coupon > maximum_coupon
        ):
            QMessageBox.warning(
                self,
                "Invalid coupon range",
                "Minimum coupon cannot be greater than maximum coupon.",
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
        currency = self.currency_input.text().strip().upper() or None
        country_name = self.country_input.text().strip()
        try:
            country = self.country_to_iso_code(country_name)
        except ValueError as error:
            QMessageBox.warning(self, "Invalid country", str(error))
            return
        bond_universe = self.universe_dropdown.currentData()
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
            filters=[
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
                             operator=SearchOperator.EQUALS,
                             value=currency),
                SearchFilter(field=SearchField.CONVERSION_PREMIUM,
                             operator=SearchOperator.BETWEEN,
                             value=analytics_ranges["conversion_premium"]),
                SearchFilter(field=SearchField.DELTA,
                             operator=SearchOperator.BETWEEN,
                             value=analytics_ranges["delta"]),
                SearchFilter(field=SearchField.YIELD_TO_MATURITY,
                             operator=SearchOperator.BETWEEN,
                             value=analytics_ranges["yield_to_maturity"]),
                SearchFilter(field=SearchField.COUNTRY,
                             operator=SearchOperator.EQUALS,
                             value=country),
                SearchFilter(field=SearchField.BOND_UNIVERSE,
                             operator=SearchOperator.EQUALS,
                             value=bond_universe),
                SearchFilter(field=SearchField.AMOUNT_OUTSTANDING,
                             operator=SearchOperator.BETWEEN,
                             value=amount_outstanding_range),
            ]
        )

        self.submit_button.setEnabled(False)
        self.submit_button.setText("Submitting...")

        try:
            self.bql_query = compile_query(query)
            # Keep compiling the BQL for inspection/export, but temporarily
            # source search results from the local CSV instead of Bloomberg.
            self.bql.setPlainText(self.bql_query)
            results = load_bond_data(query)
            self.results = results
            self.display_results(results)
        except Exception as error:
            QMessageBox.critical(
                self,
                "Search failed",
                str(error),
            )
        finally:
            self.submit_button.setEnabled(True)
            self.submit_button.setText("Submit")

    @staticmethod
    def parse_price(value: str) -> float | None:
        value = value.strip()
        return float(value) if value else None

    @staticmethod
    def country_to_iso_code(value: str) -> str | None:
        value = value.strip()
        if not value:
            return None
        if len(value) == 2 and value.isalpha():
            return value.upper()

        normalized_value = value.casefold()
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

    @staticmethod
    def parse_date(value: str) -> date | None:
        value = value.strip()
        return date.fromisoformat(value) if value else None

    def display_results(self, dataframe) -> None:
        populate_results_table(self.results_table, dataframe)
        count = len(dataframe)
        self.results_count.setText(
            f"{count:,} {'result' if count == 1 else 'results'}"
        )
        self.open_results_button.setEnabled(True)

    def open_results_window(self) -> None:
        self.results_window = ResultsWindow(self.results)
        self.results_window.show()
        self.results_window.raise_()
        self.results_window.activateWindow()

    def export_to_csv(self) -> None:
        if self.results.empty:
            QMessageBox.warning(
                self,
                "No results to export",
                "There are no search results to export.",
            )
            return
        else:
            csv_name = self.csv_name.toPlainText().strip()

            if not csv_name:
                QMessageBox.warning(
                    self,
                    "Missing CSV name",
                    "Enter a name for the CSV file.",
                )
                return

            if not csv_name.lower().endswith(".csv"):
                csv_name += ".csv"

            if not csv_name.lower().startswith("data/"):
                csv_name = f"data/{csv_name}"

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
                    str(error),
                )

    def display_query_in_controls(
        self,
        query: BondSearchQuery,
    ) -> None:
        # Clear the previous selection.
        for item in self.rating_items.values():
            item.setCheckState(Qt.CheckState.Unchecked)
        self.minimum_price.clear()
        self.maximum_price.clear()
        self.minimum_coupon.clear()
        self.maximum_coupon.clear()
        self.issuer_input.clear()
        self.minimum_maturity.clear()
        self.maximum_maturity.clear()
        self.currency_input.clear()
        self.country_input.clear()
        self.universe_dropdown.setCurrentIndex(0)
        self.minimum_amount_outstanding.setText("50")
        self.maximum_amount_outstanding.clear()
        for _, minimum_input, maximum_input in self.analytics_inputs.values():
            minimum_input.clear()
            maximum_input.clear()

        for search_filter in query.filters:
            if search_filter.field == SearchField.BOND_UNIVERSE:
                index = self.universe_dropdown.findData(search_filter.value)
                if index >= 0:
                    self.universe_dropdown.setCurrentIndex(index)
                continue

            if search_filter.field == SearchField.AMOUNT_OUTSTANDING:
                value_range = search_filter.value
                if value_range is not None and not isinstance(value_range, list):
                    if value_range.minimum is not None:
                        self.minimum_amount_outstanding.setText(
                            f"{value_range.minimum:g}"
                        )
                    if value_range.maximum is not None:
                        self.maximum_amount_outstanding.setText(
                            f"{value_range.maximum:g}"
                        )
                continue

            if search_filter.field == SearchField.COUNTRY:
                if isinstance(search_filter.value, str):
                    self.country_input.setText(search_filter.value)
                continue

            if search_filter.field == SearchField.CURRENCY:
                if isinstance(search_filter.value, str):
                    self.currency_input.setText(search_filter.value)
                continue

            if search_filter.field == SearchField.MATURITY:
                value_range = search_filter.value
                if value_range is not None and not isinstance(value_range, list):
                    if value_range.minimum is not None:
                        self.minimum_maturity.setText(value_range.minimum.isoformat())
                    if value_range.maximum is not None:
                        self.maximum_maturity.setText(value_range.maximum.isoformat())
                continue

            analytics_key = {
                SearchField.CONVERSION_PREMIUM: "conversion_premium",
                SearchField.DELTA: "delta",
                SearchField.YIELD_TO_MATURITY: "yield_to_maturity",
            }.get(search_filter.field)
            if analytics_key is not None:
                value_range = search_filter.value
                if value_range is not None and not isinstance(value_range, list):
                    _, minimum_input, maximum_input = self.analytics_inputs[analytics_key]
                    if value_range.minimum is not None:
                        minimum_input.setText(f"{value_range.minimum:g}")
                    if value_range.maximum is not None:
                        maximum_input.setText(f"{value_range.maximum:g}")
                continue

            if search_filter.field == SearchField.ISSUER:
                if isinstance(search_filter.value, str):
                    self.issuer_input.setText(search_filter.value)
                continue

            if search_filter.field == SearchField.COUPON:
                coupon_range = search_filter.value
                if coupon_range is None or isinstance(coupon_range, list):
                    continue
                if coupon_range.minimum is not None:
                    self.minimum_coupon.setText(
                        f"{coupon_range.minimum:g}"
                    )
                if coupon_range.maximum is not None:
                    self.maximum_coupon.setText(
                        f"{coupon_range.maximum:g}"
                    )
                continue

            if search_filter.field == SearchField.PRICE:
                price_range = search_filter.value
                if not isinstance(price_range, PriceRange):
                    continue
                if price_range.minimum is not None:
                    self.minimum_price.setText(
                        f"{price_range.minimum:g}"
                    )
                if price_range.maximum is not None:
                    self.maximum_price.setText(
                        f"{price_range.maximum:g}"
                    )
                continue

            if search_filter.field != SearchField.CREDIT_RATING:
                continue

            selected_ratings = set(
                search_filter.value or []
            )

            for rating, item in (
                self.rating_items.items()
            ):
                item.setCheckState(
                    Qt.CheckState.Checked
                    if rating in selected_ratings
                    else Qt.CheckState.Unchecked
                )
