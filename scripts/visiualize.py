"""
07_visualize.py
===============
Step 7 — Generate the headline visuals for the report.
Outputs: output/figures/fig_a_scenarios.png
         output/figures/fig_b_per_product_gap.png
         output/figures/fig_c_closure_curve.png
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
TABLES = ROOT / "output" / "tables"
FIGS = ROOT / "output" / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

OBS_GP, OBS_REV = 46794.49, 99748.55
C_OBS, C_HARB, C_UPT = "#7a7a7a", "#1565c0", "#ef6c00"


def panel_a_scenarios() -> Path:
    """Show the complete comparison, including price-only alternatives."""
    from decimal import Decimal, ROUND_HALF_UP

    scenarios = pd.read_csv(TABLES / "06_master_scenario_table.csv")
    assert len(scenarios) == 16 and scenarios["Scenario_ID"].is_unique
    assert scenarios["Scenario_Type"].eq("Price only").sum() == 2
    labels, colors = [], []
    for row in scenarios.to_dict("records"):
        ref, kind = row["Reference_Branch"], row["Scenario_Type"]
        closure = int(row["Cost_Closure_alpha_pct"])
        if kind == "Baseline":
            label = "Do nothing (observed Garden)"
        elif kind == "Price only":
            label = f"Match {ref} prices only"
        elif kind == "Cost only":
            label = f"{ref} gap: {closure}% closure; Garden prices"
        elif kind == "Cost and price":
            label = f"{ref} gap: {closure}% closure + {ref} prices"
        else:
            label = "Remove recorded discounts (fixed-quantity benchmark)"
        labels.append(label)
        colors.append(C_HARB if ref == "Harbour" else C_UPT if ref == "Uptown" else "#7358a5" if kind == "Discount benchmark" else C_OBS)

    values = scenarios["Benefit_v100_K0_dollars"].to_numpy()
    fig, ax = plt.subplots(figsize=(14, 10))
    y = np.arange(len(scenarios))
    ax.barh(y, values, color=colors, height=0.64)
    ax.scatter([0], [0], color=C_OBS, s=25, zorder=4)
    ax.axvline(0, color="#555555", lw=0.9)
    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=10)
    ax.invert_yaxis()
    ax.set_xlabel("Incremental benefit versus observed Garden gross profit (USD, six months)", labelpad=12)
    ax.set_title(
        "Six-month incremental benefit: all 16 alternatives\n"
        "Hypothetical fixed-quantity benchmark: v = 1.00; additional expenses K = $0",
        fontsize=14, loc="left", pad=20,
    )
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda amount, _: f"${amount / 1000:,.0f}K"))
    for i, value in enumerate(values):
        amount = Decimal(str(abs(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        label = f"{'-' if value < 0 else ''}${amount:,.2f}"
        if value < 0:
            ax.text(value / 2, i, label, ha="center", va="center", fontsize=9, color="white")
        else:
            ax.annotate(label, (value, i), xytext=(6, 0), textcoords="offset points",
                        ha="left", va="center", fontsize=9)
    ax.set_xlim(min(values) - 2500, max(values) + 3800)
    ax.grid(axis="x", alpha=0.22)
    ax.set_axisbelow(True)
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0, pad=8)
    fig.text(0.025, 0.035,
             "Blue: Harbour reference. Orange: Uptown reference. Purple: discount-removal benchmark.\n"
             "All actions use Garden's observed quantities and mix. Cost achievability and customer responses are unproven;\n"
             "positive bars are before implementation expenses. Observed baseline gross profit: $46,794.49.",
             fontsize=9, color="#444444", va="bottom")
    fig.subplots_adjust(left=0.40, right=0.98, top=0.88, bottom=0.18)
    out = FIGS / "fig_a_scenarios.png"
    fig.savefig(out, dpi=160)
    plt.close(fig)
    return out


def panel_b_per_product() -> Path:
    df = pd.read_csv(TABLES / "02_cost_gap_by_product.csv")
    df = df.sort_values("GapVsHarbour_dollars", ascending=False).head(15).iloc[::-1]
    fig, ax = plt.subplots(figsize=(10, 7))
    y = np.arange(len(df))
    ax.barh(y, df["GapVsHarbour_dollars"], color=C_HARB, edgecolor="black", linewidth=0.5)
    ax.set_yticks(y); ax.set_yticklabels(df["Product"], fontsize=9)
    ax.set_xlabel("Cost gap vs Harbour (USD, 6 months)")
    ax.set_title("Top 15 products by Garden-vs-Harbour cost gap")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.0f}"))
    for i, v in enumerate(df["GapVsHarbour_dollars"]):
        ax.text(v + 8, i, f"${v:,.0f}", va="center", fontsize=8)
    total = df["GapVsHarbour_dollars"].sum()
    ax.text(0.99, 0.02, f"Top 15 contribute {total/15923*100:.1f}% of the total $15,923 gap",
            transform=ax.transAxes, ha="right", va="bottom", fontsize=9, color="#444")
    ax.grid(axis="x", alpha=0.3)
    plt.tight_layout()
    out = FIGS / "fig_b_per_product_gap.png"
    plt.savefig(out, dpi=150); plt.close()
    return out


def panel_c_closure_levels() -> Path:
    sc = pd.read_csv(TABLES / "02_scenario_table.csv")
    fig, ax = plt.subplots(figsize=(8, 5))
    for ref, color, marker in [("Harbour", C_HARB, "o"), ("Uptown", C_UPT, "s")]:
        sub = sc[sc["Reference_Branch"] == ref].sort_values("Closure_alpha_pct")
        ax.plot(sub["Closure_alpha_pct"], sub["Scenario_GP_dollars"],
                marker=marker, markersize=9, linewidth=2, color=color, label=f"vs {ref}")
        for _, r in sub.iterrows():
            offset = (12, 12) if ref == "Harbour" else (12, -22)
            ax.annotate(f"${r['Scenario_GP_dollars']:,.0f}\n({r['Scenario_Margin_pct']:.1f}%)",
                        (r["Closure_alpha_pct"], r["Scenario_GP_dollars"]),
                        textcoords="offset points", xytext=offset, ha="center", fontsize=8)
    ax.axhline(OBS_GP, ls="--", color="black", lw=1, label=f"Observed Garden GP = ${OBS_GP:,.0f}")
    ax.axhline(97753.94, ls=":", color=C_HARB, lw=1, alpha=0.6, label="Harbour GP = $97,754")
    ax.axhline(34882.06, ls=":", color=C_UPT, lw=1, alpha=0.6, label="Uptown GP = $34,882")
    ax.set_xlabel("Cost closure alpha (%)")
    ax.set_ylabel("Garden gross profit (USD, 6 months)")
    ax.set_xticks([0, 25, 50, 100])
    ax.set_title("Garden GP at each cost-closure level (no price change, fixed quantity)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
    ax.grid(alpha=0.3); ax.legend(loc="lower right", fontsize=9, framealpha=0.95)
    plt.tight_layout()
    out = FIGS / "fig_c_closure_curve.png"
    plt.savefig(out, dpi=150); plt.close()
    return out


def main() -> int:
    print("=" * 70); print("STEP 7 — VISUALS"); print("=" * 70)
    for f in (panel_a_scenarios(), panel_b_per_product(), panel_c_closure_levels()):
        print(f"  wrote {f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())