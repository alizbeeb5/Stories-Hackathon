"""
05_feasibility.py
=================
Step 5 — Max absorbable implementation cost, alternative explanations,
and dataset can/cannot test.
"""

from __future__ import annotations
import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output" / "tables"
OUT.mkdir(parents=True, exist_ok=True)

WINDOW_MONTHS = 6


def max_absorbable() -> pd.DataFrame:
    sc = pd.read_csv(OUT / "02_scenario_table.csv")
    rows = []
    for _, r in sc.iterrows():
        uplift = r["Scenario_Uplift_dollars"]
        if uplift <= 0: continue
        annual = uplift * (12 / WINDOW_MONTHS)
        rows.append({
            "Reference_Branch": r["Reference_Branch"],
            "Closure_alpha_pct": r["Closure_alpha_pct"],
            "Six_Month_Uplift_dollars": round(uplift, 2),
            "Annualized_Uplift_dollars": round(annual, 2),
            "Max_One_Time_Cost_6mo": round(uplift, 2),
            "Max_Annual_Recurring_Cost": round(annual, 2),
            "Max_Monthly_Recurring_Cost": round(annual / 12, 2),
            "Evidence_Label": "accounting scenario (break-even)",
        })
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 70); print("STEP 5 — FEASIBILITY & REVERSAL CONDITIONS"); print("=" * 70)
    ma = max_absorbable()
    ma.to_csv(OUT / "05_max_absorbable_costs.csv", index=False)
    print("\nMax absorbable cost per scenario:")
    print(ma.to_string(index=False))

    rows = [
        {"Alternative_Explanation": "Unfavourable supplier/procurement at Garden.",
         "Dataset_Verdict": "CONSISTENT",
         "Would_Reverse_Conclusion": "If supplier invoices show quality/service offsets.",
         "Evidence_Needed": "Supplier invoices, contracts, tender documents."},
        {"Alternative_Explanation": "Garden uses larger portions or better ingredients.",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Closing the gap means lowering quality.",
         "Evidence_Needed": "Recipe cards, portion-weight logs, customer surveys."},
        {"Alternative_Explanation": "Cost-allocation artefact (shared services booked to Garden).",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Gap is a corporate decision, not Garden's lever.",
         "Evidence_Needed": "Cost-allocation policy, inter-branch transfers, shared P&L."},
        {"Alternative_Explanation": "Garden's lower volume blocks same supplier pricing.",
         "Dataset_Verdict": "PARTIAL",
         "Would_Reverse_Conclusion": "100% closure unachievable for Garden alone.",
         "Evidence_Needed": "Supplier price tiers, monthly volumes, quotes at Garden's volume."},
        {"Alternative_Explanation": "High waste/shrinkage already inside recorded cost.",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Practical ceiling on closure may be 25-50%.",
         "Evidence_Needed": "Waste logs, inventory reconciliations, expiry data."},
        {"Alternative_Explanation": "Low-price strategy; cost gap is the unavoidable consequence.",
         "Dataset_Verdict": "REFUTED",
         "Would_Reverse_Conclusion": "Garden prices are LOWER than both refs but margin is also LOWER — strategy is failing.",
         "Evidence_Needed": "Strategy memo if any; otherwise disproved."},
        {"Alternative_Explanation": "Data entry error / one-off inventory revaluation.",
         "Dataset_Verdict": "REFUTED",
         "Would_Reverse_Conclusion": "Cost is constant within (Branch, Product) across 51,177 rows; not a one-off.",
         "Evidence_Needed": "Already disproved; supplier invoices would confirm."},
    ]
    alt = pd.DataFrame(rows)
    alt.to_csv(OUT / "05_alternative_explanations.csv", index=False)
    print(f"\nWrote {OUT / '05_alternative_explanations.csv'}")

    can_cannot = pd.DataFrame([
        ("Revenue, GP, margin per branch", "CAN", "Sum line items."),
        ("Cost gap magnitude by product", "CAN", "Compare same product across branches."),
        ("Cost gap uniformity", "CAN", "Cost ratio G/H = 1.43±0.01 across 45 products."),
        ("Discount dollars by branch and order type", "CAN", "Per-line (Unit Price × Qty − Line Revenue)."),
        ("Fixed-qty price-matching effect", "CAN", "Re-price Garden to reference, keep costs/quantities."),
        ("Linear break-even volume multiplier", "CAN (under linear demand)", "Closed form on unit GP at new prices."),
        ("Customer response to price changes", "CANNOT", "No A/B or cohort data."),
        ("Portion size, ingredient quality", "CANNOT", "No recipe/weight data."),
        ("Supplier identity, contract terms", "CANNOT", "No invoice data."),
        ("Cost allocation across branches", "CANNOT", "No shared-services breakdown."),
        ("Waste, shrinkage, expiry", "CANNOT", "No inventory logs."),
        ("One-off vs structural cost gap", "CANNOT (uniformity suggests structural)", "Need supplier price time-series."),
    ], columns=["Question", "Verdict", "Why / what's needed"])
    can_cannot.to_csv(OUT / "05_dataset_can_and_cannot.csv", index=False)
    print(f"\nWrote {OUT / '05_dataset_can_and_cannot.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())