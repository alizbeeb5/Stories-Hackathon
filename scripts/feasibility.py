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

HYPOTHETICAL_VOLUME_MULTIPLIERS = [1.0, 0.95, 0.90, 0.80]


def max_absorbable() -> pd.DataFrame:
    sc = pd.read_csv(OUT / "02_scenario_table.csv")
    rows = []
    for _, r in sc.iterrows():
        # Reconstruct from the unrounded gap rather than the rounded display GP.
        gp0 = r["Recorded_Garden_GP"]
        scenario_gp = gp0 + r["Closure_alpha_pct"] / 100 * r["Cost_Gap_dollars"]
        for v in HYPOTHETICAL_VOLUME_MULTIPLIERS:
            capacity = v * scenario_gp - gp0
            rows.append({
                "Reference_Branch": r["Reference_Branch"],
                "Closure_alpha_pct": r["Closure_alpha_pct"],
                "Hypothetical_Volume_Multiplier": v,
                "Scenario_GP_at_observed_quantity": round(scenario_gp, 2),
                "Kmax_total_additional_expenses_6mo": round(capacity, 2),
                "Nonnegative_expense_budget_possible": capacity >= 0,
                "Evidence_Label": "hypothetical volume sensitivity; mix and unit economics fixed",
            })
    return pd.DataFrame(rows)


def main() -> int:
    print("=" * 70); print("STEP 5 — FEASIBILITY & REVERSAL CONDITIONS"); print("=" * 70)
    ma = max_absorbable()
    ma.to_csv(OUT / "05_max_absorbable_costs.csv", index=False)
    print("\nMax absorbable cost per scenario:")
    print(ma.to_string(index=False))

    rows = [
        {"Alternative_Explanation": "Avoidable supplier/purchasing premium at Garden.",
         "Dataset_Verdict": "COMPATIBLE; CAUSE UNVERIFIED",
         "Would_Reverse_Conclusion": "Comparable delivered quotes do not reduce actual spend after fees, service terms and implementation expenses.",
         "Evidence_Needed": "Supplier invoices, contracts and comparable quotes at Garden quantities.",
         "Stories_Action_if_confirmed": "Obtain comparable supplier terms and test actual cash savings in a bounded pilot."},
        {"Alternative_Explanation": "Garden uses larger portions or better ingredients.",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Closing the gap means lowering quality.",
         "Evidence_Needed": "Recipe cards, portion-weight logs, ingredient specifications and blind quality checks.",
         "Stories_Action_if_confirmed": "Compare like-for-like quality and portions before recommending cost changes."},
        {"Alternative_Explanation": "Cost-allocation artefact (shared services booked to Garden).",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Gap is a corporate decision, not Garden's lever.",
         "Evidence_Needed": "Cost-allocation policy, inter-branch transfers, shared P&L and cash ledger.",
         "Stories_Action_if_confirmed": "Correct branch performance comparisons; count savings only where expenses actually fall."},
        {"Alternative_Explanation": "Quantity-dependent supplier tiers restrict comparable terms.",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Lower prices require minimum orders whose waste or holding costs outweigh savings.",
         "Evidence_Needed": "Supplier tiers, delivery frequency, minimum orders and quotes at Garden's purchasing volume.",
         "Stories_Action_if_confirmed": "Use terms available at actual order volumes; include extra inventory and waste costs."},
        {"Alternative_Explanation": "High waste/shrinkage already inside recorded cost.",
         "Dataset_Verdict": "CANNOT_TEST",
         "Would_Reverse_Conclusion": "Supplier savings are offset by extra waste, or the recorded gap reflects waste already allocated to unit cost.",
         "Evidence_Needed": "Waste logs, inventory reconciliations, expiry data and unit-cost construction; no closure ceiling is identifiable here.",
         "Stories_Action_if_confirmed": "Measure saleable yield and actual waste expense; avoid double counting waste already included in cost."},
        {"Alternative_Explanation": "Low-price strategy; cost gap is the unavoidable consequence.",
         "Dataset_Verdict": "CANNOT_TEST STRATEGY OR CAUSAL LINK",
         "Would_Reverse_Conclusion": "Garden prices are below Harbour and above Uptown for all 45 products; this does not identify strategic success or explain the cost gap.",
         "Evidence_Needed": "Pricing objectives, customer-response evidence and like-for-like offers.",
         "Stories_Action_if_confirmed": "Judge price alternatives using controlled sales and realized contribution evidence."},
        {"Alternative_Explanation": "Systematic data entry, costing-rule or inventory-valuation issue.",
         "Dataset_Verdict": "CANNOT_TEST SOURCE ACCURACY",
         "Would_Reverse_Conclusion": "Fixed branch-product schedules can reproduce a systematic costing error; repeated rows do not validate invoices.",
         "Evidence_Needed": "Source invoices, inventory valuation rules, allocation records and reconciliation to the general ledger.",
         "Stories_Action_if_confirmed": "Repair measurement and rerun comparisons; do not label a ledger correction as cash saving."},
        {"Alternative_Explanation": "Cause of the recorded cost gap remains unresolved.",
         "Dataset_Verdict": "UNRESOLVED",
         "Would_Reverse_Conclusion": "Unknown cash recoverability or quality/service equivalence prevents a supplier-change recommendation.",
         "Evidence_Needed": "Reconciled actual purchases plus comparable terms, portions, quality, waste and delivery records.",
         "Stories_Action_if_confirmed": "Retain current supplier while obtaining evidence; no unconditional supplier switch."},
    ]
    alt = pd.DataFrame(rows)
    alt.to_csv(OUT / "05_alternative_explanations.csv", index=False)
    print(f"\nWrote {OUT / '05_alternative_explanations.csv'}")

    can_cannot = pd.DataFrame([
        ("Revenue, GP, margin per branch", "CAN", "Sum line items."),
        ("Cost gap magnitude by product", "CAN", "Compare same product across branches."),
        ("Cost schedule regularity", "CAN", "All 45 Garden product costs equal Harbour cost times 1.43 rounded to cents; this does not identify the cause."),
        ("Discount dollars by branch and order type", "CAN", "Per-line (Unit Price × Qty − Line Revenue)."),
        ("Fixed-qty price-matching effect", "CAN", "Re-price Garden to reference, keep costs/quantities."),
        ("Break-even volume multiplier and implementation budget", "CAN (conditional accounting identity)", "v_break_even=(G0+K)/Gs; Kmax=v*Gs-G0. Quantities scale while product mix and unit economics remain fixed."),
        ("Customer response to price changes", "CANNOT", "No A/B or cohort data."),
        ("Portion size, ingredient quality", "CANNOT", "No recipe/weight data."),
        ("Supplier identity, contract terms", "CANNOT", "No invoice data."),
        ("Cost allocation across branches", "CANNOT", "No shared-services breakdown."),
        ("Waste, shrinkage, expiry", "CANNOT", "No inventory logs."),
        ("One-off vs persistent real cost cause", "CANNOT", "Recorded schedules persist; source invoices and costing history are required to identify their cause."),
    ], columns=["Question", "Verdict", "Why / what's needed"])
    can_cannot.to_csv(OUT / "05_dataset_can_and_cannot.csv", index=False)
    print(f"\nWrote {OUT / '05_dataset_can_and_cannot.csv'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
