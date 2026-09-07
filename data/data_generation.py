import pandas as pd
import random

BQL_FIELD_MAP = [
    "SECURITY_DES",
    "BB_COMPOSITE",
    "PX_LAST",
    "CPN",
    "LONG_COMP_NAME",
    "MATURITY",
    "CRNCY",
    "CNV_PREM",
    "DELTA",
    "YLD_YTM_MID",
    "CNTRY_OF_RISK",
    "AMT_OUTSTANDING",
    "CONVERTIBLE",
    "SRCH_ASSET_CLASS",
]


df = pd.DataFrame(columns=BQL_FIELD_MAP)

for i in range(10000):
    bond_name = f"Bond_{i+1}"
    convertible = random.choice([True, False])
    rating = random.choice(["AAA", "AA" , "A", "BBB", "BB", "B", "CCC", "D", "NR"])
    price = round(random.uniform(90, 110), 2)
    coupon = round(random.uniform(0, 5), 2)
    issuer = random.choice(["Issuer_A", "Issuer_B", "Issuer_C", "Issuer_D"])
    maturity = f"{random.randint(2025, 2035)}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    currency = random.choice(["USD", "EUR", "GBP", "JPY"])
    country = random.choice(["US", "DE", "GB", "JP"])
    amt_outstanding = round(random.uniform(50, 500), 2)  # in USD millions
    delta = None
    conversion_premium = None
    conversion_ratio = None
    conversion_price = None
    if convertible:
        delta = round(random.uniform(0, 1), 2)
        conversion_premium = round(random.uniform(0, 100), 2)
        conversion_ratio = round(random.uniform(0, 100), 2)
        conversion_price = round(random.uniform(0, 100), 2)
    yield_to_maturity = round(random.uniform(0, 5), 2)

    
    df.loc[len(df)] = [
        bond_name,
        rating,
        price,
        coupon,
        issuer,
        maturity,
        currency,
        conversion_premium,
        delta,
        conversion_ratio,
        conversion_price,
        yield_to_maturity,
        country,
    ]

df.to_csv("data/bond_data.csv", index=False)
