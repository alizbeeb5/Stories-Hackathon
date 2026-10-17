"""Person 2 - Baskets & product mix: re-price every branch's purchases with ONE common price-and-cost list.
Reference = chain-wide average list price and unit cost per product (same for all branches).
Discounts are removed (list prices), so only WHAT was bought differs between branches.
Sensitivity: repeat with Harbour's and Uptown's price/cost list as the reference."""
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
R, G, P, C = "Line Revenue (USD)", "Line Gross Profit (USD)", "Unit Price (USD)", "Unit Cost (USD)"
ntx = df.groupby("Branch")["Transaction ID"].nunique()

def at_reference(price, cost):
    d = df.assign(rp=df.Product.map(price), rc=df.Product.map(cost))
    rev = (d.Quantity * d.rp).groupby(d.Branch).sum()
    gp = (d.Quantity * (d.rp - d.rc)).groupby(d.Branch).sum()
    return gp / ntx, gp / rev * 100

w = df.Quantity
chain_price = (df[P] * w).groupby(df.Product).sum() / w.groupby(df.Product).sum()
chain_cost = (df[C] * w).groupby(df.Product).sum() / w.groupby(df.Product).sum()
actual_gptx = df.groupby("Branch")[G].sum() / ntx
actual_margin = df.groupby("Branch")[G].sum() / df.groupby("Branch")[R].sum() * 100

rows = {"Actual (own prices, costs, discounts)": (actual_gptx, actual_margin),
        "Common reference: chain-average list": at_reference(chain_price, chain_cost)}
for ref in ("Harbour", "Uptown"):
    s = df[df.Branch == ref]
    rows[f"Common reference: {ref} list"] = at_reference(s.groupby("Product")[P].mean(), s.groupby("Product")[C].mean())

out = []
for name, (gptx, m) in rows.items():
    out.append({"scenario": name, **{f"GP/basket {b}": gptx[b] for b in gptx.index},
                **{f"margin% {b}": m[b] for b in m.index},
                "Garden gap vs Harbour $": gptx["Harbour"] - gptx["Garden"],
                "Garden gap vs Uptown $": gptx["Uptown"] - gptx["Garden"]})
out = pd.DataFrame(out).set_index("scenario").round(2)
out.to_csv("out/04_common_price_reference.csv")
print(out.T.to_string())
act = out.iloc[0]; com = out.iloc[1]
for b in ("Harbour", "Uptown"):
    a, c = act[f"Garden gap vs {b} $"], com[f"Garden gap vs {b} $"]
    print(f"vs {b}: actual gap {a:.2f}; gap due to what customers buy {c:.2f} ({c/a*100:.0f}% of actual); "
          f"gap due to branch prices/costs/discounts {a-c:.2f} ({(a-c)/a*100:.0f}%)")
