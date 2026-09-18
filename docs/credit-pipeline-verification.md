# Credit-spread pipeline verification

## Tested locally

`tests/test_credit_pipeline.py` runs realistic per-field Bloomberg response tables
through the actual field extractor, rate interpolation, put/equity enrichment,
both calculation functions, and Qt completion handlers. Only the Bloomberg
transport is mocked. Both callback orders are exercised.

Scenarios cover valid data, no qualifying put, put request failure, invalid put
ask, missing market cap, and equity request failure. Each unavailable approach
has its own short message while the other approach retains its result.

Independent numerical expectations cover rate conversion, expiry year fractions,
annual probabilities, LGD weighting, percent/basis-point display, and Merton
calibration using equity values generated from known assets. A least-squares
fallback handles distressed cases where the initial root solver fails; residuals
must be finite and within tolerance before accepting a calibration.

## Live verification limit

A live equity BQL request on 2026-09-18 was rejected by Bloomberg:
“Monthly limits exceeded, request is blocked.” Therefore live field availability,
units, currencies and model outputs remain unverified.

## Current model assumptions

- Both displayed spreads are the requested LGD times one-year probability, not
  independently calibrated market bond spreads.
- Merton calibrates at bond maturity. Its maturity probability is converted to
  a one-year equivalent using a constant default-intensity assumption. This is
  not a separate Merton calibration at one year.
- Market cap and both debt fields must use the same monetary scale and currency.
  The current request uses field defaults; these need checking in Bloomberg.
- Volatility is an annualised decimal, as confirmed by the user; it is passed
  directly to Merton and formatted as a percentage only for display.
- The interpolated curve quote is treated as an annual effective percentage for
  the requested log conversion. The same bond-maturity rate is used for the put;
  curve quote conventions and any requirement for a put-tenor rate remain model
  assumptions rather than verified market conventions.
- The put query chooses the lowest strike satisfying expiry/liquidity filters;
  it reports OTM percentage but does not impose an OTM threshold.

The Merton calibration equations were cross-checked against the
[MathWorks Merton reference](https://www.mathworks.com/help/risk/mertonmodel.html).
The debt threshold `ST + 0.5 * LT` and LGD-weighted annual probability follow this
application's specified formulas.
