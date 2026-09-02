from PySide6.QtWidgets import (
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QTableWidget, 
    QTableWidgetItem,
)

import pandas as pd

from server.csv_provider import load_bond_data
from server.ai_interpreter import interpret_request_with_ai
from server.bql_compiler import compile_query


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.results = pd.DataFrame()
        self.setWindowTitle("Convertible Bond Explorer")
        self.resize(900, 700)

        self.request_input = QPlainTextEdit()
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

        self.json_output = QPlainTextEdit()
        self.json_output.setReadOnly(True)

        self.bql_output = QPlainTextEdit()
        self.bql_output.setReadOnly(True)

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

        layout = QVBoxLayout()

        layout.addWidget(QLabel("Search request"))
        layout.addWidget(self.request_input)
        layout.addWidget(self.interpret_button)

        layout.addWidget(QLabel("Generated JSON"))
        layout.addWidget(self.json_output)

        layout.addWidget(QLabel("Generated BQL"))
        layout.addWidget(self.bql_output)

        layout.addWidget(QLabel("Search results"))
        layout.addWidget(self.results_table)

        layout.addWidget(QLabel("Export results to CSV"))
        layout.addWidget(self.csv_name)
        layout.addWidget(self.export_csv)

        container = QWidget()
        container.setLayout(layout)

        self.setCentralWidget(container)

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
            bql = compile_query(query)

            self.json_output.setPlainText(
                query.model_dump_json(indent=2)
            )
            self.bql_output.setPlainText(bql)
            results = load_bond_data(query)
            self.results = results
            self.display_results(results)

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