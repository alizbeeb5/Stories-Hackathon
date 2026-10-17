"""Person 2 - Baskets & product mix: demand by order type (Dine-in vs Takeaway), counted as distinct transactions."""
import pandas as pd
pd.set_option("display.width", 200)
import sys, os
# Usage: python <script>.py [path/to/stories_transactions.csv]
# Default: looks for data/stories_transactions.csv in the repo (or next to the script).
HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [os.path.join(HERE, "data", "stories_transactions.csv"), os.path.join(HERE, "..", "data", "stories_transactions.csv"),
              os.path.join(HERE, "stories_transactions.csv")]
DATA = sys.argv[1] if len(sys.argv) > 1 else next((p for p in CANDIDATES if os.path.exists(p)), CANDIDATES[0])
os.makedirs("out", exist_ok=True)
df = pd.read_csv(DATA)
R, G = "Line Revenue (USD)", "Line Gross Profit (USD)"
# check: each transaction has exactly one order type
assert df.groupby("Transaction ID")["Order Type"].nunique().max() == 1
b = df.groupby("Transaction ID").agg(branch=("Branch", "first"), otype=("Order Type", "first"),
                                      items=("Quantity", "sum"), revenue=(R, "sum"), gp=(G, "sum"))
t = b.groupby(["branch", "otype"]).agg(baskets=("items", "size"), avg_items=("items", "mean"),
                                        avg_basket_value=("revenue", "mean"), avg_gp_per_basket=("gp", "mean"),
                                        total_revenue=("revenue", "sum"), total_gp=("gp", "sum"))
t["share_of_branch_baskets_%"] = t.baskets / t.groupby(level=0).baskets.transform("sum") * 100
t["margin_%"] = t.total_gp / t.total_revenue * 100
t = t.drop(columns=["total_revenue", "total_gp"]).round(2)
t.to_csv("out/02_order_type_demand.csv")
print(t)
