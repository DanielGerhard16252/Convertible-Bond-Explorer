import pandas as pd
import random

df = pd.DataFrame(columns=["Bond_Name", "Rating", "Price", "Coupon", "Issuer"])

for i in range(1000):
    bond_name = f"Bond_{i+1}"
    rating = random.choice(["AAA", "AA" , "A", "BBB", "BB", "B", "CCC"])
    price = round(random.uniform(90, 110), 2)
    coupon = round(random.uniform(0, 5), 2)
    issuer = random.choice(["Issuer_A", "Issuer_B", "Issuer_C", "Issuer_D"])
    
    df.loc[len(df)] = {"Bond_Name": bond_name, "Rating": rating, "Price": price, "Coupon": coupon, "Issuer": issuer}

df.to_csv("data/bond_data.csv", index=False)