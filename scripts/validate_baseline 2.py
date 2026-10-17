#!/usr/bin/env python3
"""Export the shared Stories baseline without altering supplied financial amounts.

Adapted from scripts/01_validate_baseline.py: distinct transaction IDs define
purchases; revenue and gross profit sum supplied line amounts. Recorded costs
sum quantity * recorded unit cost and must reconcile to revenue - gross profit.
All source rows are retained. Prices and costs must be constant within each
branch/product before a single schedule value can be exported.

Python 3.10+, standard library only. Run:
  python3 validate_baseline.py stories_transactions.csv --out output/tables

Financial arithmetic uses Decimal. Ratios are exported without presentation
rounding, at Decimal's explicitly selected 28 significant digits. Half-up and
half-even calculations diagnose revenue rounding only; neither replaces the
supplied revenue or gross profit.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
from pathlib import Path
from typing import Any

D = Decimal
ZERO = D("0")
CENT = D("0.01")
HALF_CENT = D("0.005")
REQUIRED = (
    "Transaction ID", "Date", "Time", "Branch", "Customer ID", "Order Type",
    "Product", "Category", "Quantity", "Unit Price (USD)", "Discount Rate",
    "Unit Cost (USD)", "Line Revenue (USD)", "Line Gross Profit (USD)",
)
NUMERIC = (
    "Quantity", "Unit Price (USD)", "Discount Rate", "Unit Cost (USD)",
    "Line Revenue (USD)", "Line Gross Profit (USD)",
)
METADATA = ("Date", "Time", "Branch", "Customer ID", "Order Type")
BRANCH_FIELDS = (
    "branch", "transactions", "units", "revenue_usd", "recorded_costs_usd",
    "gross_profit_usd", "gross_margin", "gross_profit_per_transaction_usd",
    "product_lines",
)
PRODUCT_FIELDS = (
    "branch", "product", "category", "unit_price_usd", "unit_cost_usd",
    "quantity", "revenue_usd", "recorded_costs_usd", "gross_profit_usd",
    "product_lines", "nominal_discount_usd", "realized_discount_usd",
)
STABILITY_FIELDS = (
    "branch", "product", "distinct_prices", "distinct_costs", "price_min_usd",
    "price_max_usd", "cost_min_usd", "cost_max_usd", "price_changes",
    "cost_changes", "months_observed", "month_list", "first_date", "last_date",
    "product_lines",
)


def _require(condition: bool, message: str) -> None:
    """Use explicit checks so validation also runs under python -O."""
    if not condition:
        raise ValueError(message)


def _sum(rows: list[dict[str, Any]], field: str) -> Decimal:
    return sum((row[field] for row in rows), ZERO)


def _write_csv(path: Path, records: list[dict[str, Any]], fields: tuple[str, ...]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)


def generate(source: Path, out: Path) -> dict[str, Any]:
    """Write two shared baseline tables, stability and quality checks; return provenance."""
    source, out = Path(source).resolve(), Path(out).resolve()
    _require(source != out and not source.is_relative_to(out),
             "Output directory must not contain the original source file.")
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = tuple(reader.fieldnames or ())
        _require(len(fields) == len(set(fields)), "Duplicate CSV column names.")
        _require(set(REQUIRED).issubset(fields), "Missing required source columns.")
        raw = list(reader)
    _require(bool(raw), "The input CSV has no product lines.")
    _require(all(None not in row and all(row[f] is not None for f in fields) for row in raw),
             "A CSV row has too many or too few fields.")
    missing = {f: sum(not row[f].strip() for row in raw) for f in REQUIRED}
    required_blank_count = sum(n for f, n in missing.items() if f != "Customer ID")
    _require(required_blank_count == 0,
             "A required field is blank; Customer ID is the only optional field.")

    rows: list[dict[str, Any]] = []
    for source_row, record in enumerate(raw, 2):
        parsed: dict[str, Any] = dict(record, source_row=source_row)
        for field in NUMERIC:
            parsed[field] = D(record[field])
            _require(parsed[field].is_finite(), f"Non-finite {field} at row {source_row}.")
        datetime.strptime(parsed["Date"], "%Y-%m-%d")
        datetime.strptime(parsed["Time"], "%H:%M:%S")
        _require(parsed["Quantity"] > 0 and parsed["Quantity"] == int(parsed["Quantity"]),
                 f"Quantity must be a positive integer at row {source_row}.")
        _require(ZERO <= parsed["Discount Rate"] <= D("1"),
                 f"Discount rate is outside [0, 1] at row {source_row}.")
        _require(parsed["Unit Price (USD)"] >= ZERO and parsed["Unit Cost (USD)"] >= ZERO,
                 f"Negative unit price or cost at row {source_row}.")
        rows.append(parsed)

    branch_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    product_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    transactions: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        branch_groups[row["Branch"]].append(row)
        product_groups[row["Branch"], row["Product"]].append(row)
        transactions[row["Transaction ID"]].append(row)
    metadata_conflicts = sum(
        len({row[field] for row in group}) > 1
        for group in transactions.values() for field in METADATA
    )
    _require(metadata_conflicts == 0, "A transaction ID has conflicting transaction metadata.")

    branch_table: list[dict[str, Any]] = []
    with localcontext() as context:
        context.prec = 28
        for branch, group in sorted(branch_groups.items()):
            revenue = _sum(group, "Line Revenue (USD)")
            gp = _sum(group, "Line Gross Profit (USD)")
            costs = sum((row["Quantity"] * row["Unit Cost (USD)"] for row in group), ZERO)
            count = len({row["Transaction ID"] for row in group})
            _require(revenue > ZERO, f"Nonpositive revenue for {branch}.")
            _require(revenue - costs == gp, f"Revenue/cost/GP reconciliation failed for {branch}.")
            branch_table.append(dict(
                branch=branch, transactions=count, units=_sum(group, "Quantity"),
                revenue_usd=revenue, recorded_costs_usd=costs, gross_profit_usd=gp,
                gross_margin=gp / revenue, gross_profit_per_transaction_usd=gp / D(count),
                product_lines=len(group),
            ))

    product_table: list[dict[str, Any]] = []
    stability: list[dict[str, Any]] = []
    for (branch, product), group in sorted(product_groups.items()):
        prices = sorted({row["Unit Price (USD)"] for row in group})
        costs = sorted({row["Unit Cost (USD)"] for row in group})
        categories = {row["Category"] for row in group}
        ordered = sorted(group, key=lambda row: (row["Date"], row["Time"], row["source_row"]))
        months = sorted({row["Date"][:7] for row in group})
        price_changes = sum(left["Unit Price (USD)"] != right["Unit Price (USD)"]
                            for left, right in zip(ordered, ordered[1:]))
        cost_changes = sum(left["Unit Cost (USD)"] != right["Unit Cost (USD)"]
                           for left, right in zip(ordered, ordered[1:]))
        stability.append(dict(
            branch=branch, product=product, distinct_prices=len(prices), distinct_costs=len(costs),
            price_min_usd=min(prices), price_max_usd=max(prices),
            cost_min_usd=min(costs), cost_max_usd=max(costs),
            price_changes=price_changes, cost_changes=cost_changes,
            months_observed=len(months), month_list=";".join(months),
            first_date=ordered[0]["Date"], last_date=ordered[-1]["Date"], product_lines=len(group),
        ))
        _require(len(prices) == 1 and len(costs) == 1,
                 f"Variable price/cost for {branch} / {product}; cannot export one fixed value.")
        _require(len(categories) == 1, f"Conflicting categories for {branch} / {product}.")
        price, cost = prices[0], costs[0]
        quantity = _sum(group, "Quantity")
        revenue, gp = _sum(group, "Line Revenue (USD)"), _sum(group, "Line Gross Profit (USD)")
        product_table.append(dict(
            branch=branch, product=product, category=next(iter(categories)),
            unit_price_usd=price, unit_cost_usd=cost, quantity=quantity,
            revenue_usd=revenue, recorded_costs_usd=quantity * cost, gross_profit_usd=gp,
            product_lines=len(group), nominal_discount_usd=sum((
                row["Quantity"] * row["Unit Price (USD)"] * row["Discount Rate"] for row in group
            ), ZERO), realized_discount_usd=quantity * price - revenue,
        ))

    for baseline in branch_table:
        subset = [row for row in product_table if row["branch"] == baseline["branch"]]
        for branch_field, product_field in (
            ("units", "quantity"), ("revenue_usd", "revenue_usd"),
            ("recorded_costs_usd", "recorded_costs_usd"), ("gross_profit_usd", "gross_profit_usd"),
            ("product_lines", "product_lines"),
        ):
            _require(baseline[branch_field] == _sum(subset, product_field),
                     f"Branch/product reconciliation failed for {baseline['branch']}: {branch_field}.")
    _require(sum(row["transactions"] for row in branch_table) == len(transactions),
             "A transaction ID occurs in more than one branch.")
    lookup = {row["branch"]: row for row in branch_table}
    _require(set(lookup) == {"Garden", "Harbour", "Uptown"}, "Unexpected branch set.")
    for field, expected in (("transactions", 11163), ("revenue_usd", D("99748.55")),
                            ("gross_profit_usd", D("46794.49"))):
        _require(lookup["Garden"][field] == expected, f"Garden baseline check failed: {field}.")
    _require(len(product_table) == 135, "Expected 135 branch/product rows.")

    row_counts = Counter(tuple(row[field] for field in fields) for row in raw)
    duplicate_sizes = [count for count in row_counts.values() if count > 1]
    gp_mismatches = half_up_mismatches = half_even_mismatches = outside_half_cent = ties = 0
    half_up_delta = half_even_delta = ZERO
    for row in rows:
        exact = row["Quantity"] * row["Unit Price (USD)"] * (D("1") - row["Discount Rate"])
        supplied = row["Line Revenue (USD)"]
        up_delta = supplied - exact.quantize(CENT, rounding=ROUND_HALF_UP)
        even_delta = supplied - exact.quantize(CENT, rounding=ROUND_HALF_EVEN)
        half_up_mismatches += up_delta != ZERO
        half_even_mismatches += even_delta != ZERO
        half_up_delta += up_delta
        half_even_delta += even_delta
        outside_half_cent += abs(supplied - exact) > HALF_CENT
        ties += exact * D("100") % D("1") == D("0.5")
        gp_mismatches += supplied - row["Quantity"] * row["Unit Cost (USD)"] != row["Line Gross Profit (USD)"]
    _require(gp_mismatches == 0 and outside_half_cent == 0,
             "Source arithmetic has discrepancies beyond accepted cent rounding.")

    quality: list[dict[str, Any]] = []
    def check(name: str, observed: Any, interpretation: str) -> None:
        quality.append(dict(check=name, observed=observed, interpretation=interpretation))

    check("source_sha256", source_hash, "Hash of unchanged source CSV bytes; all source rows retained.")
    check("source_product_lines", len(rows), "Rows are product lines, not purchases.")
    check("distinct_transaction_ids", len(transactions), "Distinct IDs define purchases; branch counts reconcile globally.")
    check("blank_required_fields_except_customer_id", required_blank_count, "Zero blanks required; Customer ID is optional.")
    check("blank_customer_ids", missing["Customer ID"], "Informational; absence does not affect branch cost calculations.")
    check("transaction_metadata_conflicts", metadata_conflicts, "Count of transaction/metadata fields having more than one distinct value.")
    check("gross_profit_arithmetic_mismatches", gp_mismatches, "Supplied GP equals supplied revenue minus quantity times recorded unit cost.")
    check("revenue_outside_half_cent", outside_half_cent, "No supplied revenue is more than $0.005 from exact undiscounted-price calculation after discount.")
    check("revenue_half_up_mismatches", half_up_mismatches, "Diagnostic only: compares supplied revenue with exact Decimal ROUND_HALF_UP.")
    check("revenue_half_up_total_delta_usd", half_up_delta, "Supplied revenue minus diagnostic half-up revenue; supplied amounts preserved.")
    check("revenue_half_even_mismatches", half_even_mismatches, "Diagnostic only: compares supplied revenue with exact Decimal ROUND_HALF_EVEN.")
    check("revenue_half_even_total_delta_usd", half_even_delta, "Supplied revenue minus diagnostic half-even revenue; supplied amounts preserved.")
    check("exact_half_cent_revenue_ties", ties, "Unrounded revenue lies exactly halfway between two cents; does not identify the source rounding implementation.")
    check("exact_duplicate_groups", len(duplicate_sizes), "Number of identical full-row groups with at least two rows.")
    check("exact_duplicate_rows_in_groups", sum(duplicate_sizes), "264 rows belong to 132 identical pairs, counting both copies.")
    check("exact_duplicate_excess_rows", sum(count - 1 for count in duplicate_sizes), "132 excess copies; retaining one per group is a sensitivity, not a verified correction.")
    check("branch_product_groups", len(stability), "135 fixed branch/product schedules; repeated transactions reuse those schedules.")
    check("variable_price_groups", sum(row["distinct_prices"] != 1 for row in stability), "Zero observed price variation within each branch/product over the six months.")
    check("variable_cost_groups", sum(row["distinct_costs"] != 1 for row in stability), "Zero observed cost variation; constancy alone does not refute supplier or accounting explanations.")
    check("groups_observed_all_six_months", sum(row["months_observed"] == 6 for row in stability), "All 135 schedules are observed in January through June; transaction lines are not independent supplier-price observations.")
    check("branch_product_reconciliations", "passed", "Units, revenue, costs, GP and product lines reconcile exactly between the two shared baseline tables.")
    check("garden_control_totals", "passed", "11,163 distinct transactions; revenue $99,748.55; GP $46,794.49.")
    check("ratio_precision", 28, "Margins are fractions and GP/transaction are Decimal ratios without display rounding, using 28 significant digits.")
    _require(hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "Source changed during analysis.")
    out.mkdir(parents=True, exist_ok=True)
    _write_csv(out / "branch_baseline.csv", branch_table, BRANCH_FIELDS)
    _write_csv(out / "branch_product_baseline.csv", product_table, PRODUCT_FIELDS)
    _write_csv(out / "price_cost_stability.csv", stability, STABILITY_FIELDS)
    _write_csv(out / "baseline_quality_checks.csv", quality, ("check", "observed", "interpretation"))
    return dict(
        filename=source.name, sha256=source_hash,
        date_start=min(row["Date"] for row in rows), date_end=max(row["Date"] for row in rows),
        rows=len(rows), transactions=len(transactions),
        branches=sorted(branch_groups), products=len({row["Product"] for row in rows}),
        branch_product_groups=len(product_groups),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Unchanged source transaction CSV")
    parser.add_argument("--out", type=Path, required=True, help="Directory for generated CSV tables")
    args = parser.parse_args()
    print(json.dumps(generate(args.source, args.out), indent=2))


if __name__ == "__main__":
    main()
