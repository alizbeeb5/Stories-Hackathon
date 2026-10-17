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
    sc = pd.read_csv(TABLES / "02_scenario_table.csv")
    fx = pd.read_csv(TABLES / "03_fixed_quantity_summary.csv")
    labels, values, colors = [], [], []
    labels.append("Do\nnothing"); values.append(OBS_GP); colors.append(C_OBS)
    for ref, color in [("Harbour", C_HARB), ("Uptown", C_UPT)]:
        for alpha in [25, 50, 100]:
            r = sc[(sc["Reference_Branch"] == ref) & (sc["Closure_alpha_pct"] == alpha)].iloc[0]
            labels.append(f"{ref}\n{alpha}% cost\nclosure")
            values.append(r["Scenario_GP_dollars"]); colors.append(color)
    for ref, color in [("Harbour", C_HARB), ("Uptown", C_UPT)]:
        r = fx[(fx["Reference_Branch"] == ref) & (fx["Cost_Closure_alpha"] == 1.0)].iloc[0]
        labels.append(f"{ref}\n100% + price\nmatch")
        values.append(r["Scenario_GP_fixed_qty"]); colors.append(color)

    fig, ax = plt.subplots(figsize=(12, 6))
    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, edgecolor="black", linewidth=0.5)
    ax.axhline(OBS_GP, ls="--", color="black", lw=1, label=f"Do-nothing baseline = ${OBS_GP:,.0f}")
    ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Garden gross profit (USD, 6 months)")
    ax.set_title("Garden gross profit under each scenario (accounting scenarios)")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x/1000:.0f}K"))
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 800, f"${v:,.0f}",
                ha="center", va="bottom", fontsize=8)
    ax.set_ylim(0, max(values) * 1.15)
    ax.grid(axis="y", alpha=0.3); ax.legend(loc="upper left")
    plt.tight_layout()
    out = FIGS / "fig_a_scenarios.png"
    plt.savefig(out, dpi=150); plt.close()
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