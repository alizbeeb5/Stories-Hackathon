"""
06_consolidated.py
==================
Step 6 — Produce the ONE scenario table the report leads with.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "tables"
WINDOW_MONTHS = 6


def build() -> pd.DataFrame:
    sc = pd.read_csv(OUT / "02_scenario_table.csv")
    fx = pd.read_csv(OUT / "03_fixed_quantity_summary.csv")
    be = pd.read_csv(OUT / "03_demand_breakeven.csv")

    rows = []
    for ref in ["Harbour", "Uptown"]:
        for alpha in [25, 50, 100]:
            r_sc = sc[(sc["Reference_Branch"] == ref) & (sc["Closure_alpha_pct"] == alpha)].iloc[0]
            uplift = r_sc["Scenario_Uplift_dollars"]
            rows.append({
                "Scenario_ID": f"S{ref[0]}-C{alpha:03d}",
                "Scenario_Description": f"Match {ref} unit cost ({alpha}% of recorded gap) — Garden prices/quantities unchanged.",
                "Reference_Branch": ref,
                "Cost_Closure_alpha_pct": alpha,
                "Price_Move_vs_Garden": "None (observed prices)",
                "Six_Month_GP_Benefit_dollars": round(uplift, 2),
                "Annualized_Benefit_dollars": round(uplift * 12 / WINDOW_MONTHS, 2),
                "Max_Annual_Recurring_Cost_dollars": round(uplift * 12 / WINDOW_MONTHS, 2),
                "Volume_Break_Even_Multiplier": "n/a",
                "Allowable_Volume_Change_pct": "n/a",
                "Assumptions": "Recorded unit costs are real and comparable; mix and quantity constant; no implementation cost.",
                "What_Would_Reverse": "Supplier offsets, allocation artefacts, portion differences.",
                "Evidence_Label": "accounting scenario",
            })

    for ref2 in ["Harbour", "Uptown"]:
        r_fx = fx[(fx["Reference_Branch"] == ref2) & (fx["Cost_Closure_alpha"] == 1.0)].iloc[0]
        r_be = be[(be["Reference_Branch"] == ref2) & (be["Cost_Closure_alpha"] == 1.0)].iloc[0]
        uplift = r_fx["Fixed_Qty_Gain"]
        v = r_be["Breakeven_Volume_Multiplier_v"]
        v_pct = (v - 1) * 100
        price_dir = "UP" if ref2 == "Harbour" else "DOWN"
        rows.append({
            "Scenario_ID": f"S{ref2[0]}-CP100",
            "Scenario_Description": f"Match {ref2} unit cost (100%) AND match {ref2} prices. Garden prices move {price_dir}.",
            "Reference_Branch": ref2,
            "Cost_Closure_alpha_pct": 100,
            "Price_Move_vs_Garden": f"{price_dir} (to {ref2} level)",
            "Six_Month_GP_Benefit_dollars": round(uplift, 2),
            "Annualized_Benefit_dollars": round(uplift * 12 / WINDOW_MONTHS, 2),
            "Max_Annual_Recurring_Cost_dollars": round(uplift * 12 / WINDOW_MONTHS, 2),
            "Volume_Break_Even_Multiplier": round(v, 4),
            "Allowable_Volume_Change_pct": round(v_pct, 2),
            "Assumptions": "Costs real. Prices change to reference. Mix constant. Linear demand. Cost per unit independent of volume.",
            "What_Would_Reverse": "Customer loss exceeds break-even; cost per unit rises with lower volume; brand damage.",
            "Evidence_Label": "accounting scenario",
        })
    return pd.DataFrame(rows)


def main() -> int:
    df = build()
    out = OUT / "06_master_scenario_table.csv"
    df.to_csv(out, index=False)
    print("=" * 70); print("MASTER SCENARIO TABLE"); print("=" * 70)
    print(df[["Scenario_ID", "Reference_Branch", "Cost_Closure_alpha_pct",
              "Price_Move_vs_Garden", "Six_Month_GP_Benefit_dollars",
              "Allowable_Volume_Change_pct", "Evidence_Label"]].to_string(index=False))
    print(f"\nFull table written to: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())