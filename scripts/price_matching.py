"""
03_price_matching.py
====================
Step 3 — Price-matching scenarios and demand break-even.

We can move the dial on TWO levers at once: cost and price. The script asks:

  "Holding Garden's quantities and mix FIXED, what happens to gross profit
   if we re-price Garden to match a reference branch's prices (keeping
   Garden's recorded costs)?"

Then the DEMAND BREAK-EVEN question:

  "If the price change causes Garden's volume to fall/rise by X%, at what X
   does the combined cost-closure + price change stop adding gross profit?"

Assumptions: quantities scale while product mix and unit economics remain fixed.
Volume multipliers and expense levels are hypothetical sensitivity inputs, not
estimated customer responses. Garden prices are below Harbour and above Uptown.
Scenario changes are added to recorded revenue/GP, preserving the original
line-rounding residual so that an unchanged scenario reproduces the baseline.
For Garden, the recorded revenue exceeds the unrounded reconstruction by
$0.755 over six months; that residual is carried forward in price scenarios.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)
HYPOTHETICAL_IMPLEMENTATION_EXPENSES = [0.0, 1000.0, 2500.0, 5000.0]


def load():
    df = pd.read_csv(DATA)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def price_table(df: pd.DataFrame) -> pd.DataFrame:
    pp = (df.groupby(["Branch", "Product"], as_index=False)["Unit Price (USD)"].first())
    wide = pp.pivot(index="Product", columns="Branch", values="Unit Price (USD)")
    wide.columns = [f"Price_{c}" for c in wide.columns]
    return wide.reset_index()


def per_product_step(df_garden: pd.DataFrame, df_all: pd.DataFrame,
                     price_wide: pd.DataFrame,
                     cost_closure_alpha: float) -> pd.DataFrame:
    cost_wide = (
        df_all.groupby(["Branch", "Product"], as_index=False)["Unit Cost (USD)"]
        .first()
        .pivot(index="Product", columns="Branch", values="Unit Cost (USD)")
    )
    cost_wide.columns = [f"Cost_{c}" for c in cost_wide.columns]

    base = df_garden[
        ["Product", "Quantity", "Unit Price (USD)", "Unit Cost (USD)",
         "Discount Rate", "Line Revenue (USD)", "Line Gross Profit (USD)"]
    ].copy()
    base = base.rename(columns={"Unit Price (USD)": "GardenPrice",
                                "Unit Cost (USD)":  "GardenCost"})
    base = base.merge(price_wide, on="Product", how="left")
    base = base.merge(cost_wide, on="Product", how="left")
    base["ObsRev"] = base["Line Revenue (USD)"]
    base["ObsGP"]  = base["Line Gross Profit (USD)"]

    for ref in ["Harbour", "Uptown"]:
        new_cost = base["GardenCost"] + cost_closure_alpha * (
            base[f"Cost_{ref}"] - base["GardenCost"]
        )
        new_price = base[f"Price_{ref}"]
        price_delta = (new_price - base["GardenPrice"]) * base["Quantity"] * (1.0 - base["Discount Rate"])
        cost_saving = (base["GardenCost"] - new_cost) * base["Quantity"]
        new_rev   = base["ObsRev"] + price_delta
        new_gp    = base["ObsGP"] + price_delta + cost_saving
        base[f"NewRev_{ref}"]   = new_rev
        base[f"NewGP_{ref}"]    = new_gp
        base[f"DeltaRev_{ref}"] = new_rev - base["ObsRev"]
        base[f"DeltaGP_{ref}"]  = new_gp  - base["ObsGP"]
    return base


def aggregate_per_product(base: pd.DataFrame) -> pd.DataFrame:
    return base.groupby("Product", as_index=False).agg(
        GardenUnits=("Quantity", "sum"),
        GardenObsGP=("ObsGP", "sum"),
        DeltaGP_Harbour=("DeltaGP_Harbour", "sum"),
        DeltaGP_Uptown=("DeltaGP_Uptown", "sum"),
    )


def fixed_quantity_summary(base: pd.DataFrame, alpha: float) -> pd.DataFrame:
    rows = []
    obs_gp = base["ObsGP"].sum()
    for ref in ["Harbour", "Uptown"]:
        new_gp = base[f"NewGP_{ref}"].sum()
        rows.append({
            "Cost_Closure_alpha": alpha,
            "Reference_Branch": ref,
            "Observed_Garden_GP": round(obs_gp, 2),
            "Scenario_GP_fixed_qty": round(new_gp, 2),
            "Fixed_Qty_Gain": round(new_gp - obs_gp, 2),
            "Evidence_Label": "accounting scenario (fixed quantity)",
        })
    return pd.DataFrame(rows)


def demand_breakeven(base: pd.DataFrame, alpha: float,
                     implementation_expenses=HYPOTHETICAL_IMPLEMENTATION_EXPENSES) -> pd.DataFrame:
    rows = []
    obs_gp = base["ObsGP"].sum()
    for ref in ["Harbour", "Uptown"]:
        scenario_gp = base[f"NewGP_{ref}"].sum()
        for k in implementation_expenses:
            v = (obs_gp + k) / scenario_gp if scenario_gp > 0 else float("nan")
            rows.append({
                "Cost_Closure_alpha": alpha,
                "Reference_Branch": ref,
                "Observed_Garden_GP": round(obs_gp, 2),
                "Scenario_GP_at_observed_quantity": round(scenario_gp, 2),
                "Hypothetical_Implementation_Expenses_6mo": k,
                "Breakeven_Volume_Multiplier_v": round(v, 6),
                "Allowable_Volume_Drop_pct": round((1 - v) * 100, 2) if v < 1 else None,
                "Required_Volume_Uplift_pct": round((v - 1) * 100, 2) if v > 1 else None,
                "Note": "Break-even only: quantities scale; product mix and unit economics fixed.",
                "Evidence_Label": "hypothetical expense sensitivity; no customer-response estimate",
            })
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 70)
    print("STEP 3 — PRICE MATCHING + DEMAND BREAK-EVEN")
    print("=" * 70)
    df = load()
    garden = df[df["Branch"] == "Garden"].copy()
    pw = price_table(df)
    residual = (garden["Line Revenue (USD)"] - garden["Unit Price (USD)"] * garden["Quantity"] * (1 - garden["Discount Rate"])).sum()
    print(f"Recorded-revenue rounding residual carried forward: ${residual:,.3f}")

    results_fixed, results_be, per_product_tables = [], [], {}
    for alpha in [0.00, 0.25, 0.50, 1.00]:
        print(f"--- α = {int(alpha*100)}% ---")
        base = per_product_step(garden, df, pw, alpha)
        per_product_tables[alpha] = aggregate_per_product(base)
        fx = fixed_quantity_summary(base, alpha)
        be = demand_breakeven(base, alpha)
        results_fixed.append(fx); results_be.append(be)
        print(fx.to_string(index=False)); print()
        print(be.to_string(index=False)); print()

    fixed_df = pd.concat(results_fixed, ignore_index=True)
    be_df    = pd.concat(results_be, ignore_index=True)
    fixed_df.to_csv(OUT / "03_fixed_quantity_summary.csv", index=False)
    be_df.to_csv(OUT / "03_demand_breakeven.csv", index=False)

    pp100 = per_product_tables[1.00]
    pw_with_costs = pw.merge(
        garden.groupby("Product", as_index=False)["Unit Cost (USD)"].first()
              .rename(columns={"Unit Cost (USD)": "Garden_Cost"}),
        on="Product"
    )
    pp_full = pw_with_costs.merge(pp100, on="Product")
    pp_full["ShareOfHarbourGain_pct"] = (pp_full["DeltaGP_Harbour"] / pp_full["DeltaGP_Harbour"].sum() * 100).round(2)
    pp_full["ShareOfUptownGain_pct"]  = (pp_full["DeltaGP_Uptown"]  / pp_full["DeltaGP_Uptown"].sum()  * 100).round(2)
    pp_full = pp_full.sort_values("DeltaGP_Harbour", ascending=False).reset_index(drop=True)
    pp_full.to_csv(OUT / "03_per_product_price_effect_alpha100.csv", index=False)
    print(f"\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
