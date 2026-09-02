from PySide6.QtWidgets import (
    QComboBox,
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
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QDoubleValidator,
    QKeyEvent,
    QStandardItem,
    QStandardItemModel,
)

import pandas as pd
from datetime import date

from server.bloomberg_api import execute_bql
from server.ai_interpreter import interpret_request_with_ai
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

class CheckableComboBox(QComboBox):
    def __init__(self) -> None:
        super().__init__()
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select credit ratings")
        self.view().pressed.connect(self.toggle_item)

    def toggle_item(self, index) -> None:
        item = self.model().itemFromIndex(index)
        checked = item.checkState() == Qt.CheckState.Checked
        item.setCheckState(
            Qt.CheckState.Unchecked
            if checked
            else Qt.CheckState.Checked
        )


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


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.results = pd.DataFrame()
        self.bql_query = ""
        self.setWindowTitle("Convertible Bond Explorer")
        self.resize(900, 700)

        self.request_input = RequestInput()
        self.request_input.setPlaceholderText(
            "Example: Show me BBB-rated convertible bonds"
        )
        self.request_input.setMaximumHeight(100)

        self.interpret_button = QPushButton(
            "Interpret request"
        )
        self.interpret_button.clicked.connect(
            self.interpret_request
        )
        self.request_input.submitted.connect(
            self.interpret_request
        )

        self.results_table = QTableWidget()
        self.results_table.setAlternatingRowColors(True)
        self.results_table.setSortingEnabled(True)

        self.csv_name = QPlainTextEdit()
        self.csv_name.setPlaceholderText("Enter CSV file name")
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
        self.submit_button.clicked.connect(self.submit_search)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Search request"))
        layout.addWidget(self.request_input)
        layout.addWidget(self.interpret_button)

        search_controls = QHBoxLayout()
        search_controls.addWidget(self.rating_group)
        search_controls.addWidget(self.price_group)
        search_controls.addWidget(self.coupon_group)
        search_controls.addWidget(self.issuer_group)
        layout.addLayout(search_controls)
        analytics_controls = QHBoxLayout()
        analytics_controls.addWidget(self.maturity_group)
        analytics_controls.addWidget(self.currency_group)
        for group, _, _ in self.analytics_inputs.values():
            analytics_controls.addWidget(group)
        layout.addLayout(analytics_controls)
        layout.addWidget(self.submit_button)

        layout.addWidget(QLabel("Search results"))
        layout.addWidget(self.results_table)

        layout.addWidget(QLabel("Export results to CSV"))
        layout.addWidget(self.csv_name)
        layout.addWidget(self.export_csv)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

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
        self.rating_dropdown.lineEdit().setText(
            "All ratings" if len(selected) == len(self.rating_items)
            else ", ".join(selected)
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

        all_ranges = [
            ("price", minimum, maximum),
            ("coupon", minimum_coupon, maximum_coupon),
            ("maturity", minimum_maturity, maximum_maturity),
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
            ]
        )

        self.submit_button.setEnabled(False)
        self.submit_button.setText("Submitting...")

        try:
            self.bql_query = compile_query(query)
            bql_results = execute_bql(self.bql_query)
            results = pd.DataFrame(bql_results.to_dicts())
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
    def parse_date(value: str) -> date | None:
        value = value.strip()
        return date.fromisoformat(value) if value else None

    def display_results(self, dataframe) -> None:
        self.results_table.setSortingEnabled(False)

        self.results_table.clear()
        self.results_table.setRowCount(len(dataframe))
        self.results_table.setColumnCount(len(dataframe.columns))

        column_names = [
            column.replace("_", " ").title()
            for column in dataframe.columns
        ]

        self.results_table.setHorizontalHeaderLabels(
            column_names
        )

        for row_number, row in dataframe.iterrows():
            for column_number, column in enumerate(
                dataframe.columns
            ):
                value = row[column]

                item = QTableWidgetItem(str(value))

                self.results_table.setItem(
                    row_number,
                    column_number,
                    item,
                )

        self.results_table.resizeColumnsToContents()
        self.results_table.setSortingEnabled(True)

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
        for _, minimum_input, maximum_input in self.analytics_inputs.values():
            minimum_input.clear()
            maximum_input.clear()

        for search_filter in query.filters:
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
