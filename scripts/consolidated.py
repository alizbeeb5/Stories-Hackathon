"""Compare Garden actions with implementation costs and volume sensitivity.

All scenarios cover the observed six months, January--June 2026. They are
accounting counterfactuals, not forecasts. The volume multiplier scales quantities
while product mix and scenario unit economics remain fixed. No customer-response
function is estimated.

For every scenario, G_s is gross profit at Garden's observed quantities:
    incremental benefit = v * G_s - G_0 - K
    break-even v = (G_0 + K) / G_s
    maximum additional expenses = v * G_s - G_0

The exact recorded baseline anchors all changes. Repricing adds the modeled
price difference to recorded revenue; it therefore retains the $0.755 aggregate
line-rounding residual instead of treating it as an economic gain or loss.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "stories_transactions.csv"
OUT = ROOT / "output" / "tables"
DECISION_OUT = ROOT / "outputs" / "decision"
G0 = 46_794.49
VOLUMES = [0.85, 0.90, 0.95, 1.00, 1.05, 1.10]
EXPENSES = [0.0, 1_000.0, 2_500.0, 5_000.0]
CLOSURES = [0.25, 0.50, 1.00]
REFERENCES = ["Harbour", "Uptown"]


def load_inputs() -> tuple[pd.DataFrame, dict]:
    """Validate matching and accounting identities before constructing scenarios."""
    data = pd.read_csv(DATA)
    garden = data.loc[data["Branch"].eq("Garden")].copy()
    price_col, cost_col = "Unit Price (USD)", "Unit Cost (USD)"
    assert not garden.empty
    assert set(data["Branch"]) == {"Garden", "Harbour", "Uptown"}
    assert garden["Quantity"].gt(0).all()
    assert garden["Discount Rate"].between(0, 1).all()
    assert data.groupby(["Branch", "Product"])[[price_col, cost_col]].nunique().eq(1).all().all(), (
        "Unit prices/costs vary within branch/product; a first-value reference is invalid."
    )
    assert math.isclose(garden["Line Gross Profit (USD)"].sum(), G0, abs_tol=1e-8)
    recorded_revenue = float(garden["Line Revenue (USD)"].sum())
    recorded_cost = recorded_revenue - G0
    assert math.isclose((garden["Quantity"] * garden[cost_col]).sum(), recorded_cost, abs_tol=1e-8)
    reconstructed_revenue = float((garden[price_col] * garden["Quantity"] * (1 - garden["Discount Rate"])).sum())
    inputs = {
        "period_start": str(garden["Date"].min()),
        "period_end": str(garden["Date"].max()),
        "observed_garden_gp_dollars": G0,
        "observed_garden_revenue_dollars": recorded_revenue,
        "observed_garden_cost_dollars": recorded_cost,
        "observed_garden_units": int(garden["Quantity"].sum()),
        "observed_garden_transactions": int(garden["Transaction ID"].nunique()),
        "recorded_minus_reconstructed_revenue_dollars": recorded_revenue - reconstructed_revenue,
        "recorded_discount_dollars": float((garden[price_col] * garden["Quantity"] - garden["Line Revenue (USD)"]).sum()),
        "references": {},
    }
    for ref in REFERENCES:
        reference = data.loc[data["Branch"].eq(ref)].groupby("Product")[[price_col, cost_col]].first()
        ref_price = garden["Product"].map(reference[price_col])
        ref_cost = garden["Product"].map(reference[cost_col])
        assert ref_price.notna().all() and ref_cost.notna().all(), "Unmatched Garden products."
        assert (garden[price_col] < ref_price).all() if ref == "Harbour" else (garden[price_col] > ref_price).all()
        assert (garden[cost_col] > ref_cost).all()
        inputs["references"][ref] = {
            "full_cost_gap_dollars": float(((garden[cost_col] - ref_cost) * garden["Quantity"]).sum()),
            "price_change_revenue_dollars": float(((ref_price - garden[price_col]) * garden["Quantity"] * (1 - garden["Discount Rate"])).sum()),
        }
    return garden, inputs


def build(inputs: dict | None = None) -> pd.DataFrame:
    """One complete, directly comparable table (16 actions/benchmarks)."""
    if inputs is None:
        _, inputs = load_inputs()
    rows = []

    def append(scenario_id, description, scenario_type, ref="None", alpha=0.0,
               price_change=False, no_discounts=False):
        ref_values = inputs["references"].get(ref, {})
        saving = alpha * ref_values.get("full_cost_gap_dollars", 0.0)
        price_delta = ref_values.get("price_change_revenue_dollars", 0.0) if price_change else 0.0
        discount_delta = inputs["recorded_discount_dollars"] if no_discounts else 0.0
        gs = G0 + saving + price_delta + discount_delta
        if scenario_type == "Baseline":
            evidence = "Observed baseline; changing v or K creates a hypothetical baseline stress case."
            gate = "No implementation; comparator benefit is zero at v=1, K=0."
        elif no_discounts:
            evidence = "Fixed-quantity benchmark; response to removing discounts is unknown."
            gate = "Verify discount eligibility and test actual sales/mix response before removal."
        else:
            evidence = "Accounting scenario; neither cost achievability nor sales response is estimated."
            gate = "Confirm comparable, avoidable cash costs." if alpha else "Test actual sales, mix and quality response to price change."
            if alpha and price_change:
                gate += " Test actual sales, mix and quality response to price change."
        rows.append({
            "Scenario_ID": scenario_id,
            "Scenario_Description": description,
            "Scenario_Type": scenario_type,
            "Reference_Branch": ref,
            "Cost_Closure_alpha_pct": alpha * 100,
            "Price_Move_vs_Garden": (f"To {ref} ({'increase' if ref == 'Harbour' else 'decrease'})" if price_change else "Garden prices"),
            "Discount_Policy": "Remove recorded discounts" if no_discounts else "Observed Garden discount rates retained",
            "Scenario_GP_Gs_dollars": gs,
            "Observed_Garden_GP_G0_dollars": G0,
            "Fixed_Qty_Cost_Savings_dollars": saving,
            "Fixed_Qty_Price_Revenue_Change_dollars": price_delta,
            "Fixed_Qty_Discount_Removal_dollars": discount_delta,
            "Cost_Reduction_pct_of_Garden_Recorded_Cost": saving / inputs["observed_garden_cost_dollars"] * 100,
            "Benefit_v100_K0_dollars": gs - G0,
            "Benefit_v095_K0_dollars": 0.95 * gs - G0,
            "Benefit_v095_K1000_dollars": 0.95 * gs - G0 - 1000,
            "Break_Even_v_K0": G0 / gs,
            "Break_Even_v_K1000": (G0 + 1000) / gs,
            "Break_Even_v_K2500": (G0 + 2500) / gs,
            "Break_Even_v_K5000": (G0 + 5000) / gs,
            "Volume_Change_at_Break_Even_K0_pct": (G0 / gs - 1) * 100,
            "Evidence_Label": evidence,
            "Evidence_Gate": gate,
            "Assumptions": "Six months; quantities scale while product mix and scenario unit economics remain fixed; K includes all additional implementation expenses; volume and expense levels are hypothetical, not estimated customer responses.",
        })

    append("BASE", "Do nothing (observed Garden)", "Baseline")
    for ref in REFERENCES:
        append(f"{ref[0]}-P", f"Match {ref} prices only", "Price only", ref, price_change=True)
    for ref in REFERENCES:
        for alpha in CLOSURES:
            append(f"{ref[0]}-C{int(alpha*100):03d}", f"Close {int(alpha*100)}% of {ref} cost gap; keep Garden prices", "Cost only", ref, alpha)
    for ref in REFERENCES:
        for alpha in CLOSURES:
            append(f"{ref[0]}-CP{int(alpha*100):03d}", f"Close {int(alpha*100)}% of {ref} cost gap and match {ref} prices", "Cost and price", ref, alpha, price_change=True)
    append("NO-DISC", "Remove recorded discounts (fixed-quantity benchmark)", "Discount benchmark", no_discounts=True)
    result = pd.DataFrame(rows)
    assert len(result) == 16 and result["Scenario_ID"].is_unique
    assert result["Scenario_GP_Gs_dollars"].gt(0).all()
    assert result["Scenario_Type"].eq("Price only").sum() == 2
    return result


def sensitivity_table(scenarios: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for scenario in scenarios.to_dict("records"):
        gs = scenario["Scenario_GP_Gs_dollars"]
        for v in VOLUMES:
            k_max = v * gs - G0
            for k in EXPENSES:
                rows.append({
                    "Scenario_ID": scenario["Scenario_ID"],
                    "Scenario_Description": scenario["Scenario_Description"],
                    "Hypothetical_Volume_Multiplier_v": v,
                    "Hypothetical_Additional_Expenses_K_dollars": k,
                    "Scenario_GP_at_Observed_Quantities_Gs_dollars": gs,
                    "Scenario_GP_at_Scaled_Quantities_vGs_dollars": v * gs,
                    "Incremental_Benefit_dollars": k_max - k,
                    "Break_Even_Volume_Multiplier": (G0 + k) / gs,
                    "Maximum_Additional_Expenses_Kmax_dollars": k_max,
                    "Result_vs_Observed_Baseline": "Positive" if k_max > k else "Negative" if k_max < k else "Break-even",
                    "Scenario_Status": "Hypothetical stress case; not an estimated customer response",
                })
    result = pd.DataFrame(rows)
    assert len(result) == len(scenarios) * len(VOLUMES) * len(EXPENSES)
    return result


def break_even_tables(scenarios: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    be_rows, km_rows = [], []
    for scenario in scenarios.to_dict("records"):
        gs = scenario["Scenario_GP_Gs_dollars"]
        be_row = {"Scenario_ID": scenario["Scenario_ID"], "Scenario_Description": scenario["Scenario_Description"]}
        km_row = be_row.copy()
        for k in EXPENSES:
            be_row[f"Retained_Volume_pct_at_K{int(k)}"] = (G0 + k) / gs * 100
        for v in VOLUMES:
            km_row[f"Kmax_dollars_at_v{int(round(v*100)):03d}"] = v * gs - G0
        be_rows.append(be_row)
        km_rows.append(km_row)
    return pd.DataFrame(be_rows), pd.DataFrame(km_rows)


def pairwise_thresholds(scenarios: pd.DataFrame) -> pd.DataFrame:
    """Volume needed by B to equal A, with different volume and expense levels.

    v_B * G_B - K_B = v_A * G_A - K_A
    v_B = (v_A * G_A + (K_B - K_A)) / G_B
    The common observed baseline cancels. B wins strictly above this threshold.
    """
    by_id = scenarios.set_index("Scenario_ID")
    rows = []
    for a_id, b_id in [("H-C025", "H-P"), ("U-C025", "H-P"), ("H-C025", "H-CP025")]:
        ga = float(by_id.loc[a_id, "Scenario_GP_Gs_dollars"])
        gb = float(by_id.loc[b_id, "Scenario_GP_Gs_dollars"])
        for va in [0.95, 1.00]:
            for expense_delta in [-1_000, 0, 1_000, 2_500]:
                threshold = (va * ga + expense_delta) / gb
                rows.append({
                    "Alternative_A": a_id,
                    "Alternative_B": b_id,
                    "Hypothetical_Volume_A": va,
                    "Hypothetical_Expense_Difference_KB_minus_KA_dollars": expense_delta,
                    "Volume_B_to_equal_A": threshold,
                    "Volume_B_change_from_observed_pct": (threshold - 1) * 100,
                    "Decision_Rule": "B outperforms A strictly above this B volume threshold, conditional on evidence/achievability and fixed mix/unit economics; neither action is automatically positive versus observed baseline.",
                })
    return pd.DataFrame(rows)


def validate(scenarios: pd.DataFrame, sensitivity: pd.DataFrame, inputs: dict) -> dict:
    by_id = scenarios.set_index("Scenario_ID")
    assert by_id.loc["BASE", "Scenario_GP_Gs_dollars"] == G0
    assert math.isclose(by_id.loc["NO-DISC", "Benefit_v100_K0_dollars"], 555.90, abs_tol=1e-8)
    assert math.isclose(by_id.loc["H-C025", "Benefit_v100_K0_dollars"], 3980.8675, abs_tol=1e-8)
    assert math.isclose(by_id.loc["H-C025", "Benefit_v095_K0_dollars"], 1442.099625, abs_tol=1e-8)
    for ref in REFERENCES:
        for alpha in CLOSURES:
            code = f"{int(alpha*100):03d}"
            assert math.isclose(
                by_id.loc[f"{ref[0]}-CP{code}", "Scenario_GP_Gs_dollars"] - by_id.loc[f"{ref[0]}-C{code}", "Scenario_GP_Gs_dollars"],
                inputs["references"][ref]["price_change_revenue_dollars"], abs_tol=1e-8,
            )
    for row in sensitivity.to_dict("records"):
        gs, v, k = row["Scenario_GP_at_Observed_Quantities_Gs_dollars"], row["Hypothetical_Volume_Multiplier_v"], row["Hypothetical_Additional_Expenses_K_dollars"]
        assert math.isclose(row["Incremental_Benefit_dollars"], v * gs - G0 - k, abs_tol=1e-8)
        assert math.isclose(row["Break_Even_Volume_Multiplier"] * gs - G0 - k, 0, abs_tol=1e-8)
        assert math.isclose(v * gs - G0 - row["Maximum_Additional_Expenses_Kmax_dollars"], 0, abs_tol=1e-8)
    for _, group in sensitivity.groupby(["Scenario_ID", "Hypothetical_Additional_Expenses_K_dollars"]):
        assert group.sort_values("Hypothetical_Volume_Multiplier_v")["Incremental_Benefit_dollars"].is_monotonic_increasing
    for _, group in sensitivity.groupby(["Scenario_ID", "Hypothetical_Volume_Multiplier_v"]):
        assert group.sort_values("Hypothetical_Additional_Expenses_K_dollars")["Incremental_Benefit_dollars"].is_monotonic_decreasing
    return {
        "status": "passed",
        "scenario_count": len(scenarios),
        "sensitivity_cells": len(sensitivity),
        "checks": ["observed accounting identities", "reference coverage and fixed branch/product unit prices/costs", "Garden price ordering: below Harbour, above Uptown", "complete 16-scenario comparison", "cost/price decomposition identities", "break-even and maximum expense identities", "volume/expense monotonicity", "requested H25 illustrative figures"],
        "rounding_policy": "Keep full floating-point precision during calculation; CSV dollar fields retain six decimals; display dollars to two decimals and percentages to two decimals. Repricing preserves the exact observed baseline and its aggregate line-rounding residual.",
        "inputs": inputs,
        "hypothetical_volume_multipliers": VOLUMES,
        "hypothetical_implementation_expenses_dollars": EXPENSES,
    }


def main() -> int:
    _, inputs = load_inputs()
    scenarios = build(inputs)
    sensitivity = sensitivity_table(scenarios)
    break_even, max_expenses = break_even_tables(scenarios)
    crossovers = pairwise_thresholds(scenarios)
    validation = validate(scenarios, sensitivity, inputs)
    DECISION_OUT.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for name, table in [
        ("consolidated_scenarios.csv", scenarios),
        ("sensitivity_long.csv", sensitivity),
        ("break_even_volume.csv", break_even),
        ("maximum_implementation_expenses.csv", max_expenses),
        ("pairwise_action_thresholds.csv", crossovers),
    ]:
        table.to_csv(DECISION_OUT / name, index=False, float_format="%.6f")
    # Keep the existing report entry point synchronized with the complete table.
    scenarios.to_csv(OUT / "06_master_scenario_table.csv", index=False, float_format="%.6f")
    (DECISION_OUT / "calculation_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    print(scenarios[["Scenario_ID", "Scenario_GP_Gs_dollars", "Benefit_v100_K0_dollars", "Benefit_v095_K0_dollars", "Break_Even_v_K0"]].to_string(index=False, float_format=lambda value: f"{value:,.4f}"))
    print(f"Validated {len(scenarios)} scenarios and {len(sensitivity)} sensitivity cells; outputs: {DECISION_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
