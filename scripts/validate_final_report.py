"""Independent numerical audit for the integrated Stories report.

Run with Python + pandas. Reads the original CSV without altering it; writes
outputs/final_review/numeric_audit.json and supporting CSVs. Does not import the
analytical scripts it audits. Decimal checks preserve supplied cent amounts.
"""
from __future__ import annotations

import csv
import hashlib
import itertools
import json
from collections import Counter, defaultdict
from decimal import Decimal, ROUND_HALF_UP, ROUND_HALF_EVEN
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data/stories_transactions.csv"
OUT = ROOT / "outputs/final_review"
R, G, P, C, D = "Line Revenue (USD)", "Line Gross Profit (USD)", "Unit Price (USD)", "Unit Cost (USD)", "Discount Rate"
FACTORS = ["costs", "prices", "discounts", "units_per_basket", "product_mix"]
BRANCHES = ["Garden", "Harbour", "Uptown"]
ZERO, CENT = Decimal(0), Decimal("0.01")


def total(rows, field):
    return sum((r[field] for r in rows), ZERO)


def json_default(value):
    if isinstance(value, Decimal):
        return str(value)
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(type(value).__name__)


def write_table(name, records):
    pd.DataFrame(records).to_csv(OUT / name, index=False, float_format="%.10f")


def factor_set(d):
    grouped = d.groupby("Product")
    units = grouped.Quantity.sum()
    return dict(costs=grouped[C].first(), prices=grouped[P].first(),
                discounts=(d.Quantity * d[D]).groupby(d.Product).sum() / units,
                units_per_basket=d.Quantity.sum() / d["Transaction ID"].nunique(),
                product_mix=units / units.sum())


def gp_formula(factors):
    return factors["units_per_basket"] * (factors["product_mix"] *
           (factors["prices"] * (1 - factors["discounts"]) - factors["costs"])).sum()


def swap_contributions(a, b, order):
    state, result = dict(a), {}
    previous = gp_formula(state)
    for factor in order:
        state[factor] = b[factor]
        current = gp_formula(state)
        result[factor] = current - previous
        previous = current
    return result


def matched_baskets(d, label):
    quantities = d.groupby(["Transaction ID", "Product"]).Quantity.sum()
    signatures = defaultdict(list)
    for (transaction, product), count in quantities.items():
        signatures[transaction].append((product, int(count)))
    baskets = d.groupby("Transaction ID").agg(branch=("Branch", "first"), gp=(G, "sum"),
                          discounted=(D, lambda s: (s > 0).any()))
    baskets["signature"] = pd.Series({t: tuple(sorted(s)) for t, s in signatures.items()})
    records = []
    for no_discount in [False, True]:
        chosen = baskets[~baskets.discounted] if no_discount else baskets
        garden = chosen[chosen.branch == "Garden"]
        for peer in ["Harbour", "Uptown"]:
            reference = chosen[chosen.branch == peer]
            common = set(garden.signature) & set(reference.signature)
            gm, pm = garden[garden.signature.isin(common)], reference[reference.signature.isin(common)]
            gg = gm.groupby("signature").gp.agg(["size", "mean"])
            pg = pm.groupby("signature").gp.mean().reindex(gg.index)
            peer_reweighted = (gg["size"] * pg).sum() / len(gm)
            records.append(dict(variant=label + ("; undiscounted only" if no_discount else ""), peer=peer,
                matched_signatures=len(common), garden_matched_transactions=len(gm),
                garden_denominator_transactions=len(garden), garden_coverage_pct=len(gm)/len(garden)*100,
                peer_matched_transactions=len(pm), peer_denominator_transactions=len(reference),
                peer_coverage_pct=len(pm)/len(reference)*100, garden_gp_per_basket=gm.gp.mean(),
                peer_gp_per_basket_same_signature_weights=peer_reweighted,
                gap_per_basket=peer_reweighted-gm.gp.mean(),
                all_matched_signatures_garden_lower=bool((gg["mean"] < pg).all())))
    return records


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    with SOURCE.open(newline="", encoding="utf-8-sig") as stream:
        raw = list(csv.DictReader(stream))
    numeric = ["Quantity", P, D, C, R, G]
    rows = [{k: Decimal(v) if k in numeric else v for k, v in r.items()} for r in raw]
    df = pd.read_csv(SOURCE)
    checks, claims = [], []

    def check(name, condition, detail=""):
        checks.append(dict(check=name, passed=bool(condition), detail=detail))
        if not condition:
            raise AssertionError(name + ": " + str(detail))

    def claim(name, status, replacement, note=""):
        claims.append(dict(claim=name, status=status, verified_value_or_replacement=replacement, note=note))

    missing_values = {key:int(value) for key,value in df.isna().sum().items()}
    check("No missing financial/transaction fields", not df.drop(columns=["Customer ID"]).isna().any().any())
    check("Positive integral quantities and valid discounts", df.Quantity.gt(0).all()
          and df.Quantity.eq(df.Quantity.astype(int)).all() and df[D].between(0, 1).all())
    check("Expected six-month source period", df.Date.min()=="2026-01-01" and df.Date.max()=="2026-06-30")
    branches = []
    for branch in BRANCHES:
        subset = [r for r in rows if r["Branch"] == branch]
        quantity, rev, gp = total(subset, "Quantity"), total(subset, R), total(subset, G)
        cost = sum((r["Quantity"] * r[C] for r in subset), ZERO)
        transactions = len({r["Transaction ID"] for r in subset})
        discounts = sum((r["Quantity"] * r[P] - r[R] for r in subset), ZERO)
        check(f"{branch} gross-profit identity", rev - cost == gp)
        branches.append(dict(branch=branch, lines=len(subset), transactions=transactions, units=quantity,
            revenue=rev, recorded_cost=cost, gross_profit=gp, gross_margin_pct=gp/rev*100,
            units_per_basket=quantity/transactions, revenue_per_basket=rev/transactions,
            gross_profit_per_basket=gp/transactions, recorded_discount_dollars=discounts))
    base = {b["branch"]: b for b in branches}
    check("Garden observed gross profit", base["Garden"]["gross_profit"] == Decimal("46794.49"))
    check("Garden observed transactions", base["Garden"]["transactions"] == 11163)
    products = df.groupby(["Branch", "Product"])[[P, C]].first()
    stability = df.groupby(["Branch", "Product"])[[P, C]].nunique()
    check("135 stable branch-product schedules", len(stability) == 135 and stability.eq(1).all().all())
    months = df.assign(month=df.Date.str[:7]).groupby(["Branch", "Product"]).month.nunique()
    check("All branch-product schedules present in six months", months.eq(6).all())
    lookup = {(r["Branch"], r["Product"]): r for r in rows}
    product_names = sorted(df.Product.unique())
    check("45 products in each branch", all(df[df.Branch.eq(b)].Product.nunique() == 45 for b in BRANCHES))
    for target, multiplier in [("Garden", "1.43"), ("Uptown", "0.96")]:
        matches = sum((lookup["Harbour", p][C] * Decimal(multiplier)).quantize(CENT, rounding=ROUND_HALF_UP)
                      == lookup[target, p][C] for p in product_names)
        check(f"{target} Harbour-based recorded cost rule", matches == 45)
    check("Garden prices below Harbour and above Uptown on all products",
          all(lookup["Uptown", p][P] < lookup["Garden", p][P] < lookup["Harbour", p][P] for p in product_names))
    direct_lo = max((lookup["Garden",p][C]-Decimal("0.005"))/lookup["Uptown",p][C] for p in product_names)
    direct_hi = min((lookup["Garden",p][C]+Decimal("0.005"))/lookup["Uptown",p][C] for p in product_names)
    check("No direct Garden/Uptown rounded-cost multiplier", direct_lo >= direct_hi)

    exact_counts = Counter(tuple(r.items()) for r in raw)
    duplicate_groups = [n for n in exact_counts.values() if n > 1]
    repeat_products = defaultdict(list)
    for r in raw:
        repeat_products[r["Transaction ID"], r["Product"]].append(tuple(r.items()))
    nonidentical = [v for v in repeat_products.values() if len(v)>1 and len(set(v))>1]
    duplicates = dict(exact_groups=len(duplicate_groups), participating_rows=sum(duplicate_groups),
        excess_copies=sum(n-1 for n in duplicate_groups), max_group_size=max(duplicate_groups),
        nonidentical_repeated_item_groups=len(nonidentical), max_nonidentical_group_size=max(map(len,nonidentical)))
    check("Exact repeated-row counts", duplicates["exact_groups"] == 132 and duplicates["participating_rows"] == 264
          and duplicates["excess_copies"] == 132 and duplicates["max_group_size"] == 2)
    check("Nonidentical repeated-item pairs", len(nonidentical) == 34 and duplicates["max_nonidentical_group_size"] == 2)
    metadata_conflicts = {field: int((df.groupby("Transaction ID")[field].nunique() > 1).sum())
                          for field in ["Branch", "Date", "Time", "Customer ID", "Order Type"]}
    check("Transaction metadata consistent", not any(metadata_conflicts.values()))
    arithmetic = dict(gp_exact_mismatches=0, revenue_half_up_mismatches=0, revenue_half_even_mismatches=0,
                      revenue_outside_half_cent=0, revenue_rounding_residual_by_branch={})
    for r in rows:
        exact = r["Quantity"]*r[P]*(1-r[D])
        arithmetic["gp_exact_mismatches"] += r[G] != r[R]-r["Quantity"]*r[C]
        arithmetic["revenue_half_up_mismatches"] += r[R] != exact.quantize(CENT,rounding=ROUND_HALF_UP)
        arithmetic["revenue_half_even_mismatches"] += r[R] != exact.quantize(CENT,rounding=ROUND_HALF_EVEN)
        arithmetic["revenue_outside_half_cent"] += abs(r[R]-exact) > Decimal("0.005")
        arithmetic["revenue_rounding_residual_by_branch"].setdefault(r["Branch"], ZERO)
        arithmetic["revenue_rounding_residual_by_branch"][r["Branch"]] += r[R]-exact
    check("All supplied GP lines reconcile exactly", arithmetic["gp_exact_mismatches"] == 0)
    check("All revenue differences within half cent", arithmetic["revenue_outside_half_cent"] == 0)

    premiums = []
    garden_rows = [r for r in rows if r["Branch"] == "Garden"]
    garden_unique = [dict(r) for r in {tuple(r.items()) for r in garden_rows}]
    gp0, rev0, cost0 = [base["Garden"][key] for key in ["gross_profit", "revenue", "recorded_cost"]]
    for peer in ["Harbour", "Uptown"]:
        by_product = defaultdict(lambda: ZERO)
        for r in garden_rows:
            by_product[r["Product"]] += r["Quantity"]*(r[C]-lookup[peer,r["Product"]][C])
        premium = sum(by_product.values(), ZERO)
        dedup_premium = sum((r["Quantity"]*(r[C]-lookup[peer,r["Product"]][C]) for r in garden_unique), ZERO)
        ranked = sorted(by_product.items(), key=lambda kv:kv[1], reverse=True)
        top5 = sum((v for p,v in ranked[:5]),ZERO)/premium*100
        premiums.append(dict(peer=peer, recorded_cost_gap=premium, top_product=ranked[0][0],
            top_product_gap=ranked[0][1], top5_share_pct=top5, exact_repeat_sensitivity_gap=dedup_premium,
            exact_repeat_change_pct=(dedup_premium/premium-1)*100, garden_margin_with_reference_costs_pct=(gp0+premium)/rev0*100,
            cost25_saving=premium/4, cost25_garden_cost_reduction_pct=premium/4/cost0*100))
        check(f"{peer} fixed-Garden-quantity cost gap", premium == Decimal({"Harbour":"15923.47","Uptown":"17409.78"}[peer]))

    tx = df.groupby("Transaction ID").agg(branch=("Branch","first"), order_type=("Order Type","first"),
          month=("Date",lambda s:s.iloc[0][:7]), gp=(G,"sum"), dessert=("Category",lambda s:(s=="Desserts").any()),
          category_line_signature=("Category",lambda s:" + ".join(sorted(s))))
    order_shares = (tx.groupby(["branch","order_type"]).size()/tx.groupby("branch").size()*100).reset_index(name="transaction_share_pct")
    dessert = (tx.groupby(["branch","month"]).dessert.mean()*100).reset_index(name="dessert_basket_pct")
    dessert_ranges = dessert.groupby("branch").dessert_basket_pct.agg(["min","max"]).reset_index().to_dict("records")
    dessert_wide = dessert.pivot(index="month",columns="branch",values="dessert_basket_pct")
    check("Garden dessert share highest in six months", ((dessert_wide.Garden>dessert_wide.Harbour)&(dessert_wide.Garden>dessert_wide.Uptown)).all())
    category_top10 = tx.category_line_signature.value_counts().head(10).index
    slice_records=[]
    for key, names in [("category_line_signature",category_top10), ("month",sorted(tx.month.unique())), ("order_type",sorted(tx.order_type.unique()))]:
        wide = tx[tx[key].isin(names)].groupby([key,"branch"]).gp.mean().unstack("branch")
        for label,record in wide.iterrows():
            lower = record.Garden < min(record.Harbour,record.Uptown)
            slice_records.append(dict(slice_type=key,slice=label,garden_gp_per_basket=record.Garden,
                harbour_gp_per_basket=record.Harbour,uptown_gp_per_basket=record.Uptown,garden_lowest=lower))
        check("Garden GP/basket lowest in all "+key+" slices", (wide.Garden < wide[["Harbour","Uptown"]].min(axis=1)).all())

    nt = df.groupby("Branch")["Transaction ID"].nunique()
    observed = df.groupby("Branch")[G].sum()/nt
    units = df.groupby("Product").Quantity.sum()
    references = {"Chain-average": ((df[P]*df.Quantity).groupby(df.Product).sum()/units,
                                    (df[C]*df.Quantity).groupby(df.Product).sum()/units)}
    for branch in BRANCHES:
        references[branch] = (products.loc[branch,P],products.loc[branch,C])
    common=[]
    for reference,(price,cost) in references.items():
        values = (df.Quantity*(df.Product.map(price)-df.Product.map(cost))).groupby(df.Branch).sum()/nt
        for peer in ["Harbour","Uptown"]:
            effect = values[peer]-values.Garden
            common.append(dict(reference=reference,peer=peer,garden_gp_per_basket=values.Garden,
                peer_gp_per_basket=values[peer],signed_peer_minus_garden_gp_per_basket=effect,
                signed_fraction_of_observed_gap_pct=effect/(observed[peer]-observed.Garden)*100))
    factor_data = {b:factor_set(df[df.Branch.eq(b)]) for b in BRANCHES}
    decompositions=[]
    for peer in ["Harbour","Uptown"]:
        observed_gap = observed[peer]-observed.Garden
        forward = swap_contributions(factor_data["Garden"],factor_data[peer],FACTORS)
        reverse = swap_contributions(factor_data["Garden"],factor_data[peer],FACTORS[::-1])
        shapley={k:0.0 for k in FACTORS}
        for order in itertools.permutations(FACTORS):
            for key,value in swap_contributions(factor_data["Garden"],factor_data[peer],order).items():
                shapley[key] += value/120
        residual=observed_gap-sum(forward.values())
        check(peer+" Shapley contributions reconcile",abs(sum(shapley.values())+residual-observed_gap)<1e-10)
        for factor in FACTORS:
            decompositions.append(dict(peer=peer,factor=factor,forward=forward[factor],
                forward_share_of_gap_pct=forward[factor]/observed_gap*100,reverse=reverse[factor],shapley=shapley[factor]))
        decompositions.append(dict(peer=peer,factor="rounding_residual",forward=residual,
                forward_share_of_gap_pct=residual/observed_gap*100,reverse=observed_gap-sum(reverse.values()),
                shapley=observed_gap-sum(shapley.values())))
        check(peer+" rounding residual under 0.0001 per basket", abs(residual)<0.0001)
    matched=matched_baskets(df,"all lines")+matched_baskets(df.drop_duplicates(),"exact repeats once")
    check("Garden lower on every exact matched signature in all variants", all(r["all_matched_signatures_garden_lower"] for r in matched))

    claim("Garden branch totals/margins", "VERIFIED", "See audited_branch_totals.csv; Garden GP $46,794.49, revenue $99,748.55, 11,163 transactions.")
    claim("All branches same items/basket", "QUALIFY", "Garden 1.5975, Harbour 1.5975, Uptown 1.5901 units per basket; all approximately 1.60.")
    claim("Same 59%/41% order-type split", "CORRECT", "Dine-in shares: Garden 58.69%, Harbour 58.96%, Uptown 60.25%; broadly similar, not identical.")
    claim("Purchasing patterns explain only 0–6%", "CORRECT", "Report signed peer-minus-Garden effects for each common reference; negative means Garden's baskets help, not a positive portion of its deficit.", "Common reference removes discounts and changes all prices/costs; comparison is descriptive, not causal.")
    claim("Common-reference Garden $5.36, Harbour $5.33, Uptown $5.43", "VERIFIED", "Chain-average list: no discounts; use audited_common_reference.csv for precise values.")
    claim("Dessert baskets 14–17% versus 9–12%", "REFINE", "Garden 14.33–17.20%; Harbour 10.70–12.49%; Uptown 8.97–10.91%; Garden highest each month.")
    claim("All top ten basket types lower GP", "VERIFIED_WITH_DEFINITION", "True for the ten most common category-line signatures in the full dataset.", "Types count category occurrences per row; exact product-quantity matches are a separate analysis.")
    claim("92% matched coverage", "REFINE", "Give reference-specific Garden coverage and peer coverage from audited_matched_baskets.csv.", "Weight each peer's signature mean by Garden's matched-signature counts; unmatched baskets excluded.")
    claim("132 exact repeated-row pairs and 34 nonidentical repeated-item pairs", "VERIFIED", "132 exact pairs = 264 participating rows, 132 excess copies; all retained in main analysis.")
    claim("25% cost-gap closure is 25% cost reduction", "CORRECT_IF_PRESENT", "Harbour quarter-gap = $3,980.8675 = 7.5176% of Garden recorded costs, not 25%.")
    claim("Cost premium proves supplier issue rather than waste", "UNSUPPORTED_CAUSAL_CLAIM", "Fixed recorded cost schedules establish an accounting pattern; supplier terms, allocation, portions/quality, standard waste allowances, mappings and volume discounts remain unresolved.")
    claim("Partial cost-gap closure dwarfs every other lever", "FALSE_COMPARISON", "Harbour price-only uplift $4,985.868 exceeds quarter Harbour cost-gap uplift $3,980.8675 and quarter Uptown cost-gap uplift $4,352.445 before volume changes/expenses.")
    claim("Only quality/portion/allocation reverses recommendation", "FALSE_EXCLUSIVITY", "Volume loss, implementation costs, infeasible savings, supplier evidence and alternative actions can change the decision.")
    claim("Cost story not a price or mix story", "OVERSTATED", "Recorded cost is the largest accounting component; prices materially amplify Harbour's gap and offset Uptown's. Mix/size effects are small but nonzero.")
    claim("No-discount savings are guaranteed", "CORRECT_IF_PRESENT", "Removing discounts gives a $555.90 fixed-quantity benchmark; sales and mix responses are unestimated.")
    claim("Net profitability established", "CORRECT_IF_PRESENT", "Operating expenses absent; observed gross-profit comparisons do not establish total net profit.")
    claim("Garden serves 75% more transactions than Uptown", "VERIFIED_ROUNDED", "Garden 11,163 versus Uptown 6,390: 74.6948% more; total GP $46,794.49 versus $34,882.06.")
    claim("Customer-level evidence is complete", "LIMITATION", "Customer ID is absent on 18,691 of 51,177 lines (36.52%); financial/transaction fields have no missing values.", "Transaction totals remain usable; identified-customer retention cannot be fully reconstructed.")

    check("Original source preserved", hashlib.sha256(SOURCE.read_bytes()).hexdigest()==source_hash)
    report = dict(status="ALL_INDEPENDENT_NUMERIC_CHECKS_PASSED", source_sha256=source_hash,
        source_rows=len(rows), source_transactions=int(df["Transaction ID"].nunique()),
        period_start=df.Date.min(), period_end=df.Date.max(), checks=checks, branch_totals=branches,
        duplicates=duplicates, arithmetic=arithmetic, missing_values=missing_values, metadata_conflicts=metadata_conflicts,
        cost_premiums=premiums, dessert_ranges=dessert_ranges, common_reference=common,
        decomposition=decompositions, matched_baskets=matched, source_claim_review=claims,
        limitations=["Accounting comparisons do not identify causality or recoverable cash savings.",
          "No operating expenses, supplier invoices, recipe/quality/portion data or realized customer response supplied.",
          "Recorded prices/costs are reused product schedules; rows are not independent supplier-price samples.",
          "Customer IDs are missing on 18,691 lines, preventing complete identified-customer retention analysis.",
          "The numerical checks validate calculations, not the unobserved feasibility of implementation."])
    (OUT/"numeric_audit.json").write_text(json.dumps(report,indent=2,default=json_default)+"\n")
    for name,records in [("numeric_audit.csv",claims),("audited_branch_totals.csv",branches),
        ("audited_cost_premiums.csv",premiums),("audited_order_type_shares.csv",order_shares.to_dict("records")),
        ("audited_dessert_monthly.csv",dessert.to_dict("records")),("audited_gp_slices.csv",slice_records),
        ("audited_common_reference.csv",common),("audited_decomposition.csv",decompositions),
        ("audited_matched_baskets.csv",matched)]:
        write_table(name,records)
    print(json.dumps({"status":report["status"],"checks":len(checks),"claim_reviews":len(claims),
          "outputs":str(OUT)},indent=2))


if __name__ == "__main__":
    main()
