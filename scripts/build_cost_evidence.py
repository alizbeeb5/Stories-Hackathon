#!/usr/bin/env python3
"""Build the shared Person 1 evidence package using Python 3.10+ (stdlib only).

Run from any folder: python3 /path/to/person1_cost_evidence/scripts/build_cost_evidence.py
Optional: --source /path/to/stories_transactions.csv --out /path/to/results
The two shared baseline CSVs are authoritative for the main analysis and report.
The original cost audit is retained and run as an independent reconciliation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import shared_baseline

ROOT = Path(__file__).resolve().parent.parent
D = Decimal
CENT = D('0.01')
PRIMARY = 'All rows (primary)'
EXACT_ONCE = 'Exact rows once (sensitivity)'


def read_csv(path):
    with Path(path).open(newline='', encoding='utf-8-sig') as handle:
        return list(csv.DictReader(handle))


def write_csv(path, rows):
    if not rows:
        raise ValueError(f'No records for {path.name}')
    with path.open('w', newline='', encoding='utf-8') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def decimal(value):
    return D(str(value))


def dollars(value):
    return f'${rounded(decimal(value)):,.2f}'


def fraction_pct(value, places=2):
    value=(decimal(value)*100).quantize(D(1).scaleb(-places),rounding=ROUND_HALF_UP)
    return f'{value:.{places}f}%'


def rounded(value):
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def generate(source, out):
    source = source.resolve()
    out = out.resolve()
    if source.is_relative_to(out):
        raise ValueError('The output directory must not contain the source CSV.')
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    out.mkdir(parents=True, exist_ok=True)
    metadata = shared_baseline.generate(source, out)
    # Keep the pre-existing Decimal cost audit intact, including its duplicate ledger.
    subprocess.run([sys.executable, str(ROOT/'scripts'/'cost_audit.py'), str(source),
                    '--out', str(out/'audit')], check=True, capture_output=True, text=True)
    legacy = json.loads((out/'audit'/'results.json').read_text())

    # All main figures below are read from the shared baseline exports, not re-estimated.
    branches = {r['branch']:r for r in read_csv(out/'branch_baseline.csv')}
    products = read_csv(out/'branch_product_baseline.csv')
    lookup = {(r['branch'],r['product']):r for r in products}
    stability = read_csv(out/'price_cost_stability.csv')
    garden = branches['Garden']
    checks = []

    def check(name, actual, expected):
        if decimal(actual) != decimal(expected):
            raise AssertionError(f'{name}: {actual} != {expected}')
        checks.append(dict(check=name, observed=actual, expected=expected, result='MATCH'))

    check('Garden distinct transactions', garden['transactions'], 11163)
    check('Garden reported revenue USD', garden['revenue_usd'], '99748.55')
    check('Garden reported gross profit USD', garden['gross_profit_usd'], '46794.49')
    check('Unique branch-product rows',len(lookup),135)
    for row in legacy['comparison']:
        if row['scenario'] != PRIMARY:
            continue
        shared = branches[row['branch']]
        for shared_key, legacy_key in [('transactions','purchases'),('units','quantity'),
                ('revenue_usd','revenue'),('recorded_costs_usd','cogs'),('gross_profit_usd','gross_profit')]:
            check(f"Independent cost audit / {row['branch']} / {shared_key}", shared[shared_key], row[legacy_key])
    for r in stability:
        if int(r['distinct_prices']) != 1 or int(r['distinct_costs']) != 1:
            raise AssertionError(f"Unstable schedule: {r['branch']} / {r['product']}")
        if int(r['months_observed']) != 6:
            raise AssertionError('Six-month schedule coverage is incomplete.')

    rules, rule_details = [], []
    for target, factor in [('Garden',D('1.43')),('Uptown',D('0.96'))]:
        matched, exceptions, ties = 0, [], 0
        names = sorted(r['product'] for r in products if r['branch']==target)
        for name in names:
            target_cost = decimal(lookup[target,name]['unit_cost_usd'])
            base_cost = decimal(lookup['Harbour',name]['unit_cost_usd'])
            before_rounding = base_cost*factor
            predicted = rounded(before_rounding)
            match = predicted == target_cost
            tie = before_rounding % CENT == D('0.005')
            matched += match
            ties += tie
            if not match:
                exceptions.append(name)
            rule_details.append(dict(target_branch=target, reference_branch='Harbour',product=name,
                harbour_recorded_unit_cost_usd=base_cost,multiplier=factor,
                multiplied_cost_before_rounding_usd=before_rounding,
                predicted_recorded_unit_cost_usd=predicted,
                observed_recorded_unit_cost_usd=target_cost,
                residual_usd=target_cost-predicted,match=match,half_cent_tie=tie))
        target_stability = [s for s in stability if s['branch']==target]
        rules.append(dict(target_branch=target,reference_branch='Harbour',multiplier=factor,
            products_tested=len(names),matching_products=matched,exception_count=len(exceptions),
            exception_products='; '.join(exceptions) or 'None',half_cent_ties=ties,
            rounding='Decimal ROUND_HALF_UP to nearest USD 0.01',
            target_groups_with_price_changes=sum(int(s['distinct_prices'])>1 for s in target_stability),
            target_groups_with_cost_changes=sum(int(s['distinct_costs'])>1 for s in target_stability),
            months_observed_min=min(int(s['months_observed']) for s in target_stability),
            observation_unit='45 distinct product comparisons; transaction rows reuse fixed schedules'))
        check(f'{target} rule: matching products',matched,45)
        check(f'{target} rule: exceptions',len(exceptions),0)
        check(f'{target} rule: half-cent ties',ties,0)
    write_csv(out/'cost_rule_verification.csv',rules)
    write_csv(out/'cost_rule_product_checks.csv',rule_details)
    direct_u=next(r for r in legacy['cost_rules'] if r['scenario']==PRIMARY and r['target']=='Garden'
                  and r['peer']=='Uptown' and r['model']=='multiply recorded peer cost then round')
    check('Direct Garden / recorded Uptown common multiplier exists',int(direct_u['feasible']),0)

    # Benchmark costs and premiums use Garden quantities in the shared product table.
    contributions, premiums = [], []
    for peer in ['Harbour','Uptown']:
        product_rows = []
        for name in sorted(r['product'] for r in products if r['branch']=='Garden'):
            g,p = lookup['Garden',name],lookup[peer,name]
            quantity = decimal(g['quantity'])
            gc,pc = decimal(g['unit_cost_usd']),decimal(p['unit_cost_usd'])
            product_rows.append(dict(reference_branch=peer,product=name,garden_quantity=quantity,
                garden_recorded_unit_cost_usd=gc,reference_recorded_unit_cost_usd=pc,
                unit_cost_difference_usd=gc-pc,recorded_cost_premium_usd=quantity*(gc-pc)))
        product_rows.sort(key=lambda r:(-r['recorded_cost_premium_usd'],r['product']))
        premium = sum((r['recorded_cost_premium_usd'] for r in product_rows),D(0))
        check(f'Garden recorded cost premium vs {peer}',premium,{'Harbour':'15923.47','Uptown':'17409.78'}[peer])
        benchmark_costs = decimal(garden['recorded_costs_usd'])-premium
        benchmark_gp = decimal(garden['gross_profit_usd'])+premium
        for rank,r in enumerate(product_rows,1):
            r['rank'] = rank
            r['share_of_recorded_cost_premium'] = r['recorded_cost_premium_usd']/premium
        contributions.extend(product_rows)
        premiums.append(dict(reference_branch=peer,garden_units=int(garden['units']),
            garden_recorded_costs_usd=garden['recorded_costs_usd'],
            garden_basket_at_reference_costs_usd=benchmark_costs,recorded_cost_premium_usd=premium,
            benchmark_gross_profit_usd=benchmark_gp,
            benchmark_gross_margin=benchmark_gp/decimal(garden['revenue_usd']),
            evidence_label='Recorded cost benchmark at Garden quantities; not verified recoverable savings',
            assumptions='Fixed Garden quantities, reported revenue and discounts; replace only recorded unit costs; no implementation costs or behavior changes',
            scenario_rounding='Recorded reference unit costs already in cents; exact Decimal quantity multiplication; ROUND_HALF_UP only for monetary display'))
    write_csv(out/'recorded_cost_benchmarks.csv',premiums)
    write_csv(out/'product_cost_premium_contributions.csv',contributions)

    # Count participating rows separately from excess copies. Do not remove either in primary tables.
    raw = read_csv(source)
    fields = list(raw[0])
    groups = defaultdict(list)
    for index,r in enumerate(raw,2):
        groups[tuple(r[f] for f in fields)].append((index,r))
    exact_groups = [v for v in groups.values() if len(v)>1]
    duplicate_counts=[]
    for branch in sorted(branches)+['ALL']:
        selected = [g for g in exact_groups if branch=='ALL' or g[0][1]['Branch']==branch]
        duplicate_counts.append(dict(branch=branch,identical_groups=len(selected),
            rows_belonging_to_identical_groups=sum(len(g) for g in selected),
            excess_identical_rows=sum(len(g)-1 for g in selected),
            representatives_retained_in_sensitivity=len(selected)))
    check('Identical groups',duplicate_counts[-1]['identical_groups'],132)
    check('All rows belonging to identical groups',duplicate_counts[-1]['rows_belonging_to_identical_groups'],264)
    check('Excess identical copies',duplicate_counts[-1]['excess_identical_rows'],132)
    write_csv(out/'duplicate_counts.csv',duplicate_counts)
    duplicate_branch_results=[]
    for r in legacy['comparison']:
        if r['scenario'] not in [PRIMARY,EXACT_ONCE]:
            continue
        b = branches[r['branch']]
        duplicate_branch_results.append(dict(policy='Retain all rows (primary)' if r['scenario']==PRIMARY else 'Retain one copy per identical group (sensitivity)',
            branch=r['branch'],transactions=r['purchases'],units=r['quantity'],
            revenue_usd=r['revenue'],recorded_costs_usd=r['cogs'],gross_profit_usd=r['gross_profit'],
            gross_margin=decimal(r['gross_profit'])/decimal(r['revenue']),
            gross_profit_per_transaction_usd=decimal(r['gross_profit'])/r['purchases'],product_lines=r['lines'],
            revenue_change_from_primary_usd=decimal(r['revenue'])-decimal(b['revenue_usd']),
            gross_profit_change_from_primary_usd=decimal(r['gross_profit'])-decimal(b['gross_profit_usd'])))
        if r['scenario']==EXACT_ONCE:
            check(f"Distinct transactions unchanged after exact-repeat sensitivity / {r['branch']}",r['purchases'],b['transactions'])
    write_csv(out/'duplicate_headline_sensitivity.csv',duplicate_branch_results)
    duplicate_premiums=[]
    for s in legacy['scenario_results']:
        if s['scenario'] not in [PRIMARY,EXACT_ONCE]:
            continue
        for p in premiums:
            peer=p['reference_branch']
            premium=decimal(s[f'{peer}_standardized_gap'])
            baseline=decimal(p['recorded_cost_premium_usd'])
            duplicate_premiums.append(dict(policy='Retain all rows (primary)' if s['scenario']==PRIMARY else 'Retain one copy per identical group (sensitivity)',
                reference_branch=peer,recorded_cost_premium_usd=premium,
                change_from_primary_usd=premium-baseline,change_from_primary_fraction=(premium-baseline)/baseline,
                garden_harbour_rule_matching_products=rules[0]['matching_products'],uptown_harbour_rule_matching_products=rules[1]['matching_products']))
    # Verify every product retains the same cost under the sensitivity, before displaying invariant rule counts.
    for peer in ['Harbour','Uptown']:
        sens = [r for r in legacy['product_gaps'] if r['scenario']==EXACT_ONCE and r['peer']==peer]
        for r in sens:
            check(f"Exact-repeat sensitivity cost / Garden / {r['product']} vs {peer}",r['garden_unit_cost'],lookup['Garden',r['product']]['unit_cost_usd'])
            check(f"Exact-repeat sensitivity cost / {peer} / {r['product']}",r['peer_unit_cost'],lookup[peer,r['product']]['unit_cost_usd'])
    write_csv(out/'duplicate_cost_premium_sensitivity.csv',duplicate_premiums)

    ledger = read_csv(ROOT/'notes'/'explanations_ledger.csv')
    check('Alternative explanations documented',len(ledger),6)
    if any(r['status']!='Possible; unresolved' for r in ledger):
        raise AssertionError('An explanation was closed without additional evidence.')
    write_csv(out/'explanation_ledger.csv',ledger)

    # The report uses the shared branch/product baseline exports and verified benchmark outputs.
    h,u=branches['Harbour'],branches['Uptown']
    ph,pu=premiums
    sensitive_garden=next(r for r in duplicate_branch_results if r['branch']=='Garden' and 'sensitivity' in r['policy'])
    sensitive_premiums={r['reference_branch']:r for r in duplicate_premiums if 'sensitivity' in r['policy']}
    top5=sum((r['recorded_cost_premium_usd'] for r in contributions if r['reference_branch']=='Harbour' and r['rank']<=5),D(0))/ph['recorded_cost_premium_usd']
    report=f"""3 - What does Garden's recorded cost premium establish, and which explanations remain possible?

Across January-June 2026, Garden records {int(garden['transactions']):,} distinct transactions, {dollars(garden['revenue_usd'])} revenue and {dollars(garden['gross_profit_usd'])} gross profit ({fraction_pct(garden['gross_margin'])} margin; {dollars(garden['gross_profit_per_transaction_usd'])} GP per transaction). These figures and product-level comparisons use the two shared baseline tables.

All 45 products satisfy Garden cost = round(Harbour cost x 1.43, 2), and Uptown cost = round(Harbour cost x 0.96, 2), with zero exceptions. All 135 branch-product groups have fixed recorded prices and costs across all six months. Repeated transactions reuse these schedules; they are not thousands of independent supplier-price observations. A direct Garden/Uptown multiplier does not fit every rounded cent; both Harbour-based rules still hold.

The recorded cost premium, sum of Garden quantity x (Garden recorded unit cost - reference recorded unit cost), is {dollars(ph['recorded_cost_premium_usd'])} versus Harbour and {dollars(pu['recorded_cost_premium_usd'])} versus Uptown. These are fixed-basket benchmarks, not verified recoverable savings. The top five products explain {fraction_pct(top5)} of the Harbour benchmark. At Harbour costs, Garden's benchmark margin is {fraction_pct(ph['benchmark_gross_margin'])}, below Harbour's {fraction_pct(h['gross_margin'])}.

The 132 identical pairs contain 264 rows, including 132 excess copies. All rows remain in the primary baseline. Keeping one copy per pair gives Garden {dollars(sensitive_garden['revenue_usd'])} revenue and {dollars(sensitive_garden['gross_profit_usd'])} gross profit, with unchanged transactions. Benchmarks become {dollars(sensitive_premiums['Harbour']['recorded_cost_premium_usd'])}/{dollars(sensitive_premiums['Uptown']['recorded_cost_premium_usd'])}, about 0.23% lower; cost rules remain unchanged. The 34 nonidentical repeated-item groups are retained. Supplied financial amounts are preserved. Modeled rounding uses Decimal ROUND_HALF_UP; GP reconciles exactly and revenue tie differences remain within half a cent.

This establishes a consistent recorded accounting pattern without verifying supplier payments or its cause. Supplier terms, portions or ingredients, shared-cost allocation, standard waste allowances, persistent entry/mapping errors and purchasing-volume discounts remain possible. Constancy refutes none of them. The explanation ledger identifies evidence and conditional actions. Allocation or mapping corrections can change reported branch GP without reducing cash expenditure. Net profitability remains unknown without operating expenses.
"""
    (out/'report_section.txt').write_text(report,encoding='utf-8')
    write_csv(out/'claim_checks.csv',checks)
    if hashlib.sha256(source.read_bytes()).hexdigest()!=source_hash:
        raise AssertionError('The source was modified.')
    manifest=dict(source=metadata,primary_policy='All rows retained; supplied revenue and gross profit preserved',
        baseline_authority=['branch_baseline.csv','branch_product_baseline.csv'],
        rounding=dict(observed='Preserve supplied financial amounts; Decimal arithmetic for checks',
            cost_rules='Decimal ROUND_HALF_UP to USD 0.01; no half-cent ties in either tested factor',
            benchmarks='Quantity times cent-denominated recorded unit costs, summed exactly; no per-unit intermediate rounding',
            display='Monetary displays rounded to two decimal places, ROUND_HALF_UP',
            margin='Full-precision gross profit / revenue; percentages are displayed as ratio times 100'),
        cost_premium_interpretation='Recorded cost benchmark at Garden quantities, not verified recoverable savings',
        independent_supplier_observations='Not inferable. Repeated sales rows reuse fixed branch-product schedules.',
        check_count=len(checks),all_checks_match=True,
        output_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='manifest.json'},
        script_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((ROOT/'scripts').glob('*.py'))})
    (out/'manifest.json').write_text(json.dumps(manifest,indent=2,default=str)+'\n',encoding='utf-8')
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'data'/'stories_transactions.csv')
    parser.add_argument('--out',type=Path,default=ROOT/'outputs')
    args=parser.parse_args()
    manifest=generate(args.source,args.out)
    print(f"Built shared baselines, cost evidence, explanation ledger and report in {args.out.resolve()}")
    print(f"{manifest['check_count']} reconciliation checks matched; original data unchanged.")


if __name__=='__main__':
    main()
