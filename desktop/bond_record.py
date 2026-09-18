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
        layout.addWidget(self.credit_spread_label)
        self.approximate_spread_label = QLabel()
        self.approximate_spread_label.setObjectName("pageTitle")
        self.approximate_spread_label.setWordWrap(True)
        layout.addWidget(self.approximate_spread_label)
        variables_heading = QLabel("Calculation inputs and derived values")
        variables_heading.setObjectName("sectionLabel")
        layout.addWidget(variables_heading)
        self.variables_table = self._detail_table(["Variable", "Symbol", "Value", "Units / basis"])
        layout.addWidget(self.variables_table)
        self.calculation_label = QLabel()
        self.calculation_label.setTextFormat(Qt.TextFormat.PlainText)
        self.calculation_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.calculation_label.setWordWrap(True)
        self.calculation_label.hide()
        calculation_toggle = QPushButton("Show calculation steps")
        calculation_toggle.setCheckable(True)
        calculation_toggle.toggled.connect(self.calculation_label.setVisible)
        calculation_toggle.toggled.connect(
            lambda checked: calculation_toggle.setText(
                "Hide calculation steps" if checked else "Show calculation steps"))
        layout.addWidget(calculation_toggle, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.calculation_label)
        self.options_status = QLabel()
        self.options_status.setWordWrap(True)
        layout.addWidget(self.options_status)
        self.options_table = self._detail_table(["Option field", "Value"])
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
        self.approximate_spread_label.clear()
        self.calculation_label.clear()
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

    @staticmethod
    def calculate_approximate_spread(ask, rate_percent, expiry, lgd, strike, today=None):
        today = pd.Timestamp.now(tz="UTC").normalize() if today is None else pd.to_datetime(today, utc=True)
        years = (pd.to_datetime(expiry, utc=True) - today).total_seconds() / (365 * 24 * 3600)
        if not math.isfinite(years) or years <= 0:
            raise ValueError("Option expiry must be in the future")
        if not all(math.isfinite(float(value)) for value in (ask, rate_percent, lgd)) or not 0 <= lgd <= 1:
            raise ValueError("Ask, interest rate and LGD must be valid numbers")
        strike = float(strike)
        if not math.isfinite(strike) or strike <= 0:
            raise ValueError("Strike must be a positive number")
        if float(rate_percent) <= -100:
            raise ValueError("Interest rate must be greater than -100%")
        rate = math.log1p(float(rate_percent) / 100)
        q = float(ask) * math.exp(rate * years) / strike
        if not 0 <= q < 1:
            raise ValueError("The formula requires 0 <= ask * exp(r * T) / strike < 1")
        return BondRecordWindow.calculate_default_probability(q, years) * lgd

    def _update_approximate_spread(self):
        self.default_probability = None
        if self.interest_rate is None or self.option_results is None or self.loss_given_default is None:
            return
        if self.option_results.empty:
            self.approximate_spread_label.setText("no puts found")
            return
        option = {str(key).strip().casefold(): value for key, value in self.option_results.iloc[0].items()}
        today = pd.Timestamp.now(tz="UTC").normalize()
        try:
            self.approximate_credit_spread = self.calculate_approximate_spread(
                option["px_ask"], self.interest_rate, option["expire_dt"], self.loss_given_default, option["strike_px"], today=today
            )
        except (ValueError, TypeError, KeyError, OverflowError) as error:
            self.approximate_spread_label.setText(f"Approximate credit spread: unavailable ({short_error(error)})")
            return
        years = (pd.to_datetime(option["expire_dt"], utc=True) - today).total_seconds() / (365 * 24 * 3600)
        rate = math.log1p(float(self.interest_rate) / 100)
        ask = float(option["px_ask"])
        strike = float(option["strike_px"])
        q = ask * math.exp(rate * years) / strike
        y = -math.log1p(-q) / years
        self.default_probability = self.calculate_default_probability(q, years)
        probability_text = f"{self.default_probability:.4%}"
        self._fill_detail_table(self.variables_table, [
            ("Risk-free interest rate", "r", f"{self.interest_rate:.4f}%", "Annual rate"),
            ("Continuous risk-free rate", "rₑ", f"{rate:.6f}", "ln(1 + r), decimal per year"),
            ("Valuation date", "", today.strftime("%d %b %Y"), "UTC"),
            ("Option expiry", "", pd.Timestamp(option["expire_dt"]).strftime("%d %b %Y"), "Date"),
            ("Time to expiry", "T", f"{years:.4f}", "Years (actual days / 365)"),
            ("Put ask price", "P", f"{ask:,.6f}", "Option quote units"),
            ("Strike price", "K", f"{strike:,.4f}", "Same price units as ask"),
            ("Loss given default", "LGD", f"{self.loss_given_default:.2%}", "Fraction used in calculation"),
            ("Derived q", "q", f"{q:.6%}", "P × exp(rₑ × T) / K"),
            ("Default intensity", "y", f"{y:.6f}", "−ln(1 − q) / T_put, per year"),
            ("Default probability horizon", "T_PD", "1.0000", "Year"),
            ("One-year default probability", "PD", probability_text, "1 ? exp(?y ? 1)"),
            ("Approximate spread", "LGD × PD (1 year)", f"{self.approximate_credit_spread:.4%}",
             f"{self.approximate_credit_spread * 10000:,.2f} bps"),
        ])
        self.calculation_label.setText(
            f"r = ln(1 + {self.interest_rate:.6g}% / 100) = {rate:.8g}\n"
            f"T = (expiry - {today:%Y-%m-%d}) / 365 days = {years:.8g} years\n"
            f"LGD = {self.loss_given_default * 100:.6g}% / 100 = {self.loss_given_default:.8g}\n"
            f"q = {ask:.8g} * exp({rate:.8g} * {years:.8g}) / {strike:.8g} = {q:.8g}\n"
            f"y = -ln(1 - {q:.8g}) / {years:.8g} = {y:.8g} per year\n"
            f"PD (1 year) = 1 - exp(-y * 1) = {probability_text}\n"
            f"Spread = LGD * PD (1 year) = {self.loss_given_default:.8g} * {self.default_probability:.8g} = {self.approximate_credit_spread:.8g}"
        )
        self.approximate_spread_label.setText(
            f"Approximate credit spread (LGD × one-year PD): {self.approximate_credit_spread * 100:.4f}% "
            f"({self.approximate_credit_spread * 10000:.2f} bps)"
            f"\nOne-year default probability: {probability_text}"
        )

    @staticmethod
    def calculate_default_probability(q, put_years, horizon_years=1.0):
        if not all(math.isfinite(value) for value in (q, put_years, horizon_years)):
            raise ValueError("Default probability inputs must be finite")
        if not 0 <= q < 1 or put_years <= 0 or horizon_years < 0:
            raise ValueError("Requires 0 <= q < 1, positive put horizon and nonnegative probability horizon")
        y = -math.log1p(-q) / put_years
        return -math.expm1(-y * horizon_years)

    @staticmethod
    def get_interest_rate(currency, maturity):
        currency = str(currency).strip().upper()
        maturity = pd.to_datetime(maturity, utc=True).tz_localize(None)
        if pd.isna(maturity):
            raise ValueError("Bond maturity is missing")
        if currency not in OIS_LOOKUP:
            raise ValueError(f"Interest-rate curve is not configured for currency: {currency}")
        query = f"GET(maturity(), px_last()) FOR(curvemembers('{OIS_LOOKUP[currency]}'))"
        results = execute_bql(
            query, requested_columns=("maturity", "PX_LAST"),
            field_values_only=True,
        ).copy()
        results["maturity"] = (
            pd.to_datetime(results["maturity"], format="mixed", errors="raise", utc=True)
            .dt.tz_localize(None)
            .astype("datetime64[ns]")
        )
        results["PX_LAST"] = pd.to_numeric(results["PX_LAST"], errors="coerce")
        results = results.dropna(subset=["maturity", "PX_LAST"])
        results = results.loc[results["PX_LAST"].map(math.isfinite).astype(bool)].sort_values("maturity")
        if results.empty:
            raise ValueError("No valid swap rates are available for this currency")
        upper = results["maturity"].searchsorted(maturity)
        if upper == 0:
            return float(results.iloc[0]["PX_LAST"])
        if upper == len(results):
            return float(results.iloc[-1]["PX_LAST"])
        right = results.iloc[upper]
        left = results.iloc[upper - 1]
        weight = (maturity - left["maturity"]) / (right["maturity"] - left["maturity"])
        return float(left["PX_LAST"] + weight * (right["PX_LAST"] - left["PX_LAST"]))

    @staticmethod
    def get_options(ticker_name, maturity, today=None):
        today = (pd.Timestamp.now(tz="UTC") if today is None else pd.to_datetime(today, utc=True)).tz_localize(None).normalize()
        start = (today + pd.Timedelta(days=30)).strftime("%Y-%m-%d")
        ticker_name = str(ticker_name).replace("\\", "\\\\").replace("'", "\\'")
        query = f"""
let(
    #avg_volume = avg(
        dropna(px_volume(dates=range(-30d, 0d)))
    );
    #relative_spread = (
        px_ask() - px_bid()
    ) / (
        (px_ask() + px_bid()) / 2
    );
)
get(
    name(),
    put_call(),
    expire_dt(),
    strike_px(),
    px_bid(),
    px_ask(),
    px_last(),
    #avg_volume,
    open_int()
)
for(
    top(
        filter(
            options('{ticker_name}'),
            put_call() == 'Put'
            and expire_dt() > {start}
            and px_bid() > 0
            and px_ask() > 0
            and open_int() >= 100
            and #avg_volume >= 5
            and #relative_spread <= 0.1
        ),
        1,
        -strike_px()
    )
)
"""
        print(query, flush=True)
        return execute_bql(query, requested_columns=(
            "NAME", "PUT_CALL", "EXPIRE_DT", "STRIKE_PX", "PX_BID", "PX_ASK",
            "PX_LAST", "#avg_volume", "OPEN_INT",
        ), field_values_only=True)

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
        self.options_status.setText("Selected put option" if not results.empty else "no puts found")
        names = {"NAME": "Name", "PUT_CALL": "Option type", "EXPIRE_DT": "Expiry",
                 "STRIKE_PX": "Strike", "PX_BID": "Bid", "PX_ASK": "Ask",
                 "PX_LAST": "Last price", "#AVG_VOLUME": "Average volume (30 days)",
                 "OPEN_INT": "Open interest"}
        rows = []
        for _, option in results.iterrows():
            for column, value in option.items():
                field = str(column).upper()
                if pd.isna(value):
                    display = "—"
                elif field == "EXPIRE_DT":
                    display = pd.Timestamp(value).strftime("%d %b %Y")
                elif field in {"STRIKE_PX", "PX_BID", "PX_ASK", "PX_LAST"}:
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




OIS_LOOKUP = {
    "CAD": "YCSW0147 Index",
    "CHF": "YCSW0234 Index",
    "EUR": "YCSW0514 Index",  # €STR; replaces EONIA curve 0133
    "GBP": "YCSW0141 Index",
    "JPY": "YCSW0195 Index",
    "SEK": "YCSW0185 Index",
    "USD": "YCSW0490 Index",  # SOFR; replaces Fed Funds curve 0042
    "AUD": "YCSW0159 Index",
    "BRL": "YCSW0089 Index",
    "CNY": "YCSW0228 Index",
    "COP": "YCSW0329 Index",
    "CZK": "YCSW0551 Index",
    "DKK": "YCSW0186 Index",
    "GEL": "YCSW0586 Index",
    "HKD": "YCSW0145 Index",
    "HUF": "YCSW0325 Index",
    "IDR": "YCSW0158 Index",
    "ILS": "YCSW0585 Index",
    "INR": "YCSW0046 Index",
    "ISK": "YCSW0188 Index",
    "KRW": "YCSW0057 Index",
    "MXN": "YCSW0583 Index",
    "MYR": "YCSW0267 Index",
    "NOK": "YCSW0487 Index",
    "NZD": "YCSW0198 Index",
    "PHP": "YCSW0370 Index",
    "PLN": "YCSW0327 Index",
    "RUB": "YCSW0356 Index",
    "SGD": "YCSW0527 Index",
    "THB": "YCSW0146 Index",
    "TRY": "YCSW0522 Index",
    "ZAR": "YCSW0584 Index",
}
