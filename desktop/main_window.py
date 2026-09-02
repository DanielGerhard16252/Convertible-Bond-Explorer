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

from server.csv_provider import load_bond_data
from server.ai_interpreter import interpret_request_with_ai
from server.bql_compiler import compile_query

from shared.models import (
    BondSearchQuery,
    CreditRating,
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

        self.submit_button = QPushButton("Submit")
        self.submit_button.clicked.connect(self.submit_search)

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Search request"))
        layout.addWidget(self.request_input)
        layout.addWidget(self.interpret_button)

        search_controls = QHBoxLayout()
        search_controls.addWidget(self.rating_group)
        search_controls.addWidget(self.price_group)
        layout.addLayout(search_controls)
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
        except ValueError:
            QMessageBox.warning(
                self,
                "Invalid price",
                "Enter valid numbers for minimum and maximum price.",
            )
            return

        if minimum is not None and maximum is not None and minimum > maximum:
            QMessageBox.warning(
                self,
                "Invalid price range",
                "Minimum price cannot be greater than maximum price.",
            )
            return

        price_range = (
            PriceRange(minimum=minimum, maximum=maximum)
            if minimum is not None or maximum is not None
            else None
        )
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
            ]
        )

        self.submit_button.setEnabled(False)
        self.submit_button.setText("Submitting...")

        try:
            self.bql_query = compile_query(query)
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

        for search_filter in query.filters:
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
