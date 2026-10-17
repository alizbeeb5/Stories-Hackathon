"""Person 2 - Baskets & product mix: common basket types, order type, and months. Sample sizes = distinct transactions."""
import pandas as pd
pd.set_option("display.width", 220, "display.max_columns", 30)
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
df["month"] = df.Date.str[:7]
b = df.groupby("Transaction ID").agg(branch=("Branch", "first"), otype=("Order Type", "first"), month=("month", "first"),
                                      btype=("Category", lambda s: " + ".join(sorted(s))), rev=(R, "sum"), gp=(G, "sum"))

def table(key, top=None):
    t = b.groupby([key, "branch"]).agg(n=("gp", "size"), gp=("gp", "mean"), rev=("rev", "sum"), gps=("gp", "sum"))
    t["margin"] = t.gps / t.rev * 100
    t["share"] = t.n / b.groupby("branch").size().reindex(t.index.get_level_values(1)).values * 100
    w = t[["n", "share", "gp", "margin"]].unstack("branch")
    if top:
        w = w.loc[b[key].value_counts().index[:top]]
    w[("gap", "H-G $")] = w[("gp", "Harbour")] - w[("gp", "Garden")]
    w[("gap", "U-G $")] = w[("gp", "Uptown")] - w[("gp", "Garden")]
    return w.round(2)

bt = table("btype", top=10); bt.to_csv("out/05_basket_types.csv")
mo = table("month"); mo.to_csv("out/05_months.csv")
ot = table("otype"); ot.to_csv("out/05_order_type.csv")
for name, t in [("BASKET TYPES (top 10)", bt), ("MONTHS", mo), ("ORDER TYPE", ot)]:
    print("\n==", name); print(t.to_string())
print("\nbasket types where Garden is NOT lowest GP/basket:",
      (bt[("gp", "Garden")] >= bt[[("gp", "Harbour"), ("gp", "Uptown")]].min(axis=1)).sum(), "of", len(bt))
