"""Credit calculations with decimal probabilities and percentage rate inputs."""

from dataclasses import dataclass
import math
from scipy.optimize import root, least_squares
from scipy.stats import norm

import pandas as pd

def calculate_default_probability(q, put_years, horizon_years=1.0):
    if not all(math.isfinite(value) for value in (q, put_years, horizon_years)):
        raise ValueError("Default probability inputs must be finite")
    if not 0 <= q < 1 or put_years <= 0 or horizon_years < 0:
        raise ValueError("Requires 0 <= q < 1, positive put horizon and nonnegative probability horizon")
    y = -math.log1p(-q) / put_years
    return -math.expm1(-y * horizon_years)


@dataclass(frozen=True)
class CreditMetrics:
    put_years: float
    continuous_rate: float
    ask: float
    strike: float
    q: float
    default_intensity: float
    default_probability: float
    spread: float


def calculate_credit_metrics(ask, rate_percent, expiry, lgd, strike, today=None):
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
    probability = calculate_default_probability(q, years)
    return CreditMetrics(years, rate, float(ask), strike, q, -math.log1p(-q) / years, probability, probability * lgd)


def calculate_approximate_spread(ask, rate_percent, expiry, lgd, strike, today=None):
    return calculate_credit_metrics(ask, rate_percent, expiry, lgd, strike, today).spread


def merton(E, ST, LT, r, T, vol):
    if not all(math.isfinite(float(value)) for value in (E, ST, LT, r, T, vol)):
        raise ValueError("Merton inputs are missing or invalid")
    if E <= 0 or ST < 0 or LT < 0 or T <= 0 or vol <= 0:
        raise ValueError("Merton inputs must have positive equity, horizon and volatility")
    D = ST + 0.5 * LT
    if D <= 0:
        raise ValueError("Merton debt must be positive")

    def merton_equations(x):
        V, sigma_V = (math.exp(value) for value in x)

        d1 = (math.log(V / D) + (r + 0.5 * sigma_V**2) * T) / (sigma_V * math.sqrt(T))

        d2 = d1 - sigma_V * math.sqrt(T)

        eq1 = (V * norm.cdf(d1) - D * math.exp(-r * T) * norm.cdf(d2) - E) / E

        eq2 = ((V / E) * norm.cdf(d1) * sigma_V - vol)

        return [eq1, eq2]

    initial_guess = [math.log(E + D), math.log(vol * E / (E + D))]

    def calibrated(solution):
        residuals = merton_equations(solution.x)
        return solution.success and all(math.isfinite(value) and abs(value) <= 1e-6 for value in residuals)

    try:
        solution = root(merton_equations, initial_guess)
        valid = calibrated(solution)
    except (OverflowError, ValueError, ZeroDivisionError):
        valid = False
    if not valid:
        # A damped solver is more reliable for distressed, low-equity firms.
        solution = least_squares(merton_equations, initial_guess, max_nfev=2000,
                                 xtol=1e-12, ftol=1e-12, gtol=1e-12)
    if not calibrated(solution):
        raise ValueError("Merton calibration failed")
    V, sigma_V = (math.exp(value) for value in solution.x)
    d1 = (math.log(V / D) + (r + 0.5 * sigma_V**2) * T) / (sigma_V * math.sqrt(T))
    d2 = d1 - sigma_V * math.sqrt(T)
    return norm.cdf(-d2)


def calculate_merton_spread(equity, short_debt, long_debt, rate_percent,
                            maturity, volatility, lgd, today=None):
    """Return annual PD and spread; volatility is decimal, rate is percent."""
    today = pd.Timestamp.now(tz="UTC").normalize() if today is None else pd.to_datetime(today, utc=True)
    years = (pd.to_datetime(maturity, utc=True) - today).total_seconds() / (365 * 24 * 3600)
    if not math.isfinite(float(lgd)) or not 0 <= lgd <= 1:
        raise ValueError("LGD must be between zero and one")
    probability = float(merton(float(equity), float(short_debt), float(long_debt),
                               math.log1p(float(rate_percent) / 100), years,
                               float(volatility)))
    annual_pd = 1.0 if probability == 1 else -math.expm1(math.log1p(-probability) / years)
    return annual_pd, annual_pd * lgd
