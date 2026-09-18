"""Exercise BQL field extraction, lookups, calculations and Qt completion slots."""

import math
import os
import sys
from types import SimpleNamespace

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pandas as pd
import polars as pl
import pytest
from polars_bloomberg import BqlResult
from PySide6.QtWidgets import QApplication
from scipy.stats import norm

from desktop.bond_record import BondRecordWindow


@pytest.mark.parametrize("options_first", [True, False])
@pytest.mark.parametrize("missing", [None, "put", "equity", "ask", "put_error", "equity_error"])
def test_bql_to_both_displayed_spreads(monkeypatch, options_first, missing):
    today = pd.Timestamp.now(tz="UTC").normalize()
    maturity = today + pd.Timedelta(days=730)
    expiry = today + pd.Timedelta(days=180)
    rate = math.log1p(.04)
    assets, debt, asset_vol, years = 150., 100., .3, 2.
    d1 = (math.log(assets / debt) + (rate + .5 * asset_vol ** 2) * years) / (asset_vol * math.sqrt(years))
    d2 = d1 - asset_vol * math.sqrt(years)
    equity = assets * norm.cdf(d1) - debt * math.exp(-rate * years) * norm.cdf(d2)
    vol_decimal = assets / equity * norm.cdf(d1) * asset_vol
    calls = []

    def tables(values, ids):
        # Different field metadata must not interfere with security-ID joins.
        return BqlResult([
            pl.DataFrame({"ID": ids, name: vals, "DATE": [f"2026-09-{i+1:02}"] * len(ids)})
            for i, (name, vals) in enumerate(values.items())
        ], list(values))

    class FakeBQuery:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def bql(self, query):
            calls.append(query)
            if "curvemembers" in query:
                return tables({"maturity()": [(maturity - pd.Timedelta(days=365)).isoformat(),
                                               (maturity + pd.Timedelta(days=365)).isoformat()],
                               "px_last()": [3., 5.]}, ["curve1", "curve2"])
            if "options(" in query:
                if missing == "put_error":
                    raise RuntimeError("Put lookup unavailable")
                if missing == "put":
                    return BqlResult([], [])
                return tables({"name()": ["Example put"], "put_call()": ["Put"],
                               "expire_dt()": [expiry.isoformat()], "strike_px()": [80.],
                               "px_bid()": [.09], "px_ask()": [None if missing == "ask" else .1],
                               "px_last()": [.095], "#avg_volume": [10.], "open_int()": [200.]}, ["put1"])
            if missing == "equity_error":
                raise RuntimeError("Equity lookup unavailable")
            return tables({"px_last()": [100.], "cur_mkt_cap()": [None if missing == "equity" else equity],
                           "bs_st_borrow()": [50.], "bs_lt_borrow()": [100.],
                           "volatility(calc_interval=260D)": [vol_decimal]}, ["ABC US Equity"])

    monkeypatch.setitem(sys.modules, "polars_bloomberg", SimpleNamespace(BQuery=FakeBQuery))
    interest_rate = BondRecordWindow.get_interest_rate("USD", maturity)
    results = BondRecordWindow.get_options("ABC US Equity", maturity)
    assert interest_rate == pytest.approx(4.)
    assert len(calls) == 3
    app = QApplication.instance() or QApplication([])
    window = BondRecordWindow(pd.DataFrame({"MATURITY": [maturity], "CRNCY": ["USD"]}))
    window.loss_given_default = .6
    window._interest_rate_currency = "USD"
    try:
        callbacks = [lambda: window._interest_rate_finished(interest_rate, None),
                     lambda: window._options_finished(results, None)]
        for callback in reversed(callbacks) if options_first else callbacks:
            callback()
        if missing not in {"put", "ask", "put_error"}:
            q = .1 * 1.04 ** (180 / 365) / 80
            expected = (1 - (1 - q) ** (365 / 180)) * .6
            assert window.approximate_credit_spread == pytest.approx(expected)
            assert f"{expected * 10000:,.2f} bps" in window.approximate_spread_label.text()
        else:
            assert window.approximate_credit_spread is None
        if missing not in {"equity", "equity_error"}:
            expected_pd = 1 - math.sqrt(1 - norm.cdf(-d2))
            assert window.merton_default_probability == pytest.approx(expected_pd)
            assert window.merton_credit_spread == pytest.approx(expected_pd * .6)
            assert "Merton credit spread:" in window.merton_spread_label.text()
        else:
            assert window.merton_credit_spread is None
            assert "unavailable" in window.merton_spread_label.text()
        if missing == "put":
            assert window.approximate_spread_label.text() == "DOOTM: no puts found"
        if missing == "put_error":
            assert "Put lookup unavailable" in window.approximate_spread_label.text()
    finally:
        window.close()
        app.processEvents()
