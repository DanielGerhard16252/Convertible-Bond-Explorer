"""Result formatting, tables, and secondary windows."""

from datetime import date, datetime
from numbers import Real

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QMainWindow, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from desktop.result_formatting import (
    THREE_DECIMAL_COLUMNS, RESULT_COLUMN_LABELS, HIGH_YIELD_COLUMN_LABELS,
    BENCHMARK_COLUMN_LABELS, display_column_labels, select_display_columns,
    format_table_value,
)
from desktop.styles import APP_STYLESHEET
from desktop.bond_record import BondRecordWindow
from desktop.analysis_window import AnalysisWindow  # Backwards-compatible import.


class SortableTableItem(QTableWidgetItem):
    def __init__(self, value, display_value: str | None = None) -> None:
        super().__init__(display_value if display_value is not None else str(value))
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sort_value = self.normalized_sort_value(value)

    @staticmethod
    def normalized_sort_value(value) -> tuple[int, object]:
        if pd.isna(value):
            return (3, "")
        if isinstance(value, Real) and not isinstance(value, bool):
            return (0, float(value))
        if isinstance(value, (date, datetime, pd.Timestamp)):
            timestamp = pd.Timestamp(value)
            if timestamp.tzinfo is not None:
                timestamp = timestamp.tz_convert("UTC")
            # Calendar components compare across resolutions without forcing
            # distant maturities into pandas' limited nanosecond range.
            return (1, (timestamp.year, timestamp.month, timestamp.day,
                        timestamp.hour, timestamp.minute, timestamp.second,
                        timestamp.microsecond, timestamp.nanosecond))
        return (2, str(value).casefold())

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortableTableItem):
            return self.sort_value < other.sort_value
        return super().__lt__(other)


class ResultsWindow(QMainWindow):
    def __init__(
        self,
        dataframe: pd.DataFrame,
        window_title: str = "Convertible Bond Search Results",
        heading: str = "Search results",
    ) -> None:
        super().__init__()
        self.setWindowTitle(window_title)
        self.resize(1200, 700)
        self.setStyleSheet(APP_STYLESHEET)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel(heading)
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


def open_bond_record(table: QTableWidget, row: int, column: int) -> None:
    item = table.item(row, column)
    if item is None:
        return
    position = item.data(Qt.ItemDataRole.UserRole)
    if position is None:
        return
    # The stored source position travels with the item when the table sorts.
    record = table.source_records.iloc[[position]].copy(deep=True)
    window = BondRecordWindow(record, table.window(), labels=display_column_labels(record))
    table.record_windows.append(window)
    window.closed.connect(lambda closed: table.record_windows.remove(closed))
    window.show()
    window.raise_()
    window.activateWindow()


def configure_results_table(table: QTableWidget) -> None:
    table.source_records = pd.DataFrame()
    table.record_windows = []
    table.cellDoubleClicked.connect(lambda row, column: open_bond_record(table, row, column))
    table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setAlternatingRowColors(True)
    table.setSortingEnabled(True)
    table.setShowGrid(False)
    table.setSelectionBehavior(
        QAbstractItemView.SelectionBehavior.SelectItems
    )
    table.setSelectionMode(
        QAbstractItemView.SelectionMode.ExtendedSelection
    )
    table.verticalHeader().setVisible(False)
    table.verticalHeader().setDefaultSectionSize(34)
    table.horizontalHeader().setSectionResizeMode(
        QHeaderView.ResizeMode.ResizeToContents
    )
    table.horizontalHeader().setResizeContentsPrecision(-1)
    table.horizontalHeader().setStretchLastSection(False)
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)


def populate_results_table(
    table: QTableWidget,
    dataframe: pd.DataFrame,
) -> None:
    table.source_records = dataframe.copy(deep=True)
    if dataframe.empty:
        dataframe = pd.DataFrame()
    elif "bond_universe" in dataframe.attrs:
        dataframe = select_display_columns(dataframe)
    table.setSortingEnabled(False)
    table.clear()
    table.setRowCount(len(dataframe))
    table.setColumnCount(len(dataframe.columns))
    column_labels = display_column_labels(dataframe)
    table.setHorizontalHeaderLabels([
        column_labels.get(
            str(column).casefold(), str(column).replace("_", " ").title()
        )
        for column in dataframe.columns
    ])

    for row_number, row in enumerate(
        dataframe.itertuples(index=False, name=None)
    ):
        for column_number, value in enumerate(row):
            column = str(dataframe.columns[column_number])
            item = SortableTableItem(value, format_table_value(column, value))
            item.setData(Qt.ItemDataRole.UserRole, row_number)
            table.setItem(row_number, column_number, item)

    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


