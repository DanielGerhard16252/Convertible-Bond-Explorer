"""Generate complete, explicitly synthetic bond and option CSV fixtures.

Run python -m data.search_demo_generation to regenerate the demo files.
The FX factors below are arbitrary simulation inputs, not market rates.
"""

from pathlib import Path
import random

import pandas as pd

from data.data_generation import generate_bond_data
from shared.bics import BICS_LEVEL_2_VALUES
from shared.search_choices import PAYMENT_RANK_VALUES


def generate_search_demo(count=1000, seed=42):
    rng = random.Random(seed)
    bonds = generate_bond_data(count, seed)
    bonds = bonds.rename(columns={"CNV_PREM": "CV_PCT_PREMIUM", "YLD_YTM_MID": "YIELD(YIELD_TYPE=YTM)"})
    options = []
    extras = []
    for index, row in bonds.iterrows():
        convertible = row["CONVERTIBLE"] == "Y"
        conversion_price = round(rng.uniform(20, 200), 4) if convertible else None
        isin_base = f"XS{index + 1:09d}"
        digits = "".join(str(int(ch, 36)) for ch in isin_base)
        total = sum((int(ch) * 2 // 10 + int(ch) * 2 % 10) if i % 2 == 0 else int(ch)
                    for i, ch in enumerate(reversed(digits)))
        isin = isin_base + str((-total) % 10)
        ticker = f"DEMO{index + 1} US Equity" if convertible else None
        extra = {
            "ID": f"{isin} Corp", "ID_ISIN": isin,
            "SECURITY_TYP": "Convertible" if convertible else "Bond",
            "CLASSIFICATION_NAME(BICS,2)": BICS_LEVEL_2_VALUES[index % len(BICS_LEVEL_2_VALUES)],
            "PAYMENT_RANK": PAYMENT_RANK_VALUES[index % len(PAYMENT_RANK_VALUES)],
            "YIELD(YIELD_TYPE=YTW)": round(row["YIELD(YIELD_TYPE=YTM)"] - rng.uniform(0, 1), 3),
            "CV_COMMON_TICKER_EXCH": ticker,
            "CAST_PARENT_EQUITY_TICKER": f"DEMO{index + 1} US Equity",
            "CV_CNVS_PX": conversion_price,
            "CV_CNVS_RATIO": 1000 / conversion_price if convertible else None,
            "PARITY": row["PX_LAST"] / (1 + row["CV_PCT_PREMIUM"] / 100) if convertible else None,
            "AMT_OUTSTANDING_USD": row["AMT_OUTSTANDING"] * {"USD": 1, "EUR": 1.1, "GBP": 1.3, "JPY": .007}[row["CRNCY"]],
            "DATA_SOURCE": "SYNTHETIC DEMO - not market data",
        }
        if not convertible and index % 5 == 0:
            bonds.loc[index, "SRCH_ASSET_CLASS"] = "Governments"
        extras.append(extra)
        if convertible:
            for offset, strike_factor in [(-180, .95), (30, 1), (365, 1.05)]:
                options.append({
                    "ID": f"DEMO_OPTION_{index + 1}_{offset}", "TICKER": ticker,
                    "NAME": f"Demo {index + 1} call {offset}", "PUT_CALL": "Call",
                    "EXPIRE_DT": (pd.Timestamp(row["MATURITY"]) + pd.Timedelta(days=offset)).date(),
                    "STRIKE_PX": conversion_price * strike_factor,
                    "PX_LAST": round(rng.uniform(1, 20), 4), "IVOL": round(rng.uniform(10, 60), 4),
                })
    return pd.concat([bonds, pd.DataFrame(extras)], axis=1), pd.DataFrame(options)


if __name__ == "__main__":
    bonds, options = generate_search_demo()
    directory = Path(__file__).resolve().parent
    bonds.to_csv(directory / "search_demo.csv", index=False)
    options.to_csv(directory / "option_demo.csv", index=False)
