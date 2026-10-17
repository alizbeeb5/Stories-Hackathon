"""
01_validate_baseline.py
=======================
Step 1 — Recalculate branch-level revenue, costs, gross profit, margin,
quantities, and discount dollars from the raw transaction file. This is the
baseline that every later scenario is compared against.

Outputs
-------
output/tables/01_branch_summary.csv   one row per branch + a TOTAL row
output/tables/01_lineitem_vs_given.csv sanity check on supplied columns
output/tables/01_category_share.csv    category share of revenue and GP
output/tables/01_product_price_cost_stability.csv  price/cost within branch
console summary

What it deliberately does
-------------------------
* Does not delete duplicate rows. The brief says the data is supplied "as is".
  We flag duplicates and report metrics both with and without them so we can
  judge whether they change the conclusion.
* Treats each line item as independent, then aggregates by transaction and by
  branch separately, so the report can show both views.
* Separates "observed fact" (computed directly from the file) from any later
  counterfactual. Everything in this script is observed fact.
"""

from __future__ import annotations
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)


def load() -> pd.DataFrame:
    df = pd.read_csv(DATA)
    df["Date"] = pd.to_datetime(df["Date"])
    return df


def sanity_check_columns(df: pd.DataFrame) -> pd.DataFrame:
    expected_revenue = (
        df["Unit Price (USD)"] * df["Quantity"] * (1.0 - df["Discount Rate"])
    ).round(2)
    expected_gp = (
        df["Line Revenue (USD)"] - df["Unit Cost (USD)"] * df["Quantity"]
    ).round(2)
    check = df[
        [
            "Transaction ID", "Branch", "Quantity",
            "Unit Price (USD)", "Discount Rate", "Unit Cost (USD)",
            "Line Revenue (USD)", "Line Gross Profit (USD)",
        ]
    ].copy()
    check["Expected Revenue"] = expected_revenue
    check["Expected GP"] = expected_gp
    check["Revenue OK"] = (check["Line Revenue (USD)"] - check["Expected Revenue"]).abs() < 0.01
    check["GP OK"] = (check["Line Gross Profit (USD)"] - check["Expected GP"]).abs() < 0.01
    return check


def branch_summary(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby("Branch", as_index=False).agg(
        LineItems=("Transaction ID", "size"),
        Transactions=("Transaction ID", "nunique"),
        Units=("Quantity", "sum"),
        Revenue=("Line Revenue (USD)", "sum"),
        RecordedCost=(
            "Line Revenue (USD)",
            lambda s: (s - df.loc[s.index, "Line Gross Profit (USD)"]).sum(),
        ),
        GrossProfit=("Line Gross Profit (USD)", "sum"),
        DiscountDollars=(
            "Unit Price (USD)",
            lambda s: (
                (df.loc[s.index, "Unit Price (USD)"] * df.loc[s.index, "Quantity"])
                - df.loc[s.index, "Line Revenue (USD)"]
            ).sum(),
        ),
    )
    g["GrossMarginPct"] = (g["GrossProfit"] / g["Revenue"] * 100).round(2)
    g["AvgBasketLines"] = (g["LineItems"] / g["Transactions"]).round(2)
    g["AvgBasketRevenue"] = (g["Revenue"] / g["Transactions"]).round(2)
    g["AvgBasketGP"] = (g["GrossProfit"] / g["Transactions"]).round(2)
    total = pd.DataFrame([{
        "Branch": "ALL",
        "LineItems": g["LineItems"].sum(),
        "Transactions": g["Transactions"].sum(),
        "Units": g["Units"].sum(),
        "Revenue": g["Revenue"].sum(),
        "RecordedCost": g["RecordedCost"].sum(),
        "GrossProfit": g["GrossProfit"].sum(),
        "DiscountDollars": g["DiscountDollars"].sum(),
        "GrossMarginPct": round(g["GrossProfit"].sum() / g["Revenue"].sum() * 100, 2),
        "AvgBasketLines": round(g["LineItems"].sum() / g["Transactions"].sum(), 2),
        "AvgBasketRevenue": round(g["Revenue"].sum() / g["Transactions"].sum(), 2),
        "AvgBasketGP": round(g["GrossProfit"].sum() / g["Transactions"].sum(), 2),
    }])
    return pd.concat([g.sort_values("Branch").reset_index(drop=True), total], ignore_index=True)


def category_share(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for branch, sub in df.groupby("Branch"):
        cat = sub.groupby("Category").agg(
            Revenue=("Line Revenue (USD)", "sum"),
            GrossProfit=("Line Gross Profit (USD)", "sum"),
            Units=("Quantity", "sum"),
        )
        cat["RevenueSharePct"] = (cat["Revenue"] / cat["Revenue"].sum() * 100).round(2)
        cat["GPSharePct"] = (cat["GrossProfit"] / cat["GrossProfit"].sum() * 100).round(2)
        cat["Branch"] = branch
        rows.append(cat.reset_index())
    out = pd.concat(rows, ignore_index=True)
    return out[["Branch", "Category", "Units", "Revenue", "GrossProfit",
                "RevenueSharePct", "GPSharePct"]].sort_values(
        ["Branch", "Revenue"], ascending=[True, False]
    ).reset_index(drop=True)


def price_cost_stability(df: pd.DataFrame) -> pd.DataFrame:
    g = df.groupby(["Branch", "Product"], as_index=False).agg(
        PriceMin=("Unit Price (USD)", "min"),
        PriceMax=("Unit Price (USD)", "max"),
        CostMin=("Unit Cost (USD)", "min"),
        CostMax=("Unit Cost (USD)", "max"),
        Lines=("Transaction ID", "size"),
        Units=("Quantity", "sum"),
    )
    g["PriceConstant"] = (g["PriceMax"] - g["PriceMin"]).abs() < 0.005
    g["CostConstant"] = (g["CostMax"] - g["CostMin"]).abs() < 0.005
    return g


def duplicate_check(df: pd.DataFrame) -> dict:
    dup_mask = df.duplicated(subset=df.columns.tolist(), keep=False)
    return {
        "total_rows": len(df),
        "fully_duplicate_rows": int(dup_mask.sum()),
        "share_pct": round(dup_mask.sum() / len(df) * 100, 3),
    }


def main() -> int:
    print("=" * 70)
    print("STEP 1 — BASELINE VALIDATION (Garden, Harbour, Uptown)")
    print("=" * 70)
    df = load()
    print(f"Loaded {len(df):,} line items, {df['Transaction ID'].nunique():,} transactions")
    print(f"Date range: {df['Date'].min().date()} → {df['Date'].max().date()}")
    print(f"Products: {df['Product'].nunique()} unique across all branches")

    check = sanity_check_columns(df)
    n_rev_bad = (~check["Revenue OK"]).sum()
    n_gp_bad = (~check["GP OK"]).sum()
    print(f"\n[1] Supplied vs recomputed columns:")
    print(f"    rows where supplied revenue differs from recomputed: {n_rev_bad}")
    print(f"    rows where supplied GP differs from recomputed:      {n_gp_bad}")
    check.to_csv(OUT / "01_lineitem_vs_given.csv", index=False)

    summary = branch_summary(df)
    print("\n[2] Branch summary:")
    cols = ["Branch", "LineItems", "Transactions", "Units", "Revenue",
            "RecordedCost", "GrossProfit", "DiscountDollars",
            "GrossMarginPct", "AvgBasketRevenue", "AvgBasketGP"]
    print(summary[cols].to_string(index=False))
    summary.to_csv(OUT / "01_branch_summary.csv", index=False)

    cat = category_share(df)
    cat.to_csv(OUT / "01_category_share.csv", index=False)

    stab = price_cost_stability(df)
    stab.to_csv(OUT / "01_product_price_cost_stability.csv", index=False)
    print(f"\n[4] Price constant in {stab['PriceConstant'].sum()}/{len(stab)} (Branch, Product) groups")
    print(f"    Cost  constant in {stab['CostConstant'].sum()}/{len(stab)} (Branch, Product) groups")

    dup = duplicate_check(df)
    print(f"\n[5] Duplicate rows: {dup['fully_duplicate_rows']:,} ({dup['share_pct']}%)")
    if dup["fully_duplicate_rows"] > 0:
        no_dup = df.drop_duplicates()
        print(f"    total revenue all rows:    {df['Line Revenue (USD)'].sum():,.2f}")
        print(f"    total revenue unique rows: {no_dup['Line Revenue (USD)'].sum():,.2f}")

    print("\nDone. Every number above is an OBSERVED FACT.")
    return 0


if __name__ == "__main__":
    sys.exit(main())