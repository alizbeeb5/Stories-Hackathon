#!/usr/bin/env python3
"""Reproduce the Garden recorded-cost study with Python 3.10+ (stdlib only).

Run: python3 analyze_cost_gap.py stories_transactions.csv --out outputs/garden_cost_study
The input is read-only. All-row results are primary. Duplicate scenarios are
explicit sensitivities, not corrections. CSV row numbers count the header as 1.
Revenue/GP use the supplied line amounts; diagnostic rounding never overwrites them.
The output CSVs and results.json contain every value used in the comparison workbook.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, ROUND_HALF_UP
from fractions import Fraction
from pathlib import Path

D = Decimal
CENT = D('0.01')
HALF_CENT = Fraction(1, 200)
NUMERIC = ['Quantity', 'Unit Price (USD)', 'Discount Rate', 'Unit Cost (USD)',
           'Line Revenue (USD)', 'Line Gross Profit (USD)']
METADATA = ['Date', 'Time', 'Branch', 'Customer ID', 'Order Type']
PEERS = ['Harbour', 'Uptown']


def total(rows, field):
    return sum((r[field] for r in rows), D(0))


def round_cent(value, mode=ROUND_HALF_UP):
    return value.quantize(CENT, rounding=mode)


def encode(value):
    if isinstance(value, D):
        return str(value)
    if isinstance(value, Fraction):
        return {'fraction': str(value), 'decimal': float(value)}
    raise TypeError(type(value).__name__)


def save_csv(path, rows, fields=None):
    if fields is None:
        fields = list(rows[0]) if rows else []
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def product_table(rows):
    groups = defaultdict(list)
    for r in rows:
        groups[r['Branch'], r['Product']].append(r)
    result = []
    for (branch, product), group in sorted(groups.items()):
        q = total(group, 'Quantity')
        list_sales = sum((r['Quantity'] * r['Unit Price (USD)'] for r in group), D(0))
        cogs = sum((r['Quantity'] * r['Unit Cost (USD)'] for r in group), D(0))
        rev = total(group, 'Line Revenue (USD)')
        gp = total(group, 'Line Gross Profit (USD)')
        prices = sorted({r['Unit Price (USD)'] for r in group})
        costs = sorted({r['Unit Cost (USD)'] for r in group})
        categories = sorted({r['Category'] for r in group})
        result.append(dict(branch=branch, product=product, category='; '.join(categories),
            lines=len(group), purchases=len({r['Transaction ID'] for r in group}),
            quantity=q, unit_price=prices[0] if len(prices) == 1 else None,
            unit_price_min=prices[0], unit_price_max=prices[-1],
            unit_cost=costs[0] if len(costs) == 1 else None,
            unit_cost_min=costs[0], unit_cost_max=costs[-1],
            discount_rates='; '.join(str(x) for x in sorted({r['Discount Rate'] for r in group})),
            discount_rate_min=min(r['Discount Rate'] for r in group),
            discount_rate_max=max(r['Discount Rate'] for r in group),
            discounted_lines=sum(r['Discount Rate'] != 0 for r in group),
            list_sales=list_sales, nominal_discount=sum((r['Quantity'] * r['Unit Price (USD)'] * r['Discount Rate'] for r in group), D(0)),
            realized_discount=list_sales-rev, effective_discount=(list_sales-rev)/list_sales,
            revenue=rev, cogs=cogs, gross_profit=gp, margin=gp/rev))
    return result


def branch_table(rows, scenario):
    result = []
    for branch in sorted({r['Branch'] for r in rows}):
        group = [r for r in rows if r['Branch'] == branch]
        revenue = total(group, 'Line Revenue (USD)')
        gp = total(group, 'Line Gross Profit (USD)')
        result.append(dict(scenario=scenario, branch=branch, lines=len(group),
            purchases=len({r['Transaction ID'] for r in group}), quantity=total(group, 'Quantity'),
            revenue=revenue, cogs=revenue-gp, gross_profit=gp, margin=gp/revenue))
    return result


def multiplier_test(products, peer, target='Garden', both_rounded=False):
    lookup = {(p['branch'], p['product']): p for p in products}
    bounds = []
    for product in sorted({p['product'] for p in products if p['branch'] == target}):
        g = lookup[target, product]['unit_cost']
        h = lookup[peer, product]['unit_cost']
        if g is None or h is None or h <= D('0.005'):
            raise ValueError('Multiplier test requires one positive cost per branch/product.')
        g, h = Fraction(g), Fraction(h)
        lo = (g-HALF_CENT)/(h+HALF_CENT if both_rounded else h)
        hi = (g+HALF_CENT)/(h-HALF_CENT if both_rounded else h)
        bounds.append((product, lo, hi))
    low = max(x[1] for x in bounds)
    high = min(x[2] for x in bounds)
    feasible = low < high
    candidate = (low+high)/2 if feasible else None
    return dict(target=target, peer=peer, model='both observations rounded' if both_rounded else 'multiply recorded peer cost then round',
        product_count=len(bounds), lower=low, upper=high, feasible=feasible,
        lower_inclusive=not both_rounded, upper_inclusive=False,
        lower_products=', '.join(x[0] for x in bounds if x[1] == low),
        upper_products=', '.join(x[0] for x in bounds if x[2] == high), candidate=candidate)


def gap_table(products, peer, scenario):
    lookup = {(p['branch'], p['product']): p for p in products}
    result = []
    for product in sorted({p['product'] for p in products if p['branch'] == 'Garden'}):
        garden, other = lookup['Garden', product], lookup[peer, product]
        diff = garden['unit_cost']-other['unit_cost']
        premium = garden['quantity']*diff
        volume_mix = (garden['quantity']-other['quantity'])*other['unit_cost']
        raw_gap = garden['cogs']-other['cogs']
        assert premium + volume_mix == raw_gap
        result.append(dict(scenario=scenario, peer=peer, product=product,
            garden_quantity=garden['quantity'], peer_quantity=other['quantity'],
            garden_unit_cost=garden['unit_cost'], peer_unit_cost=other['unit_cost'],
            unit_cost_gap=diff, standardized_cost_gap=premium,
            volume_mix_component=volume_mix, raw_cogs_gap=raw_gap))
    result.sort(key=lambda x: (-x['standardized_cost_gap'], x['product']))
    denominator = sum((r['standardized_cost_gap'] for r in result), D(0))
    for rank, r in enumerate(result, 1):
        r['rank'] = rank
        r['share_of_standardized_gap'] = r['standardized_cost_gap']/denominator
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', default='stories_transactions.csv', type=Path)
    parser.add_argument('--out', default='outputs/garden_cost_study', type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    out = args.out.resolve()
    if source == out or source.is_relative_to(out):
        raise ValueError('Output folder must not contain the original source.')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    with source.open(newline='', encoding='utf-8-sig') as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames
        original = list(reader)
    if not original:
        raise ValueError('No source rows.')
    rows = []
    duplicates, anomalies = [], []
    first_seen = {}
    for rownum, raw in enumerate(original, 2):
        key = tuple(raw[k] for k in fields)
        r = dict(raw, source_row=rownum)
        for field in NUMERIC:
            r[field] = D(raw[field])
        datetime.strptime(r['Date'], '%Y-%m-%d')
        datetime.strptime(r['Time'], '%H:%M:%S')
        rows.append(r)
        if key in first_seen:
            duplicates.append(dict(source_row=rownum, first_source_row=first_seen[key], **raw))
        else:
            first_seen[key] = rownum
        exact = r['Quantity']*r['Unit Price (USD)']*(1-r['Discount Rate'])
        expected_gp = r['Line Revenue (USD)']-r['Quantity']*r['Unit Cost (USD)']
        tests = {
            'revenue differs from decimal half-up': r['Line Revenue (USD)']-round_cent(exact),
            'revenue differs from decimal half-even': r['Line Revenue (USD)']-round_cent(exact, ROUND_HALF_EVEN),
            'gross profit arithmetic mismatch': r['Line Gross Profit (USD)']-expected_gp,
        }
        for issue, delta in tests.items():
            if delta:
                anomalies.append(dict(source_row=rownum, transaction_id=r['Transaction ID'],
                    branch=r['Branch'], product=r['Product'], issue=issue, delta=delta,
                    exact_unrounded_revenue=exact, reported_revenue=r['Line Revenue (USD)'],
                    reported_gp=r['Line Gross Profit (USD)']))
        if r['Quantity'] <= 0 or r['Quantity'] != int(r['Quantity']) or not 0 <= r['Discount Rate'] <= 1 or r['Unit Cost (USD)'] < 0 or r['Unit Price (USD)'] < 0:
            raise ValueError(f'Unexpected quantity/rate/cost at source row {rownum}')

    txns = defaultdict(list)
    txn_products = defaultdict(list)
    for r in rows:
        txns[r['Transaction ID']].append(r)
        txn_products[r['Transaction ID'], r['Product']].append(r)
    metadata_conflicts = []
    for txn, group in txns.items():
        for field in METADATA:
            values = sorted({r[field] for r in group})
            if len(values) > 1:
                metadata_conflicts.append(dict(transaction_id=txn, field=field, values=values))
    repeated_products = []
    for (txn, product), group in txn_products.items():
        if len(group) > 1:
            repeated_products.append(dict(transaction_id=txn, product=product, lines=len(group),
                distinct_full_rows=len({tuple(str(r[k]) for k in fields) for r in group}),
                source_rows=', '.join(str(r['source_row']) for r in group),
                quantities=', '.join(str(r['Quantity']) for r in group),
                discount_rates=', '.join(str(r['Discount Rate']) for r in group)))

    duplicate_rownums = {r['source_row'] for r in duplicates}
    scenarios = {'All rows (primary)': rows,
                 'Exact rows once (sensitivity)': [r for r in rows if r['source_row'] not in duplicate_rownums]}
    # Stress test only: transaction/product is NOT a reliable duplicate key.
    first_product = {}
    last_product = {}
    for r in rows:
        key = (r['Transaction ID'], r['Product'])
        first_product.setdefault(key, r)
        last_product[key] = r
    scenarios['Txn/product first only (stress test)'] = list(first_product.values())
    scenarios['Txn/product last only (stress test)'] = list(last_product.values())

    comparison, gaps, rules, scenario_results = [], [], [], []
    primary_products = product_table(rows)
    for scenario, selected in scenarios.items():
        bp = product_table(selected)
        bt = branch_table(selected, scenario)
        comparison.extend(bt)
        s = dict(scenario=scenario, rows=len(selected), purchases=len({r['Transaction ID'] for r in selected}))
        for peer in PEERS:
            gt = gap_table(bp, peer, scenario)
            gaps.extend(gt)
            s[peer+'_standardized_gap'] = sum((r['standardized_cost_gap'] for r in gt), D(0))
            s[peer+'_top_product'] = gt[0]['product']
            direct = multiplier_test(bp, peer)
            direct['scenario'] = scenario
            rules.append(direct)
        scenario_results.append(s)
    rules.append(dict(multiplier_test(primary_products, 'Uptown', both_rounded=True), scenario='All rows (primary)'))
    rules.append(dict(multiplier_test(primary_products, 'Harbour', target='Uptown'), scenario='All rows (primary)'))
    shared_factors = []
    lookup = {(p['branch'], p['product']): p for p in primary_products}
    for target, factor in [('Garden', D('1.43')), ('Uptown', D('0.96'))]:
        matches = [p for (b,p), r in lookup.items() if b == target and
                   round_cent(lookup['Harbour',p]['unit_cost']*factor) == r['unit_cost']]
        shared_factors.append(dict(target=target, base='Harbour', multiplier=factor,
            matched_products=len(matches), tested_products=sum(b == target for b,p in lookup)))
    price_factors = []
    for target, factor in [('Harbour', D('1.05')), ('Uptown', D('0.96'))]:
        matches = sum(round_cent(lookup['Garden',p]['unit_price']*factor) == r['unit_price']
                      for (b,p),r in lookup.items() if b == target)
        price_factors.append(dict(target=target, base='Garden', multiplier=factor,
            matched_products=matches, tested_products=sum(b == target for b,p in lookup)))

    for b in branch_table(rows, 'All rows (primary)'):
        subset = [p for p in primary_products if p['branch'] == b['branch']]
        for field in ['quantity','revenue','cogs','gross_profit']:
            assert b[field] == sum((p[field] for p in subset), D(0)), field
    assert sum(b['purchases'] for b in branch_table(rows, 'All rows (primary)')) == len(txns)
    assert not metadata_conflicts, 'Resolve transaction metadata conflicts before aggregating.'
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, 'Source changed.'
    issue_counts = Counter(r['issue'] for r in anomalies)
    issue_deltas = {issue:sum((r['delta'] for r in anomalies if r['issue']==issue),D(0)) for issue in issue_counts}
    results = dict(source=dict(filename=source.name, sha256=source_hash, rows=len(rows),
        purchases=len(txns), date_start=min(r['Date'] for r in rows), date_end=max(r['Date'] for r in rows),
        products=len({r['Product'] for r in rows}), columns=fields),
        definitions=dict(revenue='Sum reported Line Revenue (USD)', gross_profit='Sum reported Line Gross Profit (USD)',
            purchases='Distinct Transaction ID within branch, never row count', margin='Total gross profit / total revenue',
            cogs='Sum quantity * unit cost; verified equals revenue - gross profit',
            standardized_gap='Garden quantity * (Garden unit cost - peer unit cost), product by product',
            raw_gap='Garden COGS - peer COGS = standardized gap + (Garden quantity - peer quantity) * peer cost',
            rounding='Direct: [target-.005, target+.005) / recorded peer. Both-rounded: ((target-.005)/(peer+.005), (target+.005)/(peer-.005)). Positive values; half-up convention. Shared-factor tests avoid ties.',
            duplicates='Primary retains all rows; exact rows once is unproven sensitivity; txn/product first and last are deliberately aggressive stress tests.'),
        comparison=comparison, branch_product=primary_products, product_gaps=gaps,
        duplicate_ledger=duplicates, repeated_transaction_products=repeated_products,
        cost_rules=rules, shared_factors=shared_factors, price_factors=price_factors, scenario_results=scenario_results,
        audit=dict(exact_duplicate_groups=len({r['first_source_row'] for r in duplicates}),
            exact_duplicate_excess_rows=len(duplicates), exact_duplicate_excess_revenue=sum((D(r['Line Revenue (USD)']) for r in duplicates),D(0)),
            exact_duplicate_excess_gp=sum((D(r['Line Gross Profit (USD)']) for r in duplicates),D(0)),
            metadata_conflicts=metadata_conflicts, repeated_txn_product_groups=len(repeated_products),
            repeated_txn_product_nonidentical_groups=sum(r['distinct_full_rows']>1 for r in repeated_products),
            missing_by_column={field:sum(not r[field] for r in original) for field in fields},
            arithmetic_issue_counts=dict(issue_counts), arithmetic_issue_total_deltas=issue_deltas,
            revenue_outside_half_cent=sum(abs(r['Line Revenue (USD)']-r['Quantity']*r['Unit Price (USD)']*(1-r['Discount Rate'])) > D('0.005') for r in rows),
            max_absolute_revenue_rounding_difference=max(abs(r['Line Revenue (USD)']-r['Quantity']*r['Unit Price (USD)']*(1-r['Discount Rate'])) for r in rows),
            variable_price_groups=sum(p['unit_price'] is None for p in primary_products),
            variable_cost_groups=sum(p['unit_cost'] is None for p in primary_products),
            product_category_conflicts=sum(len({r['Category'] for r in rows if r['Product']==p})>1 for p in {r['Product'] for r in rows})))
    out.mkdir(parents=True, exist_ok=True)
    save_csv(out/'comparison.csv', comparison)
    save_csv(out/'branch_product.csv', primary_products)
    save_csv(out/'product_cost_gaps.csv', gaps)
    save_csv(out/'duplicate_ledger.csv', duplicates, ['source_row','first_source_row']+fields)
    save_csv(out/'arithmetic_diagnostics.csv', anomalies, ['source_row','transaction_id','branch','product','issue','delta','exact_unrounded_revenue','reported_revenue','reported_gp'])
    save_csv(out/'repeated_transaction_products.csv', repeated_products)
    (out/'results.json').write_text(json.dumps(results, default=encode, indent=2)+'\n')
    print(json.dumps({key:results[key] for key in ['source','comparison','shared_factors','scenario_results','audit']}, default=encode, indent=2))


if __name__ == '__main__':
    main()
