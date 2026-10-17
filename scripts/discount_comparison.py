"""
04_discount_comparison.py
=========================
Step 4 — Compare each cost-gap scenario against Garden's recorded
discount dollars, and against the chain total. Removing recorded discounts is
a fixed-quantity accounting benchmark; the data do not identify its effect on
sales volume or product mix.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


def load():
    df = pd.read_csv(DATA)
    df["Date"] = pd.to_datetime(df["Date"])
    df["DiscountDollars"]  = df["Unit Price (USD)"] * df["Quantity"] - df["Line Revenue (USD)"]
    df["FullPriceRevenue"] = df["Unit Price (USD)"] * df["Quantity"]
    return df


def discount_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("Branch", as_index=False).agg(
        FullPriceRevenue=("FullPriceRevenue", "sum"),
        ActualRevenue=("Line Revenue (USD)", "sum"),
        DiscountDollars=("DiscountDollars", "sum"),
        DiscountedLines=("DiscountDollars", lambda s: (s > 0).sum()),
    )
    g["DiscountRate_pct_of_rev"] = (g["DiscountDollars"] / g["FullPriceRevenue"] * 100).round(3)
    g["PctOfLinesDiscounted"] = (g["DiscountedLines"] / df.groupby("Branch").size().values * 100).round(2)
    return g


def discount_by_order_type(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["Branch", "Order Type"], as_index=False).agg(
        DiscountDollars=("DiscountDollars", "sum"),
        Lines=("Transaction ID", "size"),
    )
    g["DiscountPerLine"] = (g["DiscountDollars"] / g["Lines"]).round(3)
    return g


def compare(scenarios: pd.DataFrame, discounts: pd.DataFrame) -> pd.DataFrame:
    garden_disc = discounts.loc[discounts["Branch"] == "Garden", "DiscountDollars"].iloc[0]
    chain_disc  = discounts["DiscountDollars"].sum()
    s = scenarios.copy()
    s["Garden_Discount_Dollars"]   = round(garden_disc, 2)
    s["Chain_Discount_Dollars"]    = round(chain_disc, 2)
    s["Benefit_vs_GardenDiscount"] = (s["Scenario_Uplift_dollars"] / garden_disc).round(2)
    s["Benefit_vs_ChainDiscount"]  = (s["Scenario_Uplift_dollars"] / chain_disc).round(2)
    return s


def main() -> int:
    print("=" * 70); print("STEP 4 — DISCOUNT DOLLARS vs SCENARIOS"); print("=" * 70)
    df = load()
    disc = discount_summary(df)
    disc.to_csv(OUT / "04_discount_summary.csv", index=False)
    print("\nDiscount dollars by branch:"); print(disc.to_string(index=False))
    dot = discount_by_order_type(df)
    dot.to_csv(OUT / "04_discount_by_order_type.csv", index=False)
    sc = pd.read_csv(OUT / "02_scenario_table.csv")
    cmp = compare(sc, disc)
    cmp.to_csv(OUT / "04_scenario_vs_discount.csv", index=False)
    print("\nScenario benefits vs discount dollars:")
    print(cmp[["Reference_Branch", "Closure_alpha_pct", "Scenario_Uplift_dollars",
              "Garden_Discount_Dollars", "Benefit_vs_GardenDiscount",
              "Chain_Discount_Dollars", "Benefit_vs_ChainDiscount"]].to_string(index=False))
    garden = df[df["Branch"] == "Garden"]
    observed_gp = garden["Line Gross Profit (USD)"].sum()
    garden_discounts = garden["DiscountDollars"].sum()
    benchmark = pd.DataFrame([{
        "Scenario": "Remove recorded discounts; Garden prices/costs",
        "Observed_Garden_GP": round(observed_gp, 2),
        "Fixed_Quantity_Gain": round(garden_discounts, 2),
        "Scenario_GP_fixed_qty": round(observed_gp + garden_discounts, 2),
        "Breakeven_volume_K0": observed_gp / (observed_gp + garden_discounts),
        "Evidence_Label": "fixed-quantity benchmark; demand and mix responses unknown",
    }])
    benchmark.to_csv(OUT / "04_no_discount_benchmark.csv", index=False)
    print(f"\n  Removing recorded Garden discounts: fixed-quantity benefit = ${garden_discounts:,.2f}.")
    print("  Sales-volume and product-mix responses are unknown; this is not a forecast or realized-savings ceiling.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
