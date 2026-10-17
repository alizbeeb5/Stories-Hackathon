"""Person 2 - Baskets & product mix: central waterfall of Garden's GP-per-transaction gap (reads out/08_gap_decomposition.csv).
Run 08_gap_decomposition.py first."""
import os
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({"font.size": 9.5, "text.parse_math": False, "axes.spines.top": False, "axes.spines.right": False})
dec = pd.read_csv("out/08_gap_decomposition.csv").set_index(["comparison", "component"])
obs_g = 46794.49 / 11163  # Garden observed GP per transaction (total GP / transactions)
steps = ["Recorded unit costs", "List prices", "Realized discounts", "Units per basket", "Product mix"]
UP, DOWN, ENDC = "#eb6834", "#1baf7a", "#2a78d6"

fig, axes = plt.subplots(1, 2, figsize=(11, 4.4), sharey=True)
for ax, target in zip(axes, ["Harbour", "Uptown"]):
    d = dec.loc[f"Garden -> {target}"]
    vals = [d.loc[s, "declared_order_$"] for s in steps]
    end = obs_g + d.loc["TOTAL = observed gap", "declared_order_$"]
    labels = ["Garden\nobserved"] + ["Costs", "Prices", "Discounts", "Units /\nbasket", "Mix"] + [f"{target}\nobserved"]
    ax.bar(0, obs_g, color="#8a8984", width=0.6)
    ax.text(0, obs_g + 0.06, f"${obs_g:.2f}", ha="center", fontsize=9)
    run = obs_g
    for i, v in enumerate(vals, start=1):
        # A negative contribution spans from the new running total to the old
        # one. Using a negative height after lowering the bottom shifts it twice.
        ax.bar(i, abs(v), bottom=min(run, run + v), color=UP if v >= 0 else DOWN, width=0.6)
        top = run + max(v, 0)
        ax.text(i, top + 0.06, ("$0.00" if abs(v) < 0.005 else f"+${v:.2f}" if v > 0 else f"-${-v:.2f}"), ha="center", fontsize=9)
        ax.plot([i - 0.3, i + 1.3], [run + v] * 2, color="#b9b8b2", lw=0.8, zorder=0)
        run += v
    ax.bar(len(steps) + 1, end, color=ENDC, width=0.6)
    ax.text(len(steps) + 1, end + 0.06, f"${end:.2f}", ha="center", fontsize=9)
    ax.set_xticks(range(len(labels))); ax.set_xticklabels(labels, fontsize=8.5)
    gap = d.loc["TOTAL = observed gap", "declared_order_$"]
    ax.set_title(f"Garden -> {target}: gap ${gap:.2f} per transaction", loc="left", fontsize=10.5)
    ax.set_ylim(0, 7); ax.grid(axis="y", color="#e4e3df"); ax.set_axisbelow(True)
axes[0].set_ylabel("Gross profit per transaction (USD)")
fig.suptitle("Where Garden's gross-profit-per-transaction gap comes from", x=0.01, ha="left", fontsize=12)
fig.text(0.01, 0.015, "Orange = raises the comparison branch above Garden; green = works in Garden's favour.\n"
         "Order: costs -> list prices -> discounts -> units per basket -> mix. Accounting comparison, not causal effects.",
         fontsize=8, color="#52514e")
fig.tight_layout(rect=(0, 0.09, 1, 0.95))
fig.savefig("out/11_gap_waterfall.png", dpi=170)
print("saved out/11_gap_waterfall.png")
