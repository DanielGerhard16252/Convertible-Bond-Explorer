"""Bloomberg rate-curve and put-option retrieval, independent of the UI."""

import math

import pandas as pd

from server.bloomberg_api import execute_bql
from shared.errors import short_error, is_no_results

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


def get_interest_rate(currency, maturity, *, executor=None):
    currency = str(currency).strip().upper()
    maturity = pd.to_datetime(maturity, utc=True).tz_localize(None)
    if pd.isna(maturity):
        raise ValueError("Bond maturity is missing")
    if currency not in OIS_LOOKUP:
        raise ValueError(f"Interest-rate curve is not configured for currency: {currency}")
    query = f"GET(maturity(), px_last()) FOR(curvemembers('{OIS_LOOKUP[currency]}'))"
    results = (executor or execute_bql)(
        query, requested_columns=("maturity", "PX_LAST"),
        field_values_only=True,
    ).copy()
    return interpolate_interest_rate(results, maturity)


def interpolate_interest_rate(results, maturity):
    """Interpolate sorted curve points, clamping outside the available dates."""
    results = results.copy()
    maturity = pd.to_datetime(maturity, utc=True).tz_localize(None)
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


EQUITY_FIELDS = {
    "PX_LAST": "px_last()",
    "CUR_MKT_CAP": "cur_mkt_cap()",
    "BS_ST_BORROW": "bs_st_borrow()",
    "BS_LT_BORROW": "bs_lt_borrow()",
    "VOLATILITY(CALC_INTERVAL=260D)": "volatility(calc_interval=260D)",
}


def get_options(ticker_name, maturity=None, today=None, *, executor=None):
    today = (pd.Timestamp.now(tz="UTC") if today is None else pd.to_datetime(today, utc=True)).tz_localize(None).normalize()
    start = (today + pd.Timedelta(days=10)).strftime("%Y-%m-%d")
    ticker_name = str(ticker_name).replace("\\", "\\\\").replace("'", "\\'")
    query = build_put_query(ticker_name, start)
    print(query, flush=True)
    execute = executor or execute_bql
    put_error = None
    try:
        puts = execute(query, requested_columns=(
            "NAME", "PUT_CALL", "EXPIRE_DT", "STRIKE_PX", "PX_BID", "PX_ASK",
            "PX_LAST", "#avg_volume", "OPEN_INT",
        ), field_values_only=True)
    except Exception as error:
        put_error = "no puts found" if is_no_results(error) else short_error(error)
        puts = pd.DataFrame(columns=["STRIKE_PX"])
    puts = puts.copy()
    if put_error:
        puts.attrs["put_error"] = put_error
    for field in EQUITY_FIELDS:
        puts[f"UNDERLYING_{field}"] = float("nan")
    puts["PUT_OTM_PERCENT"] = float("nan")
    try:
        equity = execute(
            f"get({', '.join(EQUITY_FIELDS.values())}) for('{ticker_name}')",
            requested_columns=tuple(EQUITY_FIELDS), field_values_only=True,
        )
        puts.attrs["equity"] = {f"UNDERLYING_{field}": equity.iloc[0].get(field, float("nan")) for field in EQUITY_FIELDS}
        for field in EQUITY_FIELDS:
            puts[f"UNDERLYING_{field}"] = equity.iloc[0].get(field, float("nan"))
        price = float(equity.iloc[0]["PX_LAST"])
        if not math.isfinite(price) or price <= 0:
            raise ValueError("Underlying price unavailable")
        puts["UNDERLYING_PX_LAST"] = price
        strikes = pd.to_numeric(puts["STRIKE_PX"], errors="coerce")
        puts["PUT_OTM_PERCENT"] = (price - strikes) / price * 100
    except Exception as error:
        puts["UNDERLYING_ERROR"] = short_error(error)
        puts.attrs["equity_error"] = short_error(error)
    return puts


def build_put_query(ticker_name, minimum_expiry):
    """Build the existing liquidity-screened put query for an escaped ticker."""
    return f"""
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
        and expire_dt() >= {minimum_expiry}
        and px_bid() > 0
        and px_ask() > 0
        and open_int() >= 100
        and #avg_volume >= 5
        and #relative_spread < 0.3
    ),
    1,
    -strike_px()
)
)
"""
