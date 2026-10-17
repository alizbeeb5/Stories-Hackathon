"""
02_cost_gap_scenarios.py
========================
Step 2 — Cost-gap scenarios for Garden.

For every Garden line item, look up the same product's recorded unit cost at
Harbour and at Uptown. The "cost gap" is Garden cost minus the reference cost,
multiplied by the Garden quantity actually sold:

    gap_dollars(Garden, ref) = SUM over Garden lines of
        (Garden_unit_cost - ref_unit_cost) * Garden_quantity

We then compute Garden's gross profit under four "closure" assumptions
(alpha = 0%, 25%, 50%, 100%):

    scenario_GP = observed_Garden_GP + alpha * gap_dollars

These are ACCOUNTING SCENARIOS, not predictions.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

CLOSURES = [0.00, 0.25, 0.50, 1.00]


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(DATA)
    df["Date"] = pd.to_datetime(df["Date"])
    cost_table = (
        df.groupby(["Branch", "Product"], as_index=False)["Unit Cost (USD)"]
        .first()
    )
    return df, cost_table


def compute_gaps(garden_df: pd.DataFrame, cost_table: pd.DataFrame) -> pd.DataFrame:
    cost_wide = cost_table.pivot(
        index="Product", columns="Branch", values="Unit Cost (USD)"
    )
    garden_df = garden_df.merge(cost_wide, left_on="Product", right_index=True, how="left")
    garden_df = garden_df.rename(columns={"Harbour": "RefCost_Harbour", "Uptown": "RefCost_Uptown"})
    garden_df["GapVsHarbour_$_per_unit"] = garden_df["Unit Cost (USD)"] - garden_df["RefCost_Harbour"]
    garden_df["GapVsUptown_$_per_unit"]  = garden_df["Unit Cost (USD)"] - garden_df["RefCost_Uptown"]
    garden_df["GapVsHarbour_$_lines"] = garden_df["GapVsHarbour_$_per_unit"] * garden_df["Quantity"]
    garden_df["GapVsUptown_$_lines"]  = garden_df["GapVsUptown_$_per_unit"]  * garden_df["Quantity"]
    return garden_df


def per_product_gap(garden_df: pd.DataFrame) -> pd.DataFrame:
    out = garden_df.groupby("Product", as_index=False).agg(
        Garden_UnitCost=("Unit Cost (USD)", "first"),
        Harbour_UnitCost=("RefCost_Harbour", "first"),
        Uptown_UnitCost=("RefCost_Uptown", "first"),
        Garden_Units=("Quantity", "sum"),
        Garden_Lines=("Transaction ID", "size"),
        GapVsHarbour_dollars=("GapVsHarbour_$_lines", "sum"),
        GapVsUptown_dollars=("GapVsUptown_$_lines", "sum"),
    )
    out["Ratio_G_over_H"] = (out["Garden_UnitCost"] / out["Harbour_UnitCost"]).round(4)
    out["Ratio_G_over_U"] = (out["Garden_UnitCost"] / out["Uptown_UnitCost"]).round(4)
    out["ShareOfHarbourGap_pct"] = (out["GapVsHarbour_dollars"] / out["GapVsHarbour_dollars"].sum() * 100).round(2)
    out["ShareOfUptownGap_pct"]  = (out["GapVsUptown_dollars"]  / out["GapVsUptown_dollars"].sum()  * 100).round(2)
    return out.sort_values("GapVsHarbour_dollars", ascending=False).reset_index(drop=True)


def scenario_table(observed_gp: float, observed_rev: float,
                   gap_harbour: float, gap_uptown: float) -> pd.DataFrame:
    rows = []
    for ref, gap in [("Harbour", gap_harbour), ("Uptown", gap_uptown)]:
        for a in CLOSURES:
            uplift = a * gap
            rows.append({
                "Reference_Branch": ref,
                "Closure_alpha_pct": int(a * 100),
                "Recorded_Garden_GP": round(observed_gp, 2),
                "Cost_Gap_dollars": round(gap, 2),
                "Scenario_Uplift_dollars": round(uplift, 2),
                "Scenario_GP_dollars": round(observed_gp + uplift, 2),
                "Scenario_Margin_pct": round((observed_gp + uplift) / observed_rev * 100, 2),
                "Evidence_Label": "accounting scenario",
            })
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 70)
    print("STEP 2 — COST-GAP SCENARIOS FOR GARDEN")
    print("=" * 70)
    df, cost_table = load()
    garden_df = df[df["Branch"] == "Garden"].copy()
    garden_df = compute_gaps(garden_df, cost_table)

    gap_harbour = garden_df["GapVsHarbour_$_lines"].sum()
    gap_uptown  = garden_df["GapVsUptown_$_lines"].sum()
    obs_gp   = garden_df["Line Gross Profit (USD)"].sum()
    obs_rev  = garden_df["Line Revenue (USD)"].sum()
    obs_cost = obs_rev - obs_gp

    print(f"\nObserved Garden revenue:        ${obs_rev:,.2f}")
    print(f"Observed Garden recorded cost:  ${obs_cost:,.2f}")
    print(f"Observed Garden gross profit:   ${obs_gp:,.2f}")
    print(f"\nTOTAL cost gap vs Harbour: ${gap_harbour:,.2f}")
    print(f"TOTAL cost gap vs Uptown:  ${gap_uptown:,.2f}")
    print(f"  Garden cost / Harbour cost = {obs_cost / (obs_cost - gap_harbour):.3f}")
    print(f"  Garden cost / Uptown cost  = {obs_cost / (obs_cost - gap_uptown):.3f}")

    pg = per_product_gap(garden_df)
    pg.to_csv(OUT / "02_cost_gap_by_product.csv", index=False)
    print(f"\nWrote {OUT / '02_cost_gap_by_product.csv'}")

    sc = scenario_table(obs_gp, obs_rev, gap_harbour, gap_uptown)
    sc.to_csv(OUT / "02_scenario_table.csv", index=False)
    print(f"\nWrote {OUT / '02_scenario_table.csv'}:")
    print(sc.to_string(index=False))
    print("\nDone. All numbers above are ACCOUNTING SCENARIOS.")
    return 0


if __name__ == "__main__":
    sys.exit(main())