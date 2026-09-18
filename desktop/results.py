"""Result formatting, tables, and secondary windows."""

from datetime import date, datetime
from numbers import Real

import pandas as pd
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QMainWindow, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from desktop.styles import APP_STYLESHEET
from desktop.bond_record import BondRecordWindow
from desktop.analysis_window import AnalysisWindow  # Backwards-compatible import.


THREE_DECIMAL_COLUMNS = {
    "parity",
    "cv_pct_premium",
    "conversion_premium",
    "price",
    "px_last",
    "conversion_price",
    "cv_cnvs_px",
    "conversion_ratio",
    "cv_cnvs_ratio",
    "strike_px",
    "benchmark_strike_px",
    "benchmark_px_last",
    "benchmark_ivol",
    "benchmark_cpn",
    "benchmark_yield(yield_type=ytm)",
    "yield_to_maturity",
    "yield_to_worst",
    "yield(yield_type=ytw)",
    "yield(yield_type=ytm)",
}

RESULT_COLUMN_LABELS = {
    "id": "ID",
    "long_comp_name": "Issuer",
    "cv_common_ticker_exch": "Equity ticker",
    "security_typ": "Security type",
    "classification_name(bics,2)": "Sector",
    "payment_rank": "Payment rank",
    "cntry_of_risk": "Risk country",
    "crncy": "Currency",
    "amt_outstanding": "Outstanding",
    "bb_composite": "Credit rating",
    "maturity": "Maturity",
    "px_last": "Price",
    "cv_cnvs_px": "Conversion price",
    "cv_cnvs_ratio": "Conversion ratio",
    "parity": "Parity",
    "cv_pct_premium": "Premium (%)",
    "cpn": "Coupon (%)",
    "yield(yield_type=ytm)": "YTM (%)",
    "yield(yield_type=ytw)": "YTW (%)",
    "delta": "Delta",
    "security_des": "Description",
}


HIGH_YIELD_COLUMN_LABELS = {
    "cast_parent_equity_ticker": "Parent equity ticker",
    "id": "ID",
    "long_comp_name": "Issuer",
    "security_typ": "Security type",
    "classification_name(bics,2)": "Sector",
    "payment_rank": "Payment rank",
    "cntry_of_risk": "Risk country",
    "crncy": "Currency",
    "amt_outstanding": "Outstanding",
    "bb_composite": "Credit rating",
    "maturity": "Maturity",
    "px_last": "Price",
    "cpn": "Coupon (%)",
    "yield(yield_type=ytm)": "YTM (%)",
    "yield(yield_type=ytw)": "YTW (%)",
    "security_des": "Description",
}


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


BENCHMARK_COLUMN_LABELS = {
    "benchmark_name": "Option name",
    "benchmark_expire_dt": "Option expiry",
    "benchmark_strike_px": "Option strike",
    "benchmark_px_last": "Option price",
    "benchmark_ivol": "Option implied vol",
}


def display_column_labels(dataframe: pd.DataFrame) -> dict[str, str]:
    labels = dict(HIGH_YIELD_COLUMN_LABELS
                  if dataframe.attrs.get("bond_universe") == "high_yield"
                  else RESULT_COLUMN_LABELS)
    if dataframe.attrs.get("include_benchmarks"):
        labels.update(BENCHMARK_COLUMN_LABELS)
    return labels


def select_display_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Match Bloomberg mnemonics or friendly headings without guessing fields."""
    labels = display_column_labels(dataframe)

    def key(value):
        return "".join(str(value).split()).replace("_", "").casefold().removesuffix("()")

    available = {}
    for column in dataframe.columns:
        available.setdefault(key(column), []).append(column)
    selected = []
    renamed = {}
    for field, label in labels.items():
        aliases = {key(field), key(label)}
        if field.startswith("benchmark_"):
            aliases.add(key("Benchmark " + label))
        if field == "security_typ":
            aliases.add(key("Security Type"))
        matches = [column for alias in aliases for column in available.get(alias, [])]
        if len(matches) > 1:
            raise ValueError(f"Multiple returned columns match {label}: {matches}")
        if matches:
            selected.append(matches[0])
            renamed[matches[0]] = field.upper()
    if not selected and len(dataframe.columns):
        raise ValueError(f"No recognised result columns. Returned: {list(dataframe.columns)}")
    return dataframe.loc[:, selected].rename(columns=renamed)


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


def format_table_value(column: str, value) -> str:
    if pd.isna(value):
        return str(value)

    normalized_column = column.casefold().removesuffix("()")
    amount_column = normalized_column.replace("_", "").replace(" ", "")
    if amount_column in {
        "amtoutstanding", "amountoutstanding", "amtout",
        "benchmarkamtoutstanding", "benchmarkamountoutstanding",
    }:
        try:
            return f"{float(value):,.0f}"
        except (TypeError, ValueError, OverflowError):
            return str(value)
    if normalized_column in THREE_DECIMAL_COLUMNS:
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    date_column = normalized_column.replace("_", "").replace(" ", "").removesuffix("()")
    if date_column not in {"maturity", "benchmarkexpiredt"}:
        return str(value)

    try:
        maturity = pd.Timestamp(value)
    except (ValueError, TypeError, OverflowError):
        return str(value)
    return (
        str(value)
        if pd.isna(maturity)
        else maturity.strftime("%m-%d-%Y")
    )


