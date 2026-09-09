"""Generate synthetic bonds for local CSV development."""

import argparse
from pathlib import Path
import random

import pandas as pd


BQL_FIELD_MAP = [
    "SECURITY_DES", "BB_COMPOSITE", "PX_LAST", "CPN", "LONG_COMP_NAME",
    "MATURITY", "CRNCY", "CNV_PREM", "DELTA", "YLD_YTM_MID",
    "CNTRY_OF_RISK", "AMT_OUTSTANDING", "CONVERTIBLE", "SRCH_ASSET_CLASS",
]


def generate_bond_data(count: int = 10_000, seed: int | None = None) -> pd.DataFrame:
    """Return sample records; amounts use currency units, not millions."""
    if count < 0:
        raise ValueError("Row count cannot be negative")
    rng = random.Random(seed)
    records = []
    for index in range(count):
        convertible = rng.choice([True, False])
        records.append({
            "SECURITY_DES": f"Bond_{index + 1}",
            "BB_COMPOSITE": rng.choice(["AAA", "AA", "A", "BBB", "BB", "B", "CCC", "D", "NR"]),
            "PX_LAST": round(rng.uniform(90, 110), 2),
            "CPN": round(rng.uniform(0, 5), 2),
            "LONG_COMP_NAME": rng.choice(["Issuer_A", "Issuer_B", "Issuer_C", "Issuer_D"]),
            "MATURITY": f"{rng.randint(2025, 2035)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "CRNCY": rng.choice(["USD", "EUR", "GBP", "JPY"]),
            "CNV_PREM": round(rng.uniform(0, 100), 2) if convertible else None,
            "DELTA": round(rng.uniform(0, 1), 2) if convertible else None,
            "YLD_YTM_MID": round(rng.uniform(0, 5), 2),
            "CNTRY_OF_RISK": rng.choice(["US", "DE", "GB", "JP"]),
            "AMT_OUTSTANDING": round(rng.uniform(50, 500), 2) * 1_000_000,
            "CONVERTIBLE": "Y" if convertible else "N",
            "SRCH_ASSET_CLASS": "Corporates",
        })
    return pd.DataFrame.from_records(records, columns=BQL_FIELD_MAP)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--count", type=int, default=10_000)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("bond_data.csv"))
    args = parser.parse_args()
    generate_bond_data(args.count, args.seed).to_csv(args.output, index=False)


if __name__ == "__main__":
    main()
