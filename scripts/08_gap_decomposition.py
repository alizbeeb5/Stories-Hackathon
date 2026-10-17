"""Person 2 - Baskets & product mix: exact decomposition of Garden's gross-profit-per-transaction gap.

Identity:  GP per transaction = units_per_basket x sum_p [ mix_p x ( list_price_p x (1 - discount_p) - cost_p ) ]

Starting from Garden's observed GP per transaction, Garden's factors are replaced one at a time by the
comparison branch's factors, in a DECLARED order:
    Recorded costs -> list prices -> realized discounts -> units per basket -> product mix
Each step's change is that factor's contribution. The steps end exactly at the comparison branch's GP per
transaction; a rounding line (cent rounding of recorded line values) closes the difference to the observed gap.
The same is repeated in REVERSE order (mix -> units -> discounts -> prices -> costs), and the average over all
120 orders (Shapley) is reported as a check. Contributions are accounting comparisons, not causal effects;
their sizes depend on the comparison method and order.

Part 2: Total gross profit = transactions x gross profit per transaction (volume vs basket profitability).
"""
import itertools, math
import pandas as pd
from _shared import *

pd.set_option("display.width", 220, "display.max_columns", 20)
df = load()
ntx = df.groupby("Branch")["Transaction ID"].nunique()
obs = df.groupby("Branch")[G].sum() / ntx                       # observed GP per transaction
F = {b: factors(df[df.Branch == b]) for b in ["Garden", "Harbour", "Uptown"]}
FWD, REV = FACTORS, FACTORS[::-1]

rows = []
for target in ["Harbour", "Uptown"]:
    gap = obs[target] - obs["Garden"]
    fwd = sequential(F["Garden"], F[target], FWD)
    rev = sequential(F["Garden"], F[target], REV)
    shap = dict.fromkeys(FACTORS, 0.0)
    for o in itertools.permutations(FACTORS):
        for k, v in sequential(F["Garden"], F[target], o).items():
            shap[k] += v / math.factorial(5)
    rounding = gap - sum(fwd.values())
    for k in FACTORS:
        rows.append({"comparison": f"Garden -> {target}", "component": LABELS[k],
                     "declared_order_$": fwd[k], "share_of_gap_%": fwd[k] / gap * 100,
                     "reverse_order_$": rev[k], "all_orders_average_$": shap[k]})
    rows.append({"comparison": f"Garden -> {target}", "component": "Cent rounding of recorded lines",
                 "declared_order_$": rounding, "share_of_gap_%": rounding / gap * 100,
                 "reverse_order_$": gap - sum(rev.values()), "all_orders_average_$": gap - sum(shap.values())})
    rows.append({"comparison": f"Garden -> {target}", "component": "TOTAL = observed gap",
                 "declared_order_$": gap, "share_of_gap_%": 100.0, "reverse_order_$": gap, "all_orders_average_$": gap})
    # reconciliation checks
    assert abs(sum(fwd.values()) + rounding - gap) < 1e-12
    assert abs(gp_per_tx(F["Garden"]) + sum(fwd.values()) - gp_per_tx(F[target])) < 1e-9
    print(f"Garden {obs['Garden']:.4f} -> {target} {obs[target]:.4f}: gap {gap:.4f}, "
          f"formula gap {gp_per_tx(F[target]) - gp_per_tx(F['Garden']):.4f}, rounding {rounding:.5f}")

dec = pd.DataFrame(rows).set_index(["comparison", "component"])
dec.round(4).to_csv("out/08_gap_decomposition.csv")
print(dec.round(3).to_string())

# Part 2: volume vs basket profitability (total GP = transactions x GP per transaction)
tot = df.groupby("Branch")[G].sum()
vol = []
for target in ["Harbour", "Uptown"]:
    Ng, Nt, gg, gt = ntx["Garden"], ntx[target], obs["Garden"], obs[target]
    vol.append({"comparison": f"{target} minus Garden",
                "transactions_Garden": Ng, f"transactions_target": Nt,
                "GP_per_tx_Garden_$": gg, "GP_per_tx_target_$": gt,
                "total_GP_Garden_$": tot["Garden"], "total_GP_target_$": tot[target],
                "total_GP_difference_$": tot[target] - tot["Garden"],
                "volume_part_$ [(Nt-Ng) x Garden GP/tx]": (Nt - Ng) * gg,
                "basket_profitability_part_$ [Nt x (gt-gg)]": Nt * (gt - gg),
                "alt_order_volume_$ [(Nt-Ng) x target GP/tx]": (Nt - Ng) * gt,
                "alt_order_profitability_$ [Ng x (gt-gg)]": Ng * (gt - gg)})
vol = pd.DataFrame(vol).set_index("comparison")
for _, r in vol.iterrows():
    tdiff = r["total_GP_difference_$"]
    assert abs(r["volume_part_$ [(Nt-Ng) x Garden GP/tx]"] + r["basket_profitability_part_$ [Nt x (gt-gg)]"] - tdiff) < 0.05
    assert abs(r["alt_order_volume_$ [(Nt-Ng) x target GP/tx]"] + r["alt_order_profitability_$ [Ng x (gt-gg)]"] - tdiff) < 0.05
vol.round(2).to_csv("out/08_volume_vs_basket_profitability.csv")
print(vol.round(2).T.to_string())
