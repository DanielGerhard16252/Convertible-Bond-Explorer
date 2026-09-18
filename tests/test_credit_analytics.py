"""Service calculations are usable without a Qt window or Bloomberg session."""

import math

import pandas as pd
import pytest

from server.credit_analytics import calculate_credit_metrics
from server.bond_lookups import get_options


@pytest.mark.parametrize("days", [180, 365, 730])
def test_metrics_share_one_annual_probability(days):
    today = pd.Timestamp("2026-01-01")
    metrics = calculate_credit_metrics(
        0.1, 4, today + pd.Timedelta(days=days), 0.6, 7.5, today=today)
    expected_q = 0.1 * 1.04 ** (days / 365) / 7.5
    expected_pd = 1 - (1 - expected_q) ** (365 / days)
    assert metrics.q == pytest.approx(expected_q)
    assert metrics.default_probability == pytest.approx(expected_pd)
    assert metrics.default_intensity == pytest.approx(-math.log1p(-expected_q) / (days / 365))
    assert metrics.spread == pytest.approx(expected_pd * 0.6)


def test_put_service_accepts_injected_executor():
    calls = []
    expected = pd.DataFrame({"PX_ASK": [1.0]})
    def execute(query, **kwargs):
        calls.append(query)
        return expected
    result = get_options("ABC US Equity", today="2026-01-01", executor=execute)
    pd.testing.assert_frame_equal(result[expected.columns], expected)
    assert "expire_dt() >= 2026-01-11" in calls[0]
    assert "#relative_spread < 0.3" in calls[0]


@pytest.mark.parametrize("strike, expected", [(80, 20), (100, 0), (120, -20)])
def test_underlying_price_and_put_moneyness(strike, expected):
    calls = []
    def execute(query, **kwargs):
        calls.append(query)
        if len(calls) == 1:
            return pd.DataFrame({"STRIKE_PX": [strike], "PX_LAST": [2.]})
        assert query == "get(px_last(), cur_mkt_cap(), bs_st_borrow(), bs_lt_borrow(), volatility(calc_interval=260D)) for('ABC US Equity')"
        assert kwargs == {"requested_columns": (
            "PX_LAST", "CUR_MKT_CAP", "BS_ST_BORROW", "BS_LT_BORROW",
            "VOLATILITY(CALC_INTERVAL=260D)"), "field_values_only": True}
        return pd.DataFrame({"PX_LAST": [100.], "CUR_MKT_CAP": [10000.],
                             "BS_ST_BORROW": [None], "BS_LT_BORROW": [200.],
                             "VOLATILITY(CALC_INTERVAL=260D)": [.25]})
    result = get_options("ABC US Equity", executor=execute)
    assert result.loc[0, "UNDERLYING_PX_LAST"] == 100
    assert result.loc[0, "PUT_OTM_PERCENT"] == expected
    assert result.loc[0, "PX_LAST"] == 2
    assert result.loc[0, "UNDERLYING_CUR_MKT_CAP"] == 10000
    assert pd.isna(result.loc[0, "UNDERLYING_BS_ST_BORROW"])
    assert result.loc[0, "UNDERLYING_BS_LT_BORROW"] == 200
    assert result.loc[0, "UNDERLYING_VOLATILITY(CALC_INTERVAL=260D)"] == .25


def test_underlying_failure_preserves_put():
    def execute(query, **kwargs):
        if "options(" in query:
            return pd.DataFrame({"STRIKE_PX": [80.]})
        raise RuntimeError("Price unavailable\nDiagnostics: details")
    result = get_options("ABC US Equity", executor=execute)
    assert result.loc[0, "STRIKE_PX"] == 80
    assert pd.isna(result.loc[0, "PUT_OTM_PERCENT"])
    assert result.loc[0, "UNDERLYING_ERROR"] == "Price unavailable"


@pytest.mark.parametrize("assets, asset_vol, years", [
    (150., .3, 2.), (20., .05, 20.), (50., .05, 5.), (50., .8, .1),
])
def test_merton_recovers_known_asset_model(assets, asset_vol, years):
    from scipy.stats import norm
    from server.credit_analytics import merton, calculate_merton_spread
    debt, rate = 100., .04
    d1 = (math.log(assets / debt) + (rate + .5 * asset_vol ** 2) * years) / (asset_vol * math.sqrt(years))
    d2 = d1 - asset_vol * math.sqrt(years)
    equity = assets * norm.cdf(d1) - debt * math.exp(-rate * years) * norm.cdf(d2)
    equity_vol = assets / equity * norm.cdf(d1) * asset_vol
    expected = norm.cdf(-d2)
    assert merton(equity, 50., 100., rate, years, equity_vol) == pytest.approx(expected)
    annual, spread = calculate_merton_spread(
        equity, 50., 100., math.expm1(rate) * 100,
        pd.Timestamp("2026-01-01") + pd.Timedelta(days=365 * years),
        equity_vol, .6, today="2026-01-01")
    assert annual == pytest.approx(1 - (1 - expected) ** (1 / years))
    assert spread == pytest.approx(annual * .6)


@pytest.mark.parametrize("equity, short_debt, long_debt, vol", [
    (None, 50, 100, .30), (100, -1, 100, .30), (100, 0, 0, .30), (100, 50, 100, 0),
])
def test_merton_rejects_missing_or_invalid_inputs(equity, short_debt, long_debt, vol):
    from server.credit_analytics import calculate_merton_spread
    with pytest.raises((TypeError, ValueError)):
        calculate_merton_spread(equity, short_debt, long_debt, 4, "2028-01-01", vol, .6, today="2026-01-01")


def test_equity_is_retained_when_no_puts_found():
    def execute(query, **kwargs):
        if "options(" in query:
            raise RuntimeError("No results found")
        return pd.DataFrame({"PX_LAST": [100.], "CUR_MKT_CAP": [1000.],
                             "BS_ST_BORROW": [50.], "BS_LT_BORROW": [100.],
                             "VOLATILITY(CALC_INTERVAL=260D)": [.30]})
    result = get_options("ABC US Equity", executor=execute)
    assert result.empty
    assert result.attrs["equity"]["UNDERLYING_CUR_MKT_CAP"] == 1000.
