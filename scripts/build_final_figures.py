#!/usr/bin/env python3
"""Rebuild four evidence charts directly from the original transaction CSV.

All rows and recorded financial amounts are retained. The common-reference chart
uses the quantity-weighted product schedule from common_price_reference.py. Its
values reproduce the source report; an unweighted branch-average schedule does
not. The waterfall uses the declared factor order in 08_gap_decomposition.py.
"""
from __future__ import annotations

import csv
import hashlib
import json
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from _shared import FACTORS, LABELS, factors, gp_per_tx, sequential

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "outputs" / "final_review" / "figures"
D = Decimal
CENT = D("0.01")
P, C, GP = "Unit Price (USD)", "Unit Cost (USD)", "Line Gross Profit (USD)"
NAVY, BLUE, ORANGE, TEAL, GREY = "#17354b", "#256da6", "#c46c24", "#267d78", "#777f87"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.titlesize": 11.5, "axes.labelsize": 9,
    "axes.titleweight": "bold", "text.color": NAVY,
    "axes.labelcolor": NAVY, "xtick.color": NAVY, "ytick.color": NAVY,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.spines.left": False, "axes.spines.bottom": False,
    "axes.axisbelow": True, "savefig.dpi": 200, "text.parse_math": False,
})


def dollar(v: float | Decimal, places: int = 2) -> str:
    x = D(str(v)).quantize(D(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return f"${x:,.{places}f}"


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", facecolor="white", dpi=200)
    plt.close(fig)


def grid(ax):
    ax.grid(axis="y", color="#e0e5e8", lw=0.65)
    ax.tick_params(length=0, pad=5)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    original_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    df = pd.read_csv(SOURCE)
    with SOURCE.open(newline="", encoding="utf-8-sig") as f:
        raw = list(csv.DictReader(f))
    schedule = {}
    quantities = {}
    exact_gp = {}
    for row in raw:
        key = row["Branch"], row["Product"]
        rec = D(row[P]), D(row[C])
        assert key not in schedule or schedule[key] == rec
        schedule[key] = rec
        quantities[key] = quantities.get(key, D(0)) + D(row["Quantity"])
        exact_gp[row["Branch"]] = exact_gp.get(row["Branch"], D(0)) + D(row[GP])
    assert exact_gp["Garden"] == D("46794.49")
    products = sorted(p for b, p in schedule if b == "Garden")
    assert len(products) == 45 and len(schedule) == 135
    checks = {"all_source_rows_retained": True, "source_sha256": original_hash,
              "source_row_count": len(df), "garden_observed_gp_usd": str(exact_gp["Garden"])}

    # 1. Fixed-Garden-quantity recorded cost premium by product.
    premiums = [dict(product=p, garden_quantity=int(quantities["Garden", p]),
                     premium_usd=quantities["Garden", p] * (schedule["Garden", p][1] - schedule["Harbour", p][1]))
                for p in products]
    premiums.sort(key=lambda r: (-r["premium_usd"], r["product"]))
    total = sum((r["premium_usd"] for r in premiums), D(0))
    assert total == D("15923.47")
    pd.DataFrame(premiums).to_csv(OUT / "top_product_premium_data.csv", index=False)
    top = premiums[:15]
    top_share = sum((r["premium_usd"] for r in top), D(0)) / total
    checks["harbour_recorded_cost_premium_usd"] = str(total)
    checks["top15_share"] = str(top_share)
    fig, ax = plt.subplots(figsize=(6.8, 4.95))
    y = np.arange(len(top))
    vals = [float(r["premium_usd"]) for r in top]
    ax.barh(y, vals, color=BLUE, height=.69)
    ax.set_yticks(y, [r["product"] for r in top], fontsize=8.5)
    ax.invert_yaxis()
    ax.tick_params(length=0)
    ax.grid(axis="x", color="#e0e5e8", lw=.65)
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: dollar(x, 0)))
    ax.set_xlim(0, 950)
    ax.set_xlabel("Garden quantity × (Garden − Harbour recorded unit cost), USD")
    for i, value in enumerate(vals):
        ax.text(value + 10, i, dollar(value, 0), va="center", fontsize=8.5)
    fig.suptitle("Largest contributors to Garden’s recorded cost premium", x=.02, ha="left", y=.985, fontsize=11.2, fontweight="bold")
    fig.text(.02, .925, "Harbour reference | January–June 2026 | Garden’s observed quantities", fontsize=9)
    fig.text(.02, .022, f"Top 15: {float(top_share):.1%} of the {dollar(total)} benchmark. Recoverable savings are unverified.", fontsize=8)
    fig.subplots_adjust(left=.29, right=.98, bottom=.14, top=.88)
    save(fig, "01_recorded_cost_premiums")

    # 2. Quantity-weighted common product schedule, matching source script/PDF.
    n = df.groupby("Branch")["Transaction ID"].nunique()
    q = df["Quantity"]
    chain_price = (df[P] * q).groupby(df.Product).sum() / q.groupby(df.Product).sum()
    chain_cost = (df[C] * q).groupby(df.Product).sum() / q.groupby(df.Product).sum()
    observed = df.groupby("Branch")[GP].sum() / n
    common = (q * (df.Product.map(chain_price) - df.Product.map(chain_cost))).groupby(df.Branch).sum() / n
    order = ["Garden", "Harbour", "Uptown"]
    expected = {"Garden": 5.36, "Harbour": 5.33, "Uptown": 5.43}
    for b in order:
        assert round(common[b], 2) == expected[b]
    comparison = pd.DataFrame({"branch": order, "transactions": [int(n[b]) for b in order],
        "observed_gp_per_transaction_usd": [observed[b] for b in order],
        "common_reference_gp_per_transaction_usd": [common[b] for b in order]})
    comparison.to_csv(OUT / "common_reference_data.csv", index=False)
    checks["common_reference_convention"] = "Quantity-weighted chain product price and unit cost, then applied to each branch quantities; discounts removed"
    fig, ax = plt.subplots(figsize=(6.8, 3.65))
    x = np.arange(3)
    width = .31
    for offset, series, label, color in [(-width / 2, observed, "Observed prices, costs and discounts", ORANGE),
                                       (width / 2, common, "Common prices and costs; no discounts", BLUE)]:
        values = [series[b] for b in order]
        ax.bar(x + offset, values, width=width, label=label, color=color)
        for i, v in enumerate(values):
            ax.text(i + offset, v + .12, dollar(v), ha="center", va="bottom", fontsize=9)
    ax.set_xticks(x, [f"{b}\n({n[b]:,} transactions)" for b in order])
    ax.set_ylabel("Gross profit per transaction (USD)")
    ax.set_ylim(0, 7.1)
    ax.set_yticks(np.arange(0, 8))
    grid(ax)
    fig.suptitle("Observed and common-reference gross profit per transaction", x=.02, y=.985, ha="left", fontsize=11.2, fontweight="bold")
    fig.legend(loc="upper left", bbox_to_anchor=(.02, .915), frameon=False, fontsize=8.4)
    fig.text(.02, .035, "Common reference: quantity-weighted chain product prices and costs. Each branch keeps its baskets.\nJanuary–June 2026; this comparison is descriptive, with no assumed customer response.", fontsize=8, linespacing=1.4)
    fig.subplots_adjust(left=.10, right=.98, top=.70, bottom=.23)
    save(fig, "02_common_reference_baskets")

    # 3. Sequential factor decomposition. Negative bars use absolute heights.
    F = {b: factors(df[df.Branch == b]) for b in order}
    fig, axes = plt.subplots(2, 1, figsize=(6.8, 6.05), sharey=True)
    decomposition = []
    labels = ["Garden\nobserved", "Recorded\ncosts", "List\nprices", "Realized\ndiscounts", "Units per\nbasket", "Product\nmix"]
    for ax, target in zip(axes, ["Harbour", "Uptown"]):
        vals = sequential(F["Garden"], F[target], FACTORS)
        gap = observed[target] - observed["Garden"]
        residual = gap - sum(vals.values())
        assert abs(residual) < .0001
        assert abs(gp_per_tx(F["Garden"]) + sum(vals.values()) - gp_per_tx(F[target])) < 1e-9
        running = observed["Garden"]
        ax.bar(0, running, color=GREY, width=.6)
        ax.text(0, running + .11, dollar(running), ha="center", fontsize=9)
        for i, key in enumerate(FACTORS, 1):
            v = vals[key]
            nxt = running + v
            ax.plot([i - .7, i + .3], [running, running], color="#adb7bf", lw=.8, zorder=0)
            ax.bar(i, abs(v), bottom=min(running, nxt), color=ORANGE if v >= 0 else TEAL, width=.6)
            text = "$0.00" if abs(v) < .005 else ("+" if v > 0 else "−") + dollar(abs(v))
            ax.text(i, max(running, nxt) + .11, text, ha="center", fontsize=9)
            running = nxt
            decomposition.append({"comparison": f"Garden to {target}", "component": LABELS[key], "contribution_usd_per_transaction": v})
        ax.plot([5.3, 5.7], [running, running], color="#adb7bf", lw=.8, zorder=0)
        ax.bar(6, observed[target], color=BLUE, width=.6)
        ax.text(6, observed[target] + .11, dollar(observed[target]), ha="center", fontsize=9)
        ax.set_xticks(np.arange(7), labels + [f"{target}\nobserved"], fontsize=8.4)
        ax.set_ylim(0, 7)
        ax.set_ylabel("GP per transaction (USD)")
        ax.set_title(f"Garden → {target} | observed gap {dollar(gap)} per transaction", loc="left", fontsize=10, pad=8)
        grid(ax)
        decomposition.extend([
            {"comparison": f"Garden to {target}", "component": "Recorded-line cent rounding", "contribution_usd_per_transaction": residual},
            {"comparison": f"Garden to {target}", "component": "Observed gap", "contribution_usd_per_transaction": gap}])
        checks[f"{target.lower()}_waterfall_residual_usd_per_transaction"] = residual
    pd.DataFrame(decomposition).to_csv(OUT / "declared_order_decomposition_data.csv", index=False)
    fig.suptitle("Accounting decomposition of Garden’s gross-profit gaps", x=.02, y=.985, ha="left", fontsize=11.2, fontweight="bold")
    fig.text(.02, .93, "Declared order: recorded costs → list prices → discounts → units per basket → product mix", fontsize=8.5)
    fig.text(.02, .025, "Orange adds to the gap; teal offsets it. Recorded-line rounding is below $0.0001 per transaction.\nOrder-dependent accounting comparison; factor contributions are not causal effects.", fontsize=8, linespacing=1.4)
    fig.subplots_adjust(left=.10, right=.98, top=.86, bottom=.14, hspace=.43)
    save(fig, "03_declared_order_waterfalls")

    # 4. Two exact cent-rounded recorded cost rules.
    rules = []
    for b, multiplier in [("Garden", D("1.43")), ("Uptown", D("0.96"))]:
        for p in products:
            hcost = schedule["Harbour", p][1]
            predicted = (hcost * multiplier).quantize(CENT, rounding=ROUND_HALF_UP)
            actual = schedule[b, p][1]
            assert predicted == actual
            rules.append({"branch": b, "product": p, "harbour_recorded_cost_usd": hcost,
                          "branch_recorded_cost_usd": actual, "factor": multiplier,
                          "predicted_after_cent_rounding_usd": predicted, "matches": True})
        checks[f"{b.lower()}_rule_matches"] = 45
    pd.DataFrame(rules).to_csv(OUT / "cost_schedule_rule_data.csv", index=False)
    fig, ax = plt.subplots(figsize=(6.8, 4.15))
    line = np.array([0, 6.0])
    for b, multiplier, color, marker in [("Garden", 1.43, ORANGE, "o"), ("Uptown", .96, BLUE, "s")]:
        ax.plot(line, line * multiplier, color=color, ls="--", lw=1)
        ax.scatter([float(schedule["Harbour", p][1]) for p in products], [float(schedule[b, p][1]) for p in products],
                   color=color, marker=marker, s=25, edgecolors="white", linewidths=.4,
                   label=f"{b}: Harbour × {multiplier:.2f}; 45/45 after cent rounding", zorder=3)
    ax.set_xlim(0, 6)
    ax.set_ylim(0, 9)
    ax.set_xlabel("Harbour recorded unit cost (USD)")
    ax.set_ylabel("Garden / Uptown recorded unit cost (USD)")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: dollar(x, 0)))
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: dollar(y, 0)))
    grid(ax)
    ax.grid(axis="x", color="#e0e5e8", lw=.65)
    fig.suptitle("Recorded unit costs follow two fixed schedules", x=.02, y=.985, ha="left", fontsize=11.2, fontweight="bold")
    fig.legend(loc="upper left", bbox_to_anchor=(.10, .925), frameon=False, fontsize=8.6)
    fig.text(.02, .025, "Each marker is one product; identical cost pairs overlap. Dashed lines show the unrounded factors.\nJanuary–June 2026; these schedules do not establish supplier payments or the cause of the differences.", fontsize=8, linespacing=1.4)
    fig.subplots_adjust(left=.10, right=.98, top=.74, bottom=.23)
    save(fig, "04_recorded_cost_schedules")

    assert hashlib.sha256(SOURCE.read_bytes()).hexdigest() == original_hash
    checks["source_unchanged"] = True
    checks["charts"] = sorted(p.name for p in OUT.glob("*.png"))
    (OUT / "figure_validation.json").write_text(json.dumps(checks, indent=2) + "\n")
    print(json.dumps(checks, indent=2))


if __name__ == "__main__":
    main()
