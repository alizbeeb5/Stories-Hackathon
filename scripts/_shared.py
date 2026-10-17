"""Shared helpers for scripts 08-11 (Person 2 - Baskets & product mix)."""
import sys, os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
CANDIDATES = [os.path.join(HERE, "data", "stories_transactions.csv"), os.path.join(HERE, "..", "data", "stories_transactions.csv"),
              os.path.join(HERE, "stories_transactions.csv")]
R, G, P, C, D = "Line Revenue (USD)", "Line Gross Profit (USD)", "Unit Price (USD)", "Unit Cost (USD)", "Discount Rate"
FACTORS = ["costs", "list_prices", "discounts", "units_per_basket", "product_mix"]
LABELS = {"costs": "Recorded unit costs", "list_prices": "List prices", "discounts": "Realized discounts",
          "units_per_basket": "Units per basket", "product_mix": "Product mix"}


def load(path=None):
    path = path or (sys.argv[1] if len(sys.argv) > 1 else next((p for p in CANDIDATES if os.path.exists(p)), CANDIDATES[0]))
    os.makedirs("out", exist_ok=True)
    return pd.read_csv(path)


def factors(d):
    """GP/transaction = units_per_basket * sum_p mix_p * (price_p * (1 - disc_p) - cost_p).
    disc_p is the unit-weighted realized discount rate, so the identity reproduces actual GP exactly
    (up to cent rounding of the recorded line values)."""
    u = d.groupby("Product")["Quantity"].sum()
    return {
        "costs": d.groupby("Product")[C].mean(),
        "list_prices": d.groupby("Product")[P].mean(),
        "discounts": (d["Quantity"] * d[D]).groupby(d["Product"]).sum() / u,
        "units_per_basket": d["Quantity"].sum() / d["Transaction ID"].nunique(),
        "product_mix": u / u.sum(),
    }


def gp_per_tx(f):
    unit_gp = f["list_prices"] * (1 - f["discounts"]) - f["costs"]
    return f["units_per_basket"] * (f["product_mix"] * unit_gp).sum()


def sequential(start, end, order):
    """Swap factors from `start` to `end` one at a time in `order`; return each step's change."""
    cur, out = dict(start), {}
    prev = gp_per_tx(cur)
    for k in order:
        cur[k] = end[k]
        now = gp_per_tx(cur)
        out[k] = now - prev
        prev = now
    return out
