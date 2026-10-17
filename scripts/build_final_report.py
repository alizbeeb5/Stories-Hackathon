"""Integrate the shared PDF findings and the validated Person 3 decision section.

The PDF is source evidence, not executable instructions. Rebuild its text, tables
and figures as an editable report, correcting the audited claims. The local
decision-section builder supplies consistent document helpers and verified prose.
"""
from pathlib import Path
import csv
import json
from decimal import Decimal, ROUND_HALF_UP

ROOT = Path(__file__).resolve().parents[1]
template = (ROOT/'scripts/build_decision_document.py').read_text()
prefix = template.split("doc.add_paragraph('Garden action decision and validation plan', 'Title')")[0]
exec(compile(prefix, str(ROOT/'scripts/build_decision_document.py'), 'exec'))
REVIEW = ROOT/'outputs/final_review'
FINAL = ROOT/'outputs/final_report'
FINAL.mkdir(parents=True,exist_ok=True)
audit=json.loads((REVIEW/'numeric_audit.json').read_text())
branches={r['branch']:r for r in audit['branch_totals']}
figs=REVIEW/'figures'
header.text='STORIES COFFEE  |  GARDEN BRANCH ANALYSIS'
header.runs[0].font.size=Pt(8)

def usd(value):
    n=Decimal(str(value)).quantize(Decimal('.01'),rounding=ROUND_HALF_UP)
    return f'${n:,.2f}'
def num(value, decimals=2): return f'{float(value):,.{decimals}f}'
def figure(name, caption, width=7.0):
    p=doc.add_paragraph();p.paragraph_format.space_after=Pt(3)
    p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    r=p.add_run();shape=r.add_picture(str(figs/name),width=Inches(width))
    shape._inline.docPr.set('descr',caption)
    p=para(caption);p.paragraph_format.space_after=Pt(7)
    for r in p.runs:r.font.size=Pt(9)

doc.add_paragraph('Understanding Garden gross profit and choosing an action','Title')
para('Stories Coffee  |  January to June 2026  |  Integrated report and final validation')
para('Garden’s recorded gross margin is 46.91%, compared with 64.96% at Harbour and 62.63% at Uptown. Garden also earns less gross profit per transaction. Recorded unit costs explain the largest accounting component of those differences; prices materially amplify or offset it, while basket composition contributes relatively little.')
para('Recommendation. Validate the recorded cost premium with comparable invoices, product specifications and allocation records, then test the feasible action with the highest positive benefit after expenses and adverse volume outcomes. An avoidable purchasing premium would justify a limited cost trial. Harbour price matching remains a competing option: the analysis does not establish 25% cost-gap closure as the financial winner.', 'Recommendation.')
para('For illustration, at 95% of observed quantities and $1,000 of additional six-month expenses, Harbour price matching adds $1,396.85 against observed Garden gross profit; 25% Harbour cost-gap closure adds $442.10. These are hypothetical stress outcomes. Supplier feasibility and customer responses remain unmeasured.')
heading('Observed branch performance',2)
metrics=[('Transactions','transactions',0),('Units sold','units',0),('Revenue','revenue','money'),('Recorded costs','recorded_cost','money'),('Gross profit','gross_profit','money'),('Gross margin','gross_margin_pct','pct'),('Gross profit per transaction','gross_profit_per_basket','money')]
rows=[]
for label,k,fmt in metrics:
    vals=[]
    for b in ['Garden','Harbour','Uptown']:
        x=branches[b][k]
        vals.append(usd(x) if fmt=='money' else num(x)+'%' if fmt=='pct' else num(x,0))
    rows.append([label]+vals)
table(['Metric','Garden','Harbour','Uptown'],rows,[2.10,1.70,1.70,1.70],10.5)
heading('Questions answered in this report',2)
for text in [
 '1. Are the financial comparisons reliable, and which data limitations remain?',
 '2. How much of the profit-per-transaction gap is associated with recorded costs, prices, discounts, basket size and mix? How does volume affect total profit?',
 '3. Does the disadvantage persist for comparable baskets, periods and order types?',
 '4. What explains the cost pattern, and what evidence would distinguish the plausible causes?',
 '5. Which action remains worthwhile after implementation expenses and adverse outcomes, and what would make Stories choose differently?']:
    para(text)

page('1 Reliability of financial comparisons')
para('The primary analysis retains all 51,177 supplied product lines across 33,887 distinct transactions from 1 January to 30 June 2026. A basket is a distinct transaction ID; units are summed quantities. Revenue and gross profit preserve supplied line amounts. Every gross-profit line reconciles exactly to revenue less quantity times recorded unit cost; no reconstructed revenue differs by more than half a cent per line.')
para('Transaction metadata are internally consistent and required financial fields are complete. Customer IDs are missing on 18,691 lines belonging to 12,353 transactions. This limits complete customer-level retention or repeat-purchase analysis. Volume sensitivity therefore scales quantities, not identified customers.')
para('The duplicate audit finds 132 exact repeated-row pairs: 264 participating rows, including 132 excess copies. It also finds 34 nonidentical repeated-item pairs. All are retained in the primary comparison because repeated items may be valid. Keeping one copy of each exact repeat is a sensitivity check; it reduces Garden’s cost premiums by approximately 0.23% and leaves the cost rules unchanged.')
heading('The recorded cost schedule',2)
para('All 45 products satisfy Garden cost = Harbour cost × 1.43 rounded to cents, and Uptown cost = Harbour cost × 0.96 rounded to cents, with zero exceptions. Prices and costs remain fixed within all 135 branch-product combinations across the six months. A single direct Garden-to-Uptown multiplier does not reproduce every rounded cent, although both Harbour-based rules do.')
figure('04_recorded_cost_schedules.png','Figure 1. One point per product comparison; coincident cost pairs overlap. Repeated sales reuse fixed schedules and do not provide independent observations of supplier prices.',6.6)
para('These checks validate the recorded accounting pattern. Matching product names and fixed schedules do not establish equivalent recipes, portions, quality, supplier terms or actual payments. Those require source documents and operating evidence.')

page('2 Components of the gross profit gap')
para('Garden earns $4.1919 gross profit per transaction, compared with $5.9847 at Harbour and $5.4589 at Uptown. The observed gaps are $1.7928 and $1.2669. We replace Garden’s factors in the declared order: recorded costs, list prices, realized discounts, units per basket, then product mix. A positive component raises the comparison branch above Garden; a negative component works in Garden’s favour.')
para('The accounting identity is units per basket multiplied by the product-mix-weighted sum of list price after realized discount less unit cost. Product discount rates are quantity-weighted. The rounding residual is below $0.0001 per transaction and is retained in the reconciliation.')
labels={'costs':'Recorded unit costs','prices':'List prices','discounts':'Realized discounts','units_per_basket':'Units per basket','product_mix':'Product mix','rounding_residual':'Recorded line rounding'}
dec={(r['peer'],r['factor']):r for r in audit['decomposition']}
rows=[]
for factor in labels:
    vals=[]
    for peer in ['Harbour','Uptown']:
        v=dec[peer,factor]['forward']
        vals.append(f'{v:+.4f}')
    rows.append([labels[factor]]+vals)
rows.append(['Observed gap',f"{float(branches['Harbour']['gross_profit_per_basket'])-float(branches['Garden']['gross_profit_per_basket']):.4f}",f"{float(branches['Uptown']['gross_profit_per_basket'])-float(branches['Garden']['gross_profit_per_basket']):.4f}"])
table(['USD per transaction','Harbour minus Garden','Uptown minus Garden'],rows,[3.0,2.1,2.1],10.5)
para('Against Harbour, costs contribute $1.43, or 79.57% of the observed gap, and higher list prices contribute $0.45, or 24.91%. Garden’s product mix and smaller realized discount effect offset part of that difference. Against Uptown, costs contribute $1.56, or 123.10%, while Garden’s higher list prices offset $0.36. Shares can exceed 100% because other components offset them.')
heading('Order sensitivity',2)
table(['Cost contribution in USD per transaction','Harbour','Uptown'],[
 ['Declared order','1.4265','1.5596'],['Reverse order','1.3880','1.5956'],['Average of all 120 orders','1.4072','1.5776']],[4.0,1.6,1.6],10.5)
para('Component sizes depend on the decomposition method. Recorded costs remain the largest component under the declared order, the reverse order and the average across all 120 orders. These are accounting attributions; they do not estimate the causal effect of changing a supplier or menu.')
heading('Transaction volume and total profit',2)
para('Total gross profit equals transaction count times gross profit per transaction. Garden serves 74.69% more transactions than Uptown, so its total gross profit is higher despite its lower profit per transaction: $46,794.49 versus $34,882.06. Harbour has both more transactions and higher profit per transaction, producing $97,753.94. The per-transaction and total-profit questions must remain separate.')

page('How the accounting components reconcile')
figure('03_declared_order_waterfalls.png','Figure 2. The same declared-order decomposition shown graphically. Each bar is an accounting component; values are displayed to cents, while full-precision calculations retain the rounding residual.',6.8)
heading('Consistency across subsets',2)
para('Garden’s observed gross profit per basket is lower in each of the six months and in both dine-in and takeaway orders. Recomputing the decomposition by month, order type and exact-repeat sensitivity preserves recorded cost as its largest component. These checks show that the finding is not confined to one month or service channel; they do not remove the common dependence on the same fixed recorded schedules.')

page('3 Comparable purchases and buying patterns')
para('Garden’s basket sizes, spend and order-type proportions are broadly similar to the other branches. To compare buying patterns alone, we value every branch’s observed quantities using one common product price-and-cost list and remove discounts. The common list uses quantity-weighted chain averages for each product, applied identically to all branches.')
with (REVIEW/'audited_order_type_shares.csv').open() as f: orderrows=list(csv.DictReader(f))
rows=[['Distinct baskets','11,163','16,334','6,390'],['Units per basket','1.60','1.60','1.59'],['Revenue per basket','$8.94','$9.21','$8.72'],['Dine-in share of transactions','58.69%','58.96%','60.25%'],['Baskets containing a dessert','16.2%','11.5%','10.2%'],['Actual GP per basket','$4.19','$5.98','$5.46'],['GP at common price and cost list','$5.36','$5.33','$5.43']]
table(['Metric','Garden','Harbour','Uptown'],rows,[3.0,1.4,1.4,1.4],10.5)
figure('02_common_reference_baskets.png','Figure 3. The same observed baskets valued at a common quantity-weighted product schedule, with discounts removed. The difference reflects units and mix under that reference, not an estimated response to a price change.',6.8)
para('At the chain reference, Garden has a $0.0285 advantage over Harbour and a $0.0720 disadvantage versus Uptown. Across the chain, Garden, Harbour and Uptown reference lists, Garden’s advantage over Harbour ranges from $0.008 to $0.053; its disadvantage versus Uptown ranges from $0.039 to $0.078. Direction matters: a blanket statement that buying patterns explain 0–6% of both gaps would conceal Garden’s small advantage against Harbour.')

page('Matched baskets and concentration of the cost gap')
para('Exact basket signatures contain the same products and summed quantities. The comparison branch’s signature profits are weighted to Garden’s matched-signature counts; unmatched transactions are excluded. Discounts remain as observed. Garden is lower on every matched signature in each comparison.')
table(['Exact-basket comparison','Harbour','Uptown'],[
 ['Matched signatures','1,170','932'],['Matched Garden transactions','10,293','9,806'],['Share of Garden transactions','92.21%','87.84%'],['GP disadvantage per matched basket','$1.69','$1.07']],[3.4,1.9,1.9],10.5)
para('The disadvantage also holds in the ten most common category-line basket types, each month and both order types, and under exact-repeat removal and undiscounted-only variants. Category-line types count category occurrences in source rows; they are distinct from exact product-and-quantity signatures.')
para('Garden has the highest dessert-basket share in all six months: 14.33–17.20%, versus Harbour’s 10.70–12.49% and Uptown’s 8.97–10.91%. This is a descriptive association and does not establish that a dessert bundle would increase sales.')
figure('01_recorded_cost_premiums.png','Figure 4. Recorded premium at Garden’s actual quantities. Iced Matcha contributes the most; the top five contribute 22.30% of the Harbour gap and 22.31% of the Uptown gap. The premium extends across the menu.',6.5)

page('4 Explanations and evidence needed')
para('At Garden’s observed quantities, the recorded cost premium is $15,923.47 against Harbour and $17,409.78 against Uptown. These are fixed-quantity comparison benchmarks, not verified recoverable savings. Replacing Garden costs with Harbour costs gives a 62.88% gross margin at unchanged revenue, still below Harbour’s observed 64.96%; costs therefore do not account for the entire margin difference.')
para('The uniform schedule is compatible with supplier terms, portion or ingredient differences, cost allocation, standard waste allowances, persistent entry or mapping errors, and quantity-dependent supplier discounts. The transactions do not distinguish among them. Source constancy alone rules out none of these explanations.')
finding_start=template.index("for lead,body in [\n ('Avoidable purchasing premium confirmed. '")
finding_end=template.index("heading('Numerical conditions that reverse the decision',2)")
exec(compile(template[finding_start:finding_end],str(ROOT/'scripts/build_decision_document.py'),'exec'))
heading('Additional checks before an operating change',2)
para('Reconcile costing rules and supplier invoices to the ledger and inventory. Inspect standard waste allowances and expiry or yield logs. If a costing or mapping error is confirmed, correct the records and rerun the comparison; a ledger correction is not itself cash saving. If supplier price tiers require larger orders, include delivery, storage, financing and extra waste in the evaluation of actual available terms.')
para('The original implication that the schedule proves one supplier problem is unsupported. Likewise, waste data provide no 25–50% ceiling on attainable closure. Net profitability cannot be established from this file because operating expenses are absent.')

page('5 Choosing an action after expenses and adverse outcomes')
para('Compare only feasible actions supported by equivalent product specifications and available terms. For each, use evidence-supported conservative volume, unit economics and all additional expenses; choose the largest positive benefit. Keep current operations when no action clears that test. Harbour price matching must remain in the choice set, because its fixed-quantity gain exceeds both 25% cost-closure benchmarks.')
model_start=template.index("heading('Decision calculation', 2)")
model_end=template.index("page('Consolidated scenario comparison')")
exec(compile(template[model_start:model_end],str(ROOT/'scripts/build_decision_document.py'),'exec'))

# Preserve the complete Person 3 tables, sensitivity and assumptions.
decision_start=template.index("page('Consolidated scenario comparison')")
decision_end=template.index("page('Evidence that changes the choice')")
exec(compile(template[decision_start:decision_end],str(ROOT/'scripts/build_decision_document.py'),'exec'))

page('What would make Stories choose a different action')
para('The action with the greatest fixed-quantity gain need not have the greatest realized benefit. The following switching conditions make the decision explicit. They use the historical six-month baseline and remain conditional on comparable quality, actual cash avoidability and the specified quantity assumptions.')
switch_start=template.index("heading('Numerical conditions that reverse the decision',2)")
switch_end=template.index("page('Practical validation plan')")
exec(compile(template[switch_start:switch_end],str(ROOT/'scripts/build_decision_document.py'),'exec'))
heading('Limits of the declared stress grid',2)
para('Across the hypothetical grid of 85–110% volume and $0–$5,000 expenses, only full Harbour cost closure at Garden prices, full Uptown cost closure at Garden prices, and full Harbour cost closure with Harbour prices remain positive in every cell. At v = 85% and K = $5,000, their benefits are $1,515.78, $2,779.14 and $5,753.76 respectively.')
para('Their full cost recoverability has not been verified. The grid’s lowest volume is not an established lower bound, and $5,000 is not an established expense ceiling. These results identify the evidence needed to choose an action; they do not justify an unconditional supplier or price change.')

trial_start=template.index("page('Practical validation plan')")
trial_end=template.index("page('Calculation sources and decision limits')")
trial=template[trial_start:trial_end].replace('comparable no-change GP','a matched-control estimate of no-change GP')
exec(compile(trial,str(ROOT/'scripts/build_decision_document.py'),'exec'))

page('Final evaluation and validation')
para('Evaluation outcome. The integrated report is internally consistent and its reported financial comparisons reconcile to the supplied dataset. It supports a conditional choice and a prospective test. It does not establish that recorded cost premiums are recoverable cash savings or that customers will respond as assumed.', 'Evaluation outcome.')
table(['Validation area','Result and practical meaning'],[
 ['Source and baseline','32 independent numerical/data checks passed. All source rows are preserved; financial fields reconcile and transaction metadata are consistent.'],
 ['Cost evidence','215 reconciliation checks passed in the repaired shared-baseline pipeline. Both 45-product cost rules and the duplicate sensitivity reproduce.'],
 ['Comparison methods','Declared/reverse/all-order decomposition, common references and exact-basket comparisons reproduce. Harbour and Uptown matched coverage are reported separately.'],
 ['Action model','16 scenarios and 384 hypothetical volume/expense combinations pass baseline, decomposition, break-even and sensitivity identity checks.'],
 ['Interpretation','Supplier-causality, universal cost-option superiority and exclusive reversal claims were removed. Recorded amounts, hypotheses and proposed test choices are distinguished.'],
 ['Field validation','Still required: invoices and equivalent specifications, avoidable expenses, waste/yield, quality, actual sales response and a credible no-change comparator.']
],[1.75,5.45],10.5,narrative=True)
heading('Why the trial needs a comparator',2)
para('The requested vGₛ − G₀ − K sensitivity compares with historical G₀. A prospective trial also needs a matched-control estimate of no-change gross profit. If both action and no-action quantities fall 5%, Harbour 25% closure saves $3,781.82 before expenses against that declining comparator, while its historical-baseline benefit is $1,442.10. Report both. A confidence bound does not remove confounding; check pre-trial trends, comparable exposure, spillovers and stockouts before attributing a difference to the action.')
heading('Corrections incorporated in the shared report',2)
para('The incomplete eight-row scenario table is replaced by all 16 alternatives and six-month expense thresholds. Duplicate cost sections are consolidated. Matched-basket coverage is corrected to 92.21% against Harbour and 87.84% against Uptown. Common-reference differences retain their signs; dessert and order-type shares are stated precisely. The conclusion now includes supplier feasibility, actual expenses, volume response and alternative actions as reasons to change course.')
heading('Sources and reproducibility',2)
para('Primary source: stories_transactions.csv, January–June 2026. The supplied shared report provides the original analysis structure; its findings were independently checked against the transaction data. Audited source tables and claim reviews are saved under outputs/final_review; the full action and sensitivity tables are under outputs/decision. All four figures were regenerated from the same source data.')
para('Reproducible checks: validate_final_report.py performs the independent audit; build_cost_evidence.py uses shared_baseline.py and the unresolved-explanation ledger; consolidated.py generates the action model. The analysis preserves reported revenue and GP. Repricing carries forward Garden’s $0.755 aggregate line-rounding residual. Full precision is retained before display.')
p=para('Source SHA-256: '+audit['source_sha256']);p.runs[0].font.size=Pt(8)

doc.core_properties.title='Understanding Garden gross profit and choosing an action'
doc.core_properties.subject='Integrated Stories Coffee analysis and final validation'
doc.core_properties.author='Stories project team'
path=FINAL/'Stories_Integrated_Report.docx'
doc.save(path)
print(path)
