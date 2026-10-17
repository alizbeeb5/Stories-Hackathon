"""Build the local Person 3 Word section from validated decision tables."""
from pathlib import Path
import csv
import hashlib
import json
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'outputs' / 'decision'
with (OUT / 'consolidated_scenarios.csv').open() as f:
    scenarios = list(csv.DictReader(f))
by_id = {r['Scenario_ID']: r for r in scenarios}
G0 = 46794.49

def number(r, k): return float(r[k])
def money(x): return ('−' if x < 0 else '') + f'${abs(x):,.2f}'
def whole(x): return ('−' if x < 0 else '') + f'{abs(x):,.0f}'
def pct(x): return f'{x:.2f}%'

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.top_margin = sec.bottom_margin = Inches(.62)
sec.left_margin = sec.right_margin = Inches(.65)
sec.header_distance = sec.footer_distance = Inches(.25)
styles = doc.styles
for name in ['Normal', 'Title', 'Subtitle', 'Heading 1', 'Heading 2', 'Heading 3']:
    styles[name].font.name = 'Calibri'
    styles[name].font.color.rgb = RGBColor(0,0,0)
styles['Normal'].font.size = Pt(11)
styles['Normal'].paragraph_format.space_after = Pt(7)
styles['Normal'].paragraph_format.line_spacing = 1.05
styles['Title'].font.size = Pt(23)
styles['Title'].paragraph_format.space_after = Pt(8)
styles['Heading 1'].font.size = Pt(17)
styles['Heading 1'].paragraph_format.space_before = Pt(0)
styles['Heading 1'].paragraph_format.space_after = Pt(9)
styles['Heading 2'].font.size = Pt(12.5)
styles['Heading 2'].paragraph_format.space_before = Pt(10)
styles['Heading 2'].paragraph_format.space_after = Pt(5)
for border in list(styles.element.iter(qn('w:pBdr'))):
    border.getparent().remove(border)
header = sec.header.paragraphs[0]
header.text = 'STORIES  |  GARDEN BRANCH  |  PERSON 3 DECISION ANALYSIS'
header.runs[0].font.size = Pt(8)
footer = sec.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.RIGHT
footer.add_run('January to June 2026 analysis  •  ' ).font.size = Pt(8)
field = OxmlElement('w:fldSimple'); field.set(qn('w:instr'), 'PAGE')
footer._p.append(field)

def para(text, boldlead=None, style=None):
    p = doc.add_paragraph(style=style)
    if boldlead and text.startswith(boldlead):
        p.add_run(boldlead).bold = True; p.add_run(text[len(boldlead):])
    else: p.add_run(text)
    return p

def heading(text, level=1): doc.add_heading(text, level=level)
def page(text):
    p=doc.add_heading(text, level=1)
    p.paragraph_format.page_break_before=True

def table(headers, rows, widths, font=10, narrative=False):
    t = doc.add_table(rows=1, cols=len(headers))
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    for col, width in zip(t.columns, widths): col.width = Inches(width)
    for c, txt in zip(t.rows[0].cells, headers): c.text = txt
    for row in rows:
        for c, txt in zip(t.add_row().cells, row): c.text = str(txt)
    tblpr = t._tbl.tblPr
    borders = OxmlElement('w:tblBorders')
    for edge in ['top','left','bottom','right','insideH','insideV']:
        e=OxmlElement('w:'+edge); e.set(qn('w:val'),'single'); e.set(qn('w:sz'),'4'); e.set(qn('w:color'),'D9D9D9'); borders.append(e)
    tblpr.append(borders)
    for i, row in enumerate(t.rows):
        trpr = row._tr.get_or_add_trPr()
        cant = OxmlElement('w:cantSplit'); trpr.append(cant)
        if i == 0:
            repeat=OxmlElement('w:tblHeader'); trpr.append(repeat)
        for j,c in enumerate(row.cells):
            c.width = Inches(widths[j]); c.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cp=c._tc.get_or_add_tcPr(); mar=OxmlElement('w:tcMar')
            for edge, val in [('top','65'),('bottom','65'),('left','85'),('right','85')]:
                e=OxmlElement('w:'+edge); e.set(qn('w:w'),val); e.set(qn('w:type'),'dxa'); mar.append(e)
            cp.append(mar)
            sh=OxmlElement('w:shd'); sh.set(qn('w:fill'),'20384A' if i==0 else ('F0F4F7' if i%2==0 else 'FFFFFF')); cp.append(sh)
            for p in c.paragraphs:
                p.paragraph_format.space_after = Pt(0)
                p.paragraph_format.line_spacing = 1.0
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT if j==0 or narrative else WD_ALIGN_PARAGRAPH.CENTER
                for r in p.runs:
                    r.font.size=Pt(font); r.bold=(i==0)
                    r.font.color.rgb=RGBColor(255,255,255) if i==0 else RGBColor(0,0,0)
    doc.add_paragraph().paragraph_format.space_after=Pt(0)
    return t

def mr(text):
    r=OxmlElement('m:r'); t=OxmlElement('m:t'); t.text=text; r.append(t); return r
def sub(base, index):
    s=OxmlElement('m:sSub'); e=OxmlElement('m:e'); e.append(mr(base)); s.append(e)
    si=OxmlElement('m:sub'); si.append(mr(index)); s.append(si); return s
def fraction(top, bottom):
    f=OxmlElement('m:f')
    for tag, parts in [('num',top),('den',bottom)]:
        e=OxmlElement('m:'+tag)
        for part in parts: e.append(part)
        f.append(e)
    return f
def equation(parts):
    p=doc.add_paragraph(); p.paragraph_format.space_after=Pt(5)
    m=OxmlElement('m:oMath')
    for part in parts: m.append(part)
    p._p.append(m)

doc.add_paragraph('Garden action decision and validation plan', 'Title')
para('Person 3 report section  |  Six months from 1 January to 30 June 2026')
para('Recommendation. Keep current operations while validating the recorded cost gap, then choose the feasible action with the highest positive benefit under evidence-supported volume and expense assumptions. Start with comparable supplier quotes and a limited purchasing trial if an avoidable premium is confirmed. Keep Harbour price matching as a competing test: the data do not establish a cost-only action as the financial winner.', 'Recommendation.')
para('The illustrative 25% Harbour cost closure earns $3,980.87 before implementation expenses at unchanged volume. At 95% volume and $1,000 in expenses, it earns only $442.10. Harbour price matching earns $1,396.85 under those same hypothetical conditions. Full cost closure produces larger modeled gains, but its availability and cash effect have not been demonstrated.')
heading('Corrected interpretation', 2)
para('Garden’s listed prices are below Harbour’s and above Uptown’s for all 45 matched products. Neither a deliberate pricing strategy nor a systematic recording or allocation error is ruled out by these transactions. Constant recorded costs are compatible with several explanations. Waste is unmeasured; the data support no 25–50% ceiling on attainable savings.')
heading('Decision calculation', 2)
para('Let Gₛ be scenario gross profit at Garden’s observed quantities and G₀ = $46,794.49. Let v scale quantities while product mix and scenario unit economics remain fixed. Let K be all additional implementation expenses over the same six months. This is a proportional accounting stress test; it estimates no demand curve or customer response.')
equation([mr('Incremental benefit = v'),sub('G','s'),mr(' − '),sub('G','0'),mr(' − K')])
equation([sub('v','break-even'),mr(' = '),fraction([sub('G','0'),mr(' + K')],[sub('G','s')])])
equation([sub('K','max'),mr(' = v'),sub('G','s'),mr(' − '),sub('G','0')])
para('These formulas apply because every Gₛ in the comparison is positive. A break-even v above 1 requires volume growth. A negative Kmax means the action loses against observed profit even with no implementation expense. Strictly positive benefit requires v above break-even, or K below Kmax.')
heading('What 25 percent closure means', 2)
para('Garden’s recorded costs total $52,954.06. Repricing its quantities at Harbour’s recorded unit costs gives $37,030.59, a $15,923.47 gap. Recovering one quarter of that gap saves $3,980.87, or 7.52% of Garden’s costs, and leaves $48,973.19 of costs. It does not mean cutting Garden costs by 25%. At 95% volume, 0.95 × $50,775.3575 − $46,794.49 = $1,442.10 before K.')

page('Consolidated scenario comparison')
para('All values cover the same six months. Dollar columns below are rounded to whole dollars for readability; supporting tables retain precision. H means Harbour and U means Uptown. Closure percentages refer to the reference cost gap. Garden’s observed discount rates are retained except in the final row.')
labels={
 'BASE':'Do nothing', 'H-P':'H prices only', 'U-P':'U prices only',
 'H-C025':'H gap 25% · Garden prices','H-C050':'H gap 50% · Garden prices','H-C100':'H gap 100% · Garden prices',
 'U-C025':'U gap 25% · Garden prices','U-C050':'U gap 50% · Garden prices','U-C100':'U gap 100% · Garden prices',
 'H-CP025':'H gap 25% · H prices','H-CP050':'H gap 50% · H prices','H-CP100':'H gap 100% · H prices',
 'U-CP025':'U gap 25% · U prices','U-CP050':'U gap 50% · U prices','U-CP100':'U gap 100% · U prices',
 'NO-DISC':'Remove recorded discounts'}
rows=[]
for r in scenarios:
    base=r['Scenario_ID']=='BASE'
    rows.append([labels[r['Scenario_ID']],pct(number(r,'Cost_Reduction_pct_of_Garden_Recorded_Cost')),
                 whole(number(r,'Scenario_GP_Gs_dollars')),whole(number(r,'Benefit_v100_K0_dollars')),
                 '—' if base else whole(number(r,'Benefit_v095_K1000_dollars'))])
table(['Action','Garden cost reduction','Gₛ\nUSD','Benefit\nv 100%\nK $0','Benefit\nv 95%\nK $1,000'],rows,[2.55,1.05,1.10,1.15,1.35],10)
para('Do nothing is the observed comparator: v = 1, K = $0 and benefit = $0. Applying different v or K to its coefficients is a baseline stress calculation, not a separate action; therefore its adverse-action cell is left blank.')
para('At the same v and K, Harbour price matching exceeds 25% Harbour cost closure by $1,005.00 at unchanged volume, and by $954.75 at 95% volume. Uptown 25% cost closure also exceeds Harbour 25% closure by $371.58 at unchanged volume. The choice of cost benchmark must therefore depend on attainable, comparable supplier terms.')
para('The $555.90 discount-removal gain is a fixed-quantity benchmark. Sales, retention and product mix may change if discounts are removed; that response is unknown. It is not a proven recoverable cash amount or a universal ceiling on potential gains.')

page('Break even volume and expense sensitivity')
para('Minimum quantities as a percentage of observed Garden volume. Equality means zero incremental benefit; a worthwhile action must exceed the threshold. Expense levels are explicitly hypothetical six-month totals, not budgets quoted by suppliers or estimated customer responses.')
rows=[]
for r in scenarios:
    if r['Scenario_ID']=='BASE': continue
    rows.append([labels[r['Scenario_ID']]] + [pct(number(r,f'Break_Even_v_K{k}')*100) for k in [0,1000,2500,5000]])
table(['Action','K $0','K $1,000','K $2,500','K $5,000'],rows,[2.80,1.10,1.10,1.10,1.10],10)
heading('Harbour 25 percent cost closure stress test',2)
para('Incremental benefit in USD. These volume levels are hypothetical quantities, with mix and unit economics fixed. Every cell uses the same Gₛ = $50,775.3575.')
gs=number(by_id['H-C025'],'Scenario_GP_Gs_dollars')
rows=[[pct(v*100)]+[whole(v*gs-G0-k) for k in [0,1000,2500,5000]] for v in [.85,.90,.95,1,1.05,1.10]]
table(['Volume v','K $0','K $1,000','K $2,500','K $5,000'],rows,[1.40,1.45,1.45,1.45,1.45],10)
para('At v = 95%, Kmax is $1,442.10. Raising K from $1,000 to $2,500 changes the result from +$442.10 to −$1,057.90. At v = 90%, the result is already −$1,096.67 before any implementation expenses.')

page('Assumptions register')
assumptions=[
 ('Observed baseline','Garden revenue $99,748.55, recorded costs $52,954.06 and GP $46,794.49 cover January–June 2026. They are historical observations, not a future no-action forecast.'),
 ('Comparable products','All 45 product names match, and branch/product prices and costs are constant in the file. Names alone do not establish equivalent recipes, portions, quality, service or supplier terms. Verify these before selecting a reference.'),
 ('Cash avoidability','Cost closure is hypothetical. Count savings only where procurement, waste or another expense actually falls. A lower allocated charge alone changes reported branch performance, not Stories’ total cash expenses.'),
 ('Closure mechanism','For each product, new cost equals Garden cost less α times its gap to the reference. The same α applies across products. If only some products change, aggregate their actual savings and recompute Gₛ.'),
 ('Volume and mix','v scales units sold, not customer or transaction counts. Product mix, discounts and scenario unit margins stay fixed. No elasticity is estimated. Recompute product-level profit if mix, terms, waste or unit costs change.'),
 ('Prices and discounts','Price matching changes list prices to the reference and preserves Garden discount rates. Removing discounts restores recorded discount dollars at fixed quantity. Neither customer response nor future promotion effectiveness is observed.'),
 ('Implementation expenses','K includes setup, training, testing, switching, delivery, minimum-order effects and six-month recurring expenses beyond scenario costs. Include additional waste or refunds once only; avoid double-counting amounts already in unit costs or net revenue.'),
 ('Sensitivity levels','v = 85%, 90%, 95%, 100%, 105% and 110%; K = $0, $1,000, $2,500 and $5,000. These are illustrative stress levels, not forecasts, probability bounds or estimated customer responses.'),
 ('Profit and timing','Results are gross-profit changes less additional expenses, not a full forecast of net profit. Existing fixed overhead is unchanged. Ramp-up delays and affected sales coverage must reduce projected benefits. A short trial cannot establish realized six-month benefit.'),
 ('Rounding and inference','Repricing adds modeled price changes to recorded revenue, preserving its $0.755 aggregate rounding residual. Full precision is kept until display. Repeated transactions at fixed prices and costs do not identify demand response or the cause of the cost gap.'),
]
table(['Assumption or evidence','Decision consequence'],assumptions,[1.65,5.55],10.5,narrative=True)
para('Scope of uncertainty. The missing evidence is supplier invoices and contracts, allocation rules, recipe and portion specifications, inventory and waste records, and a controlled sales response. Until these are resolved, the scenarios quantify conditional opportunities rather than validated actions.', 'Scope of uncertainty.')
with (OUT/'assumptions_register.csv').open('w',newline='') as f:
    w=csv.writer(f);w.writerow(['Assumption_or_evidence','Decision_consequence']);w.writerows(assumptions)

page('Evidence that changes the choice')
para('Decision rule. Compare only actions whose costs and operating requirements are demonstrably feasible. For each, use evidence-supported conservative quantities, unit economics and total expenses; choose the largest positive incremental benefit. If the result is zero or negative, or required evidence is absent, retain current operations and resolve that uncertainty. Run the price and cost tests separately before testing their combination.', 'Decision rule.')
heading('Findings and required action',2)
for lead,body in [
 ('Avoidable purchasing premium confirmed. ','Obtain like-for-like supplier terms at Garden’s actual purchase volumes, including freight, rebates, credit, minimum orders and service. Trial the quoted offer and count invoice-backed savings after additional expenses.'),
 ('Allocation difference confirmed. ','Correct branch performance comparisons and identify the expenses allocated to each branch. Count financial savings only where Stories’ underlying expenses actually fall; do not recommend a supplier change from an allocation correction.'),
 ('Quality or portion differences confirmed. ','Compare equivalent ingredients, recipes, yields and portion sizes. Evaluate like-for-like offers and customer quality acceptance before recommending cost reduction. Retain the premium if its value outweighs verified alternatives.'),
 ('Cause unresolved. ','A supplier-change recommendation is blocked by uncertainty over whether the recorded premium is a comparable and avoidable purchase cost. Obtain invoices, allocation rules and product specifications before proceeding.')]:
    para(lead+body,lead)
heading('Numerical conditions that reverse the decision',2)
for text in [
 'Harbour 25% cost closure: with K = $1,000, retain more than 94.13% of observed quantities. At v = 95%, keep K below $1,442.10. At v = 95% and K = $1,000, actual Harbour-gap closure must exceed 22.08%; at K = $2,500 it must exceed 31.99%.',
 'Choose Harbour price-only over Harbour 25% cost-only if, at equal expenses, price-only retains more than 98.06% while cost-only retains 100%, or more than 93.16% while cost-only retains 95%. If price-only costs $1,000 more and cost-only retains 100%, price-only must retain more than 99.99%. Independently require positive benefit versus baseline.',
 'Choose Uptown 25% cost closure over Harbour 25% if equally comparable and feasible: at v = 95%, Uptown can incur only $353.00 more expense before losing its advantage. With equal v and K, Harbour cost closure must exceed 31.31% of its gap to outperform Harbour price-only.',
 'Test the combined Harbour 25% cost closure and Harbour prices after both levers pass: at v = 95%, K = $1,000 it yields $5,178.67. Choose it only if the joint result survives actual demand, quality and expense measurements.',
 'Uptown price-only needs more than 9.36% volume growth at K = $0 or 11.70% at K = $1,000 merely to beat observed GP. Discount removal tolerates only 1.17% volume loss at K = $0. These thresholds require measured evidence before adoption.'
]: para(text)

page('Practical validation plan')
para('Proposed trial design. Use two weeks of baseline measurement followed by four weeks of a limited trial, covering at least two replenishment cycles. Before starting, record products, supplier terms, unchanged recipe/portion specifications, matched untreated products or alternating comparable periods, cost coverage, expense cap and stopping rules. This duration and the tolerances below are proposed management choices; the dataset does not establish them.', 'Proposed trial design.')
para('Purchasing trial: hold prices and promotions stable and test one cost change. Measure contemporaneous untreated products or periods to separate demand and seasonality from the change. Then, if warranted, test Harbour prices with cost and quality held stable. Use matched weekdays, order types and product groups; record spillovers and stockouts. A combined trial follows only if the separate tests justify it.')
para('Set minimum exposure from baseline daily variation before launch. Predeclare a one-sided 95% lower confidence bound on matched-day recurring incremental contribution. Project it only across verified coverage and rollout time, then deduct all six-month expenses once. Four weeks does not guarantee sufficient precision; an inconclusive result does not support rollout.')
heading('Measures and financial reconciliation',2)
for lead,body in [
 ('Purchase costs. ','Reconcile receipts, invoices, freight, rebates and usable yield per comparable unit. Track units purchased, consumed, sold and held in inventory. Separate purchase timing from actual expense reduction.'),
 ('Implementation expenses. ','Log setup, staff time, testing, transport, minimum-order commitments and recurring expenses. Maintain trial expenses and complete six-month K. Reduce projected savings for delayed rollout; do not also count those missed savings in K.'),
 ('Waste and quality. ','Weigh waste by product and reason; track waste cost, portion compliance, specification checks, blind quality scores, complaints and refunds. Reconcile waste with cost of sales to count it only once.'),
 ('Sales and realized benefit. ','Track quantities, mix, net revenue, discounts and returns daily. Calculate trial GP from actual net sales less actual consumed costs, then subtract comparable no-change GP and incremental expenses. Report the measured trial result separately from any six-month projection.')]: para(lead+body,lead)
heading('Predeclared success and stop conditions',2)
para('Economic success. For the illustrative Harbour 25% plan, require verified comparable savings equivalent to at least 25% of the weighted gap, total six-month K no greater than $1,000, and a conservative quantity assumption of at least 95%. These imply at least $442.10 under the model. Recalculate for actual coverage and ramp-up; do not award full savings to a partial rollout. Require a positive conservative six-month benefit bound. Report trial net benefit after all trial expenses even if upfront costs make it negative; this is a six-month decision, not a four-week payback rule.', 'Economic success.')
para('Operating success. Require every delivered trial batch to meet agreed ingredient and portion specifications. Predeclare no more than a 0.5 percentage-point increase in waste weight as a share of material handled, no more than a 1 percentage-point increase in orders with complaints or refunds, and no more than a 0.25-point drop in blind quality rating on a five-point scale. These are proposed tolerances, not estimated outcomes; fix them before data collection.', 'Operating success.')
para('Stop or hold. Stop on a specification failure or an operating tolerance breached at two consecutive weekly reviews. Hold expansion if K is forecast to exceed $1,000, conservative six-month benefit is zero or negative, or a volume/savings floor fails. At four weeks, incomplete invoices or an inconclusive six-month bound mean no rollout. Extend only within a budget and duration agreed before seeing the results. Reconcile actual benefit at six months before calling the projected saving realized.', 'Stop or hold.')

page('Calculation sources and decision limits')
para('Counterfactual check. The requested vGₛ − G₀ − K stress test uses historical G₀. The trial must also compare with a contemporaneous no-change estimate. If both action and no-action volumes fall 5%, Harbour 25% savings before K are $3,781.82 versus that comparator; $1,442.10 is the separate historical-baseline result. Report both and explain their difference.', 'Counterfactual check.')
heading('What the declared stress grid establishes',2)
para('Across the complete hypothetical grid of 85–110% volume and $0–$5,000 in expenses, only three modeled actions remain positive in every cell: 100% Harbour cost closure at Garden prices, 100% Uptown cost closure at Garden prices, and 100% Harbour cost closure with Harbour prices. At the most adverse grid point, v = 85% and K = $5,000, their benefits are respectively $1,515.78, $2,779.14 and $5,753.76.')
para('These are conditional stress results. The file supplies no evidence that full gap closure is commercially attainable, that the lowest tested volume is a lower bound, or that $5,000 is an upper bound on expenses. No action is established as universally worthwhile. Validated offers, measured sales response and a complete expense estimate determine which rows are eligible for the decision.')
heading('Source and reproducibility',2)
sha=hashlib.sha256((ROOT/'data/stories_transactions.csv').read_bytes()).hexdigest()
para('Primary source: data/stories_transactions.csv in the Stories Hackathon project. Garden has 17,833 units across 11,163 transactions in the six-month window. The cost scenarios match all 45 Garden products to the same named products at Harbour and Uptown.')
para('The revised cost_gap_scenarios.py, price_matching.py, discount_comparison.py and feasibility.py scripts correct the interpretation and support the calculation. consolidated.py recomputes all 16 scenarios directly from the source file and produces the common sensitivity grid. Assertions check baseline accounting, matched coverage, price ordering, decomposition, break-even identities and the requested Harbour 25% example.')
table(['Supporting file in outputs/decision','Contents'],[
 ('consolidated_scenarios.csv','All 16 alternatives, Gₛ, benefits, evidence conditions and break-even levels'),
 ('break_even_volume.csv','Minimum volume for each action at four expense levels'),
 ('maximum_implementation_expenses.csv','Kmax for each action at six volume levels'),
 ('sensitivity_long.csv','All 384 scenario × volume × expense calculations'),
 ('pairwise_action_thresholds.csv','Switching thresholds when actions retain different volumes or incur different expenses'),
 ('assumptions_register.csv','Assumptions and evidence limits used in this section'),
 ('calculation_validation.json','Inputs, period, rounding policy and passed numerical checks')
],[3.15,4.05],10.5,narrative=True)
para('All table amounts derive from the project data. Supplier feasibility, expense levels, volume stress levels and proposed trial tolerances are kept distinct from observations. No annualized gains or customer-response estimates are claimed.')
p=para('Source SHA-256: '+sha); p.runs[0].font.size=Pt(8)
para('Prepared as a local Word section for insertion into the shared project document. The project-wide final evaluation is a separate next step.')

path=OUT/'Stories_Person_3_Decision_Section.docx'
doc.core_properties.title='Garden action decision and validation plan'
doc.core_properties.subject='Person 3 scenario decision analysis'
doc.core_properties.author='Stories project team'
doc.save(path)
print(path)
