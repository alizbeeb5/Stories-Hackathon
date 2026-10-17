"""Person 2 - Baskets & product mix: exact matched-basket comparison.

Basket signature = sorted product names with SUMMED quantities per product within the transaction,
e.g. "Butter Croissant x1 | Iced Latte x1". Only signatures that appear in BOTH Garden and the comparison
branch are used. The comparison branch's GP per basket is re-weighted to Garden's signature counts, so both
sides describe exactly the same set of purchases. Discounts are kept as recorded (a variant restricted to
undiscounted transactions is also reported). Sensitivity: rerun after removing exact repeated lines.
"""
import pandas as pd
from _shared import *

pd.set_option("display.width", 220, "display.max_columns", 20)
raw = load()


def baskets(d):
    q = d.groupby(["Transaction ID", "Product"])["Quantity"].sum().reset_index()
    sig = q.sort_values("Product").groupby("Transaction ID").apply(
        lambda g: " | ".join(f"{p} x{n}" for p, n in zip(g.Product, g.Quantity)), include_groups=False)
    return d.groupby("Transaction ID").agg(branch=("Branch", "first"), gp=(G, "sum"),
                                           discounted=(D, lambda s: (s > 0).any())).join(sig.rename("sig"))


def compare(b, target, label):
    ntot = b.branch.value_counts()
    g, t = b[b.branch == "Garden"], b[b.branch == target]
    common = set(g.sig) & set(t.sig)
    gm, tm = g[g.sig.isin(common)], t[t.sig.isin(common)]
    g_by = gm.groupby("sig").gp.agg(["size", "mean"])
    t_by = tm.groupby("sig").gp.mean()
    t_reweighted = (g_by["size"] * t_by.reindex(g_by.index)).sum() / g_by["size"].sum()
    g_mean = gm.gp.mean()
    return {"comparison": f"Garden vs {target}", "variant": label,
            "matched_signatures": len(common),
            "Garden_transactions": len(gm), "Garden_coverage_%": len(gm) / ntot["Garden"] * 100,
            f"target_transactions": len(tm), "target_coverage_%": len(tm) / ntot[target] * 100,
            "Garden_GP_per_basket_$": g_mean, "target_GP_per_basket_same_mix_$": t_reweighted,
            "matched_gap_$": t_reweighted - g_mean,
            "signatures_where_Garden_lower_%": (g_by["mean"] < t_by.reindex(g_by.index)).mean() * 100}


rows = []
dedup = raw.drop_duplicates()
for label, d in [("all lines", raw), ("exact repeated lines removed", dedup)]:
    b = baskets(d)
    for target in ["Harbour", "Uptown"]:
        rows.append(compare(b, target, label))
        rows.append(compare(b[~b.discounted], target, label + ", undiscounted transactions only"))
out = pd.DataFrame(rows).set_index(["comparison", "variant"]).sort_index()
out.round(2).to_csv("out/09_matched_baskets.csv")
print(out.round(2).to_string())
print("\nrepeated lines removed:", len(raw) - len(dedup))

# top 10 matched signatures (all lines, by Garden count) for the report
b = baskets(raw)
top = []
for target in ["Harbour", "Uptown"]:
    g, t = b[b.branch == "Garden"], b[b.branch == target]
    common = set(g.sig) & set(t.sig)
    gg = g[g.sig.isin(common)].groupby("sig").gp.agg(["size", "mean"])
    tt = t[t.sig.isin(common)].groupby("sig").gp.agg(["size", "mean"])
    j = gg.join(tt, lsuffix="_Garden", rsuffix=f"_{target}")
    j["comparison"] = target
    top.append(j.sort_values("size_Garden", ascending=False).head(10))
top = pd.concat(top)
top.round(2).to_csv("out/09_top_matched_signatures.csv")
print(top.round(2).to_string())
