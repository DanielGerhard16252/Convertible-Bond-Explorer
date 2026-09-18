"""Detail window for a single bond record."""

from shared.errors import short_error, is_no_results


import math
import pandas as pd
from PySide6.QtCore import Qt, Signal, Slot, QThreadPool
from PySide6.QtWidgets import (
    QAbstractItemView, QLineEdit, QLabel, QMainWindow, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget, QPushButton, QMessageBox,
    QHeaderView, QScrollArea,
)
from desktop.background import BackgroundJob
from desktop.styles import APP_STYLESHEET
from server.bloomberg_api import execute_bql
from server import bond_lookups
from server.bond_lookups import OIS_LOOKUP
from server.credit_analytics import (
    calculate_approximate_spread, calculate_default_probability, calculate_credit_metrics, calculate_merton_spread,
)


class BondRecordWindow(QMainWindow):
    """An independent snapshot of one complete source record."""

    closed = Signal(object)

    def __init__(self, record: pd.DataFrame, parent=None, *, labels: dict[str, str] | None = None) -> None:
        super().__init__(parent)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self._closing = False
        self._interest_rate_job = None
        self._options_job = None
        self.option_results = None
        self.interest_rate = None
        self.credit_spread = None
        self.approximate_credit_spread = None
        self.default_probability = None
        self.merton_default_probability = None
        self.merton_credit_spread = None
        self.loss_given_default = None
        self.record = record.copy(deep=True)
        columns = {str(column).casefold(): position
                   for position, column in enumerate(self.record.columns)}
        bond_name = "Bond details"
        for field in ("security_des", "bond_name", "description", "id", "isin"):
            if field in columns and not self.record.empty:
                value = self.record.iloc[0, columns[field]]
                if pd.notna(value) and str(value).strip():
                    bond_name = str(value)
                    break
        self.setWindowTitle(bond_name)
        self.resize(1200, 700)
        self.setStyleSheet(APP_STYLESHEET)
        container = QWidget()
        layout = QVBoxLayout(container)
        self.heading = QLabel(bond_name)
        self.heading.setTextFormat(Qt.TextFormat.PlainText)
        self.heading.setObjectName("pageTitle")
        self.heading.setWordWrap(True)
        layout.addWidget(self.heading)
        self.table = QTableWidget(len(self.record), len(self.record.columns))
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        labels = labels or {}
        for column_number, column in enumerate(self.record.columns):
            header = QTableWidgetItem(labels.get(str(column).casefold(), str(column)))
            header.setToolTip(str(column))
            self.table.setHorizontalHeaderItem(column_number, header)
            for row_number in range(len(self.record)):
                self.table.setItem(row_number, column_number, QTableWidgetItem(
                    str(self.record.iloc[row_number, column_number])
                ))
        self.table.resizeColumnsToContents()
        self.table.setFixedHeight(
            self.table.horizontalHeader().sizeHint().height()
            + sum(self.table.rowHeight(row) for row in range(self.table.rowCount()))
            + self.table.horizontalScrollBar().sizeHint().height()
            + 2 * self.table.frameWidth() + 8
        )
        layout.addWidget(self.table)
        layout.addWidget(QLabel("Loss given default (%) — required, 0 to 100"))
        self.lgd_input = QLineEdit()
        self.lgd_input.setPlaceholderText("e.g. 60 for 60%")
        self.lgd_input.textChanged.connect(self._update_rate_button)
        layout.addWidget(self.lgd_input)
        self.interest_rate_button = QPushButton("Get interest rate")
        self.interest_rate_button.setEnabled(False)
        self.interest_rate_button.clicked.connect(self.request_interest_rate)
        layout.addWidget(self.interest_rate_button, alignment=Qt.AlignmentFlag.AlignLeft)
        self.interest_rate_label = QLabel()
        layout.addWidget(self.interest_rate_label)
        self.credit_spread_label = QLabel()
        self.credit_spread_label.hide()
        self.approximate_spread_label = QLabel()
        self.approximate_spread_label.setObjectName("pageTitle")
        self.approximate_spread_label.setWordWrap(True)
        layout.addWidget(self.approximate_spread_label)
        variables_heading = QLabel("Inputs")
        variables_heading.setObjectName("sectionLabel")
        layout.addWidget(variables_heading)
        self.variables_table = self._detail_table(["Variable", "Symbol", "Value", "Units / basis"])
        layout.addWidget(self.variables_table)
        self.merton_spread_label = QLabel()
        self.merton_spread_label.setObjectName("pageTitle")
        self.merton_spread_label.setWordWrap(True)
        layout.insertWidget(layout.indexOf(self.approximate_spread_label) + 1, self.merton_spread_label)
        self.options_status = QLabel()
        self.options_status.setWordWrap(True)
        layout.addWidget(self.options_status)
        self.options_table = self._detail_table(["Returned field", "Value"])
        self.options_table.hide()
        layout.addWidget(self.options_table)
        layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(container)
        self.setCentralWidget(scroll)

    @staticmethod
    def _detail_table(headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        table.setAlternatingRowColors(True)
        table.verticalHeader().hide()
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setMinimumHeight(70)
        return table

    @staticmethod
    def _fill_detail_table(table, rows):
        table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                if column == (2 if table.columnCount() == 4 else 1):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row, column, item)
        table.resizeRowsToContents()
        table.setFixedHeight(table.horizontalHeader().height()
                             + sum(table.rowHeight(row) for row in range(len(rows))) + 8)

    def _lgd_value(self):
        try:
            value = float(self.lgd_input.text())
        except ValueError:
            return None
        return value / 100 if math.isfinite(value) and 0 <= value <= 100 else None

    def _update_rate_button(self):
        self.interest_rate_button.setEnabled(
            self._lgd_value() is not None and self._interest_rate_job is None and self._options_job is None
        )

    def request_interest_rate(self) -> None:
        if self._interest_rate_job is not None or self._options_job is not None or self._closing:
            return
        self.loss_given_default = self._lgd_value()
        if self.loss_given_default is None:
            return
        self.approximate_credit_spread = None
        self.merton_credit_spread = None
        self.merton_default_probability = None
        self.approximate_spread_label.clear()
        self.merton_spread_label.clear()
        self.variables_table.setRowCount(0)
        self.options_table.setRowCount(0)
        self.options_table.hide()
        record = self.record.iloc[0] if not self.record.empty else pd.Series(dtype=object)
        currency = next((record[column] for column in record.index
                         if str(column).strip().casefold() in {"crncy", "currency"}), None)
        currency = str(currency).strip().upper()
        self._interest_rate_currency = currency
        maturity = next((record[column] for column in record.index
                         if str(column).strip().casefold() == "maturity"), None)
        if maturity is None or pd.isna(maturity):
            QMessageBox.warning(self, "Interest rate", "Bond maturity is missing")
            return
        self._interest_rate_job = BackgroundJob(BondRecordWindow.get_interest_rate, currency, maturity)
        self._interest_rate_job.signals.completed.connect(self._interest_rate_finished)
        self.interest_rate_button.setEnabled(False)
        self.interest_rate_button.setText("Loading interest rate...")
        self.interest_rate = None
        self.interest_rate_label.clear()
        self.credit_spread = None
        self.credit_spread_label.clear()
        QThreadPool.globalInstance().start(self._interest_rate_job)
        fields = {str(column).strip().casefold(): record[column] for column in record.index}
        ticker = next((fields[field] for field in ("cast_parent_equity_ticker", "cv_common_ticker_exch")
                       if field in fields and pd.notna(fields[field]) and str(fields[field]).strip()), None)
        self.option_results = None
        if ticker is None:
            self.options_status.setText("Options unavailable: equity ticker is missing")
        else:
            self.options_status.setText("Loading options...")
            self._options_job = BackgroundJob(BondRecordWindow.get_options, ticker, maturity)
            self._options_job.signals.completed.connect(self._options_finished)
            QThreadPool.globalInstance().start(self._options_job)

    @Slot(object, object)
    def _interest_rate_finished(self, results, error) -> None:
        self._interest_rate_job = None
        if self._closing:
            return
        self._update_rate_button()
        self.interest_rate_button.setText("Get interest rate")
        if error is not None:
            QMessageBox.critical(self, "Interest rate failed", short_error(error))
            return
        self.interest_rate = results
        self.interest_rate_label.setText(
            f"Estimated risk-free interest rate ({self._interest_rate_currency}): {results:.4f}%"
        )
        record = self.record.iloc[0] if not self.record.empty else pd.Series(dtype=object)
        ytm = next((record[column] for column in record.index
                    if str(column).strip().casefold() in
                    {"yield_to_maturity", "yield(yield_type=ytm)"}), None)
        ytm = pd.to_numeric(ytm, errors="coerce")
        if pd.isna(ytm):
            self.credit_spread = None
            self.credit_spread_label.setText("Credit spread: unavailable (yield to maturity is missing)")
        else:
            self.credit_spread = float(ytm) - self.interest_rate
            self.credit_spread_label.setText(
                f"Credit spread (YTM − interest rate): {self.credit_spread:.4f} percentage points "
                f"({self.credit_spread * 100:.2f} bps)"
            )

        self._update_approximate_spread()

    calculate_approximate_spread = staticmethod(calculate_approximate_spread)

    def _update_approximate_spread(self):
        self.default_probability = None
        self.approximate_credit_spread = None
        self.merton_default_probability = None
        self.merton_credit_spread = None
        if self.interest_rate is None or self.option_results is None or self.loss_given_default is None:
            return
        option = ({str(key).strip().casefold(): value for key, value in self.option_results.iloc[0].items()}
                  if not self.option_results.empty else {})
        option.update({key.casefold(): value for key, value in self.option_results.attrs.get("equity", {}).items()})
        today = pd.Timestamp.now(tz="UTC").normalize()
        record = self.record.iloc[0] if not self.record.empty else pd.Series(dtype=object)
        maturity = next((record[column] for column in record.index
                         if str(column).strip().casefold() == "maturity"), None)
        self._fill_detail_table(self.variables_table, [
            ("Risk-free interest rate", "r", f"{self.interest_rate:.4f}%", "Annual rate"),
            ("Loss given default", "LGD", f"{self.loss_given_default:.2%}", ""),
            ("Bond maturity", "", str(maturity) if maturity is not None else "Unavailable", ""),
        ])
        try:
            metrics = calculate_credit_metrics(
                option["px_ask"], self.interest_rate, option["expire_dt"],
                self.loss_given_default, option["strike_px"], today=today)
            self.approximate_credit_spread = metrics.spread
            self.default_probability = metrics.default_probability
            self.approximate_spread_label.setText(
                f"DOOTM credit spread: {metrics.spread:.4%} ({metrics.spread * 10000:,.2f} bps)"
                f"\nOne-year default probability: {metrics.default_probability:.4%}")
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self.approximate_spread_label.setText(
                f"DOOTM: {self.option_results.attrs.get('put_error', 'no puts found')}"
                if self.option_results.empty else f"DOOTM: {short_error(error)}")
        try:
            probability, spread = calculate_merton_spread(
                option.get("underlying_cur_mkt_cap"), option.get("underlying_bs_st_borrow"),
                option.get("underlying_bs_lt_borrow"), self.interest_rate, maturity,
                option.get("underlying_volatility(calc_interval=260d)"),
                self.loss_given_default, today=today)
            self.merton_default_probability = probability
            self.merton_credit_spread = spread
            self.merton_spread_label.setText(
                f"Merton credit spread: {spread:.4%} ({spread * 10000:,.2f} bps)"
                f"\nOne-year default probability: {probability:.4%}")
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            message = self.option_results.attrs.get("equity_error", "unavailable (missing inputs or calibration failed)")
            self.merton_spread_label.setText(f"Merton: {message}")

    calculate_default_probability = staticmethod(calculate_default_probability)

    @staticmethod
    def get_interest_rate(currency, maturity):
        return bond_lookups.get_interest_rate(currency, maturity, executor=execute_bql)

    @staticmethod
    def get_options(ticker_name, maturity=None, today=None):
        return bond_lookups.get_options(ticker_name, maturity, today, executor=execute_bql)

    @Slot(object, object)
    def _options_finished(self, results, error):
        self._options_job = None
        if self._closing:
            return
        self._update_rate_button()
        if error is not None:
            self.options_status.setText("no puts found" if is_no_results(error) else short_error(error))
            return
        self.option_results = results
        self._update_approximate_spread()
        self.options_status.setText("Put and underlying equity values" if not results.empty
                                    else results.attrs.get("put_error", "no puts found"))
        names = {"NAME": "Name", "PUT_CALL": "Option type", "EXPIRE_DT": "Expiry",
                 "STRIKE_PX": "Strike", "PX_BID": "Bid", "PX_ASK": "Ask",
                 "PX_LAST": "Last price", "#AVG_VOLUME": "Average volume (30 days)",
                 "OPEN_INT": "Open interest", "UNDERLYING_PX_LAST": "Underlying price",
                 "UNDERLYING_CUR_MKT_CAP": "Equity market cap (Bloomberg units)",
                 "UNDERLYING_BS_ST_BORROW": "Short-term borrowing (Bloomberg units)",
                 "UNDERLYING_BS_LT_BORROW": "Long-term borrowing (Bloomberg units)",
                 "UNDERLYING_VOLATILITY(CALC_INTERVAL=260D)": "Equity volatility (260 days)",
                 "PUT_OTM_PERCENT": "Put out of the money (%)", "UNDERLYING_ERROR": "Underlying lookup"}
        rows = []
        display_results = results if not results.empty else pd.DataFrame([results.attrs.get("equity", {})])
        for _, option in display_results.iterrows():
            for column, value in option.items():
                field = str(column).upper()
                if pd.isna(value):
                    display = "—"
                elif field == "EXPIRE_DT":
                    display = pd.Timestamp(value).strftime("%d %b %Y")
                elif field == "PUT_OTM_PERCENT":
                    display = f"{float(value):.2f}%"
                elif field == "UNDERLYING_VOLATILITY(CALC_INTERVAL=260D)":
                    display = f"{float(value):.2f}%"
                elif field in {"UNDERLYING_CUR_MKT_CAP", "UNDERLYING_BS_ST_BORROW", "UNDERLYING_BS_LT_BORROW"}:
                    display = f"{float(value):,.2f}"
                elif field in {"STRIKE_PX", "PX_BID", "PX_ASK", "PX_LAST", "UNDERLYING_PX_LAST"}:
                    display = f"{float(value):,.4f}"
                elif field in {"OPEN_INT", "#AVG_VOLUME"}:
                    display = f"{float(value):,.2f}"
                else:
                    display = str(value)
                rows.append((names.get(field, str(column)), display))
        self._fill_detail_table(self.options_table, rows)
        self.options_table.setVisible(bool(rows))

    def closeEvent(self, event) -> None:
        self._closing = True
        if self._interest_rate_job is not None:
            self._interest_rate_job.signals.completed.disconnect(self._interest_rate_finished)
        if self._options_job is not None:
            self._options_job.signals.completed.disconnect(self._options_finished)
        self.closed.emit(self)
        super().closeEvent(event)
