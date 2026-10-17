"""Person 2 - Baskets & product mix: situations where Garden performs relatively well, and whether they persist month by month.
Candidates tested:
  A. Dessert demand: share of baskets containing a dessert, and dessert-only baskets.
  B. Revenue per basket vs Uptown (customers spend more at Garden than at Uptown).
  C. Purchase value at a COMMON price-and-cost list: is Garden's basket mix as profitable as the others'?
  D. Total gross profit vs Uptown (volume).
Sample sizes = distinct transactions per branch-month."""
import pandas as pd
import sys, os
pd.set_option("display.width", 220, "display.max_columns", 30)
HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [os.path.join(HERE, "data", "stories_transactions.csv"), os.path.join(HERE, "..", "data", "stories_transactions.csv"),
              os.path.join(HERE, "stories_transactions.csv")]
DATA = sys.argv[1] if len(sys.argv) > 1 else next((p for p in CANDIDATES if os.path.exists(p)), CANDIDATES[0])
os.makedirs("out", exist_ok=True)
df = pd.read_csv(DATA)
R, G, P, C = "Line Revenue (USD)", "Line Gross Profit (USD)", "Unit Price (USD)", "Unit Cost (USD)"
df["month"] = df.Date.str[:7]

# common reference (chain-average list price and cost per product, no discounts)
w = df.Quantity
ref_p = (df[P] * w).groupby(df.Product).sum() / w.groupby(df.Product).sum()
ref_c = (df[C] * w).groupby(df.Product).sum() / w.groupby(df.Product).sum()
df["ref_gp"] = df.Quantity * (df.Product.map(ref_p) - df.Product.map(ref_c))

b = df.groupby("Transaction ID").agg(branch=("Branch", "first"), month=("month", "first"), rev=(R, "sum"), gp=(G, "sum"),
                                      ref_gp=("ref_gp", "sum"),
                                      has_dessert=("Category", lambda s: (s == "Desserts").any()),
                                      dessert_only=("Category", lambda s: (s == "Desserts").all()))
m = b.groupby(["month", "branch"]).agg(baskets=("gp", "size"), dessert_baskets_pct=("has_dessert", "mean"),
                                        dessert_only_pct=("dessert_only", "mean"), rev_per_basket=("rev", "mean"),
                                        ref_gp_per_basket=("ref_gp", "mean"), total_gp=("gp", "sum"))
m[["dessert_baskets_pct", "dessert_only_pct"]] *= 100
wide = m.unstack("branch").round(2)
wide.to_csv("out/06_where_garden_does_well_by_month.csv")

def months_true(cond):
    return f"{int(cond.sum())} of {len(cond)} months"

tests = pd.DataFrame([
    ["A. Garden has the highest share of baskets with a dessert",
     months_true(wide.dessert_baskets_pct.idxmax(axis=1) == "Garden"),
     f"Garden {wide.dessert_baskets_pct.Garden.min():.1f}-{wide.dessert_baskets_pct.Garden.max():.1f}% vs Harbour "
     f"{wide.dessert_baskets_pct.Harbour.min():.1f}-{wide.dessert_baskets_pct.Harbour.max():.1f}%, Uptown "
     f"{wide.dessert_baskets_pct.Uptown.min():.1f}-{wide.dessert_baskets_pct.Uptown.max():.1f}%"],
    ["A2. Garden has the highest share of dessert-only baskets",
     months_true(wide.dessert_only_pct.idxmax(axis=1) == "Garden"),
     f"Garden {wide.dessert_only_pct.Garden.min():.1f}-{wide.dessert_only_pct.Garden.max():.1f}% vs Harbour "
     f"{wide.dessert_only_pct.Harbour.min():.1f}-{wide.dessert_only_pct.Harbour.max():.1f}%, Uptown "
     f"{wide.dessert_only_pct.Uptown.min():.1f}-{wide.dessert_only_pct.Uptown.max():.1f}%"],
    ["B. Garden revenue per basket > Uptown",
     months_true(wide.rev_per_basket.Garden > wide.rev_per_basket.Uptown),
     f"avg gap +${(wide.rev_per_basket.Garden - wide.rev_per_basket.Uptown).mean():.2f} per basket"],
    ["C. At a common price/cost list, Garden's baskets earn >= Harbour's",
     months_true(wide.ref_gp_per_basket.Garden >= wide.ref_gp_per_basket.Harbour),
     f"Garden ${wide.ref_gp_per_basket.Garden.mean():.2f} vs Harbour ${wide.ref_gp_per_basket.Harbour.mean():.2f} "
     f"vs Uptown ${wide.ref_gp_per_basket.Uptown.mean():.2f} (avg)"],
    ["D. Garden total gross profit > Uptown",
     months_true(wide.total_gp.Garden > wide.total_gp.Uptown),
     f"Garden ${wide.total_gp.Garden.sum():,.0f} vs Uptown ${wide.total_gp.Uptown.sum():,.0f} (H1)"],
], columns=["candidate", "holds in", "evidence"]).set_index("candidate")
tests.to_csv("out/06_where_garden_does_well_tests.csv")
print(tests.to_string())
print("\nBaskets per month (sample sizes):\n", wide.baskets.to_string())
print("\nDessert baskets % by month:\n", wide.dessert_baskets_pct.to_string())
print("\nCommon-reference GP per basket by month:\n", wide.ref_gp_per_basket.to_string())
