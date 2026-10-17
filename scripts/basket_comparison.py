"""Person 2 - Baskets & product mix: rebuild baskets (1 basket = 1 distinct Transaction ID) and compare branches.
Rows are product lines. Repeated lines are kept (not deleted). Margin = total GP / total revenue."""
import pandas as pd
pd.set_option("display.width", 200, "display.max_columns", 30)
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

b = df.groupby("Transaction ID").agg(branch=("Branch", "first"), lines=("Product", "size"),
                                      items=("Quantity", "sum"), revenue=(R, "sum"), gp=(G, "sum"))
t = b.groupby("branch").agg(baskets=("lines", "size"), avg_items=("items", "mean"), avg_lines=("lines", "mean"),
                             avg_basket_value=("revenue", "mean"), avg_gp_per_basket=("gp", "mean"),
                             total_revenue=("revenue", "sum"), total_gp=("gp", "sum"))
t["margin_%"] = t.total_gp / t.total_revenue * 100
for k in (1, 2, 3):
    t[f"share_{k}_line_baskets_%"] = b.groupby("branch").lines.apply(lambda s: (s == k).mean() * 100)
t["repeated_lines_kept"] = df[df.duplicated()].groupby("Branch").size()
t.round(2).to_csv("out/01_basket_comparison.csv")
print(t.round(2).T)

mix = pd.crosstab(df.Category, df.Branch, values=df.Quantity, aggfunc="sum", normalize="columns") * 100
mix.round(1).to_csv("out/01_category_mix_units_pct.csv")
print("\nCategory mix (% of units)\n", mix.round(1))
