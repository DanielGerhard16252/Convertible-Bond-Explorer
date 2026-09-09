"""Result formatting, tables, and secondary windows."""

from datetime import date, datetime
from numbers import Real

import pandas as pd
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView, QHeaderView, QLabel, QMainWindow, QTableWidget,
    QTableWidgetItem, QTextBrowser, QVBoxLayout, QWidget, QPushButton, QMessageBox,
)

from desktop.styles import APP_STYLESHEET
from desktop.widgets import RequestInput
from desktop.background import BackgroundJob
from server.ai_analysis import run_post_analysis


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
    "yield_to_maturity",
    "yield(yield_type=ytm)",
}

RESULT_COLUMN_LABELS = {
    "id": "ID",
    "long_comp_name": "Long Comp Name",
    "cv_common_ticker_exch": "Cv Common Ticker Exch",
    "security_typ": "Security Typ",
    "industry_sector": "Industry Sector",
    "cntry_of_risk": "Country of Risk",
    "crncy": "CRNCY",
    "amt_outstanding": "Amount Outstanding",
    "bb_composite": "BB Composite",
    "maturity": "Maturity",
    "px_last": "Px last",
    "cv_cnvs_px": "Cv Cnvs Px",
    "cv_cnvs_ratio": "Cv cnvs ratio",
    "parity": "parity",
    "cv_pct_premium": "conversion premium (%)",
    "cpn": "cpn",
    "yield(yield_type=ytm)": "yield(yield type=ytm)",
    "delta": "delta",
    "security_des": "security des",
}


HIGH_YIELD_COLUMN_LABELS = {
    "id": "ID",
    "long_comp_name": "Issuer Name",
    "security_typ": "Security Type",
    "industry_sector": "Industry Sector",
    "cntry_of_risk": "Country of Risk",
    "crncy": "CRNCY",
    "amt_outstanding": "Amt Out",
    "bb_composite": "BB composite",
    "maturity": "Maturity",
    "px_last": "px last",
    "cpn": "cpn",
    "yield(yield_type=ytm)": "yield(yield type=ytm)",
    "security_des": "security des",
}


class SortableTableItem(QTableWidgetItem):
    def __init__(self, value, display_value: str | None = None) -> None:
        super().__init__(display_value if display_value is not None else str(value))
        self.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
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


class AnalysisWindow(QMainWindow):
    closed = Signal(object)

    def __init__(self, question: str, result: str,
                 dataset: pd.DataFrame | None = None, bql_query: str = "") -> None:
        super().__init__()
        self.history = [
            {"role": "user", "content": question},
            {"role": "assistant", "content": result},
        ]
        self.dataset = dataset.copy(deep=True) if dataset is not None else pd.DataFrame()
        self.bql_query = bql_query
        self._job = None
        self._closed = False
        self.setWindowTitle("AI Post Analysis")
        self.resize(800, 600)
        self.setStyleSheet(APP_STYLESHEET)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(12)

        title = QLabel("AI post analysis")
        title.setObjectName("pageTitle")
        question_heading = QLabel("Question")
        question_heading.setObjectName("sectionLabel")
        self.question_label = QLabel(question)
        self.question_label.setWordWrap(True)

        result_heading = QLabel("Answer")
        result_heading.setObjectName("sectionLabel")
        self.result_text = QTextBrowser()
        self._render_history()
        self.result_text.setOpenExternalLinks(True)

        layout.addWidget(title)
        self.question_label.hide()
        layout.addWidget(self.result_text, 1)
        self.follow_up = RequestInput()
        self.follow_up.setPlaceholderText("Ask a follow-up question (Enter to send, Shift+Enter for a new line)")
        self.follow_up.setMaximumHeight(90)
        self.follow_up.submitted.connect(self.submit_follow_up)
        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.submit_follow_up)
        self.send_button.setEnabled(not self.dataset.empty)
        layout.addWidget(self.follow_up)
        layout.addWidget(self.send_button)
        self.setCentralWidget(container)

    def _render_history(self) -> None:
        self.result_text.setMarkdown("\n\n---\n\n".join(
            f"**{'You' if message['role'] == 'user' else 'AI'}**\n\n{message['content']}"
            for message in self.history
        ))
        scrollbar = self.result_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def submit_follow_up(self) -> None:
        question = self.follow_up.toPlainText().strip()
        if self._closed or self._job is not None or not question or self.dataset.empty:
            return
        self._job = BackgroundJob(
            run_post_analysis, question, self.dataset.copy(deep=True),
            self.bql_query, [dict(message) for message in self.history],
        )
        self.history.append({"role": "user", "content": question})
        self._render_history()
        self.follow_up.clear()
        self.send_button.setEnabled(False)
        self.send_button.setText("Waiting...")
        self._job.signals.completed.connect(self._follow_up_finished)
        QThreadPool.globalInstance().start(self._job)

    @Slot(object, object)
    def _follow_up_finished(self, result, error) -> None:
        self._job = None
        if self._closed:
            return
        self.send_button.setEnabled(True)
        self.send_button.setText("Send")
        if error is not None:
            question = self.history.pop()["content"]
            if not self.follow_up.toPlainText().strip():
                self.follow_up.setPlainText(question)
            QMessageBox.critical(self, "Analysis failed", str(error))
        else:
            self.history.append({"role": "assistant", "content": result})
        self._render_history()

    def closeEvent(self, event) -> None:
        self._closed = True
        self.history.clear()
        self.dataset = pd.DataFrame()
        self.bql_query = ""
        self.result_text.clear()
        self.follow_up.clear()
        self.question_label.clear()
        self.closed.emit(self)
        super().closeEvent(event)


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
    table.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignCenter)


BENCHMARK_COLUMN_LABELS = {
    "benchmark_id": "Benchmark Id",
    "benchmark_name": "Benchmark Name",
    "benchmark_expire_dt": "Benchmark Expire Dt()",
    "benchmark_strike_px": "Benchmark Strike Px()",
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
    if "bond_universe" in dataframe.attrs:
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
            table.setItem(
                row_number,
                column_number,
                SortableTableItem(
                    value,
                    format_table_value(column, value),
                ),
            )

    table.resizeColumnsToContents()
    table.setSortingEnabled(True)


def format_table_value(column: str, value) -> str:
    if pd.isna(value):
        return str(value)

    normalized_column = column.casefold()
    if normalized_column in THREE_DECIMAL_COLUMNS:
        try:
            return f"{float(value):.3f}"
        except (TypeError, ValueError):
            return str(value)

    if normalized_column != "maturity":
        return str(value)

    maturity = pd.to_datetime(value, errors="coerce")
    return (
        str(value)
        if pd.isna(maturity)
        else maturity.strftime("%m-%d-%Y")
    )


