"""Person 2 - Baskets & product mix: robustness of the decomposition.

A. Signed purchasing-pattern effect: every branch's purchases valued at ONE common list (list prices, no
   discounts). Garden minus comparison > 0 means Garden's purchase mix is MORE profitable. Repeated with the
   Harbour, Uptown and chain-average lists.
B. Declared-order decomposition (costs -> prices -> discounts -> units -> mix) recomputed within each month,
   each order type, and with exact repeated lines removed.
All results are accounting comparisons, not causal effects.
"""
import pandas as pd
from _shared import *

pd.set_option("display.width", 240, "display.max_columns", 30)
df = load()
BR = ["Garden", "Harbour", "Uptown"]

# A. signed mix effect at common reference lists
w = df.Quantity
refs = {"Chain-average list": ((df[P] * w).groupby(df.Product).sum() / w.groupby(df.Product).sum(),
                               (df[C] * w).groupby(df.Product).sum() / w.groupby(df.Product).sum())}
for b in ["Harbour", "Uptown", "Garden"]:
    s = df[df.Branch == b]
    refs[f"{b} list"] = (s.groupby("Product")[P].mean(), s.groupby("Product")[C].mean())
ntx = df.groupby("Branch")["Transaction ID"].nunique()
ra = []
for name, (pr, co) in refs.items():
    g = (df.Quantity * (df.Product.map(pr) - df.Product.map(co))).groupby(df.Branch).sum() / ntx
    ra.append({"reference list": name, **{f"GP/basket {b} $": g[b] for b in BR},
               "Garden minus Harbour $": g["Garden"] - g["Harbour"], "Garden minus Uptown $": g["Garden"] - g["Uptown"]})
ra = pd.DataFrame(ra).set_index("reference list")
ra.round(3).to_csv("out/10_common_reference_signed.csv")
print(ra.round(3).to_string())


# B. decomposition stability
def decomp(d):
    out = {}
    F = {b: factors(d[d.Branch == b]) for b in BR}
    o = d.groupby("Branch")[G].sum() / d.groupby("Branch")["Transaction ID"].nunique()
    for t in ["Harbour", "Uptown"]:
        s = sequential(F["Garden"], F[t], FACTORS)
        out[f"{t}: gap $"] = o[t] - o["Garden"]
        for k in FACTORS:
            out[f"{t}: {LABELS[k]} $"] = s[k]
        out[f"{t}: cost share %"] = s["costs"] / (o[t] - o["Garden"]) * 100
    return out

rb = [{"slice": "All Jan-Jun (baseline)", "Garden transactions": ntx["Garden"], **decomp(df)}]
for m, d in df.groupby(df.Date.str[:7]):
    rb.append({"slice": m, "Garden transactions": d[d.Branch == "Garden"]["Transaction ID"].nunique(), **decomp(d)})
for ot, d in df.groupby("Order Type"):
    rb.append({"slice": ot, "Garden transactions": d[d.Branch == "Garden"]["Transaction ID"].nunique(), **decomp(d)})
dd = df.drop_duplicates()
rb.append({"slice": "Exact repeated lines removed", "Garden transactions": dd[dd.Branch == "Garden"]["Transaction ID"].nunique(), **decomp(dd)})
rb = pd.DataFrame(rb).set_index("slice")
rb.round(3).to_csv("out/10_decomposition_stability.csv")
cols = [c for c in rb.columns if any(x in c for x in ["gap", "Recorded", "List prices", "Product mix", "cost share", "Garden transactions"])]
print(rb[cols].round(2).to_string())
summary = pd.DataFrame({
    "min": rb.drop(index="All Jan-Jun (baseline)")[cols[1:]].min(),
    "max": rb.drop(index="All Jan-Jun (baseline)")[cols[1:]].max()}).round(2)
summary.to_csv("out/10_stability_range.csv")
print(summary.to_string())
