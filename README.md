# Stories Hackathon

Analysis of Stories Coffee transactions from January to June 2026, explaining
Garden's recorded gross-profit gap and comparing actions after implementation
expenses and adverse volume outcomes.

## Final submission

- [Integrated report PDF](outputs/final_report/Stories_Integrated_Report.pdf)
- [Editable integrated Word report](outputs/final_report/Stories_Integrated_Report.docx)
- [All 16 scenarios](outputs/decision/consolidated_scenarios.csv)
- [Break-even volume](outputs/decision/break_even_volume.csv)
- [Maximum implementation expenses](outputs/decision/maximum_implementation_expenses.csv)
- [All 384 sensitivity calculations](outputs/decision/sensitivity_long.csv)
- [Assumptions register](outputs/decision/assumptions_register.csv)
- [Action switching thresholds](outputs/decision/pairwise_action_thresholds.csv)

The integrated report replaces the earlier shared report and incorporates the
Person 3 section. The standalone Person 3 Word file is retained as supporting
work; use the integrated report for submission.

Garden's prices are below Harbour's and above Uptown's. At the same volume and
implementation expenses, Harbour price matching exceeds 25% Harbour cost-gap
closure. The recommendation is therefore conditional: confirm comparable,
avoidable costs, then test feasible actions and choose the largest positive
benefit under evidence-supported assumptions. Supplier availability and customer
responses have not been established by the transaction data.

## Reproduce the analysis

Use Python 3.12 and run from the repository root:

```sh
python -m pip install -r requirements.txt
python scripts/run_final_validation.py
python scripts/build_final_figures.py
python scripts/build_decision_document.py
python scripts/build_final_report.py
```

The validation runner executes 17 analytical scripts in dependency order,
reconciles their outputs, and exits with an error on failure. The report builder
reuses the decision builder's document helpers and sections, so keep both files.
The supplied source PDF is not needed to reproduce the rebuilt report.

The Word build does not export a PDF. Export it with Word or LibreOffice after
checking layout. For example, with LibreOffice installed:

```sh
libreoffice --headless --convert-to pdf --outdir outputs/final_report outputs/final_report/Stories_Integrated_Report.docx
```

The committed PDF was rendered from the committed Word document; every one of
its 14 pages was visually reviewed for readable figures, complete tables,
equations, page numbering, clipping and overflow. Different office software or
fonts can change pagination, so review a newly exported PDF before submission.

## Final validation

| Check | Result |
| --- | --- |
| Analytical scripts | 17 of 17 passed |
| Crosschecks between output families | 11 passed |
| Independent data and numerical audit | 32 checks passed; 18 original claims reviewed |
| Canonical cost evidence | 215 reconciliations passed |
| Decision model | 16 scenarios and 384 hypothetical sensitivity cells |
| Source preservation | SHA-256 unchanged |
| Integrated report layout | All 14 rendered pages reviewed |
| Final artifact checks | 41 checks passed, including report table values and file integrity |

See [pipeline manifest](outputs/final_review/pipeline_validation.json),
[independent audit](outputs/final_review/numeric_audit.json),
[cost evidence manifest](outputs/final_review/cost_evidence/manifest.json),
[scenario validation](outputs/decision/calculation_validation.json), and
[figure validation](outputs/final_review/figures/figure_validation.json).
The [submission validation record](outputs/final_review/submission_validation.json)
checks the report's scenario and break-even tables against their numerical
exports and records the final Word and PDF hashes.
The manifests and logs record the environments used. Analytical validation does
not establish causal effects or recoverable cash savings.

The primary data are `data/stories_transactions.csv`: 51,177 product lines,
33,887 transactions and 45 products across three branches. Source SHA-256:
`f1672e728c28295b2b802d878fd38a158ba039827b429355e8438ee0463237a1`.
All rows are retained; exact-repeat removal is a separate sensitivity check.
The Decimal audit is authoritative for rounding and supplied financial amounts.
The older floating-point baseline diagnostic can flag half-cent rounding ties;
all supplied gross-profit identities reconcile exactly and revenue deviations
remain within half a cent per line.

## Model and interpretation

For each action, `benefit = v * Gs - G0 - K`, with observed Garden gross profit
`G0 = $46,794.49`. `Gs` uses Garden's observed quantities; `v` scales quantities
with product mix and scenario unit economics fixed; `K` includes all additional
expenses over the same six months. The tested volume levels (85%, 90%, 95%, 100%,
105%, 110%) and expense levels ($0, $1,000, $2,500, $5,000) are hypothetical,
not estimated customer responses.

Closing 25% of the Harbour cost gap saves $3,980.87 at observed quantities, equal
to 7.52% of Garden's recorded costs. At 95% volume the benefit before expenses is
$1,442.10; after $1,000 of expenses it is $442.10. Harbour price matching yields
$1,396.85 under those same illustrative conditions. These comparisons do not
prove either action is achievable.

The report gives evidence conditions for purchasing premiums, allocations,
quality or portion differences and unresolved causes. Its proposed trial
measures actual purchase costs, additional expenses, waste, quality, sales and
realized financial benefit, with success and stop rules fixed before results.
Historical-baseline sensitivity and a contemporaneous no-change comparison are
reported separately.

## Repository map

- `scripts/`: analysis, validation, chart and document builders.
- `notes/explanations_ledger.csv`: unresolved explanations and required evidence.
- `outputs/final_report/`: authoritative submission report in Word and PDF.
- `outputs/decision/`: complete scenario model and supporting section.
- `outputs/final_review/`: independent audit, cost evidence, final figures and logs.
- `out/` and `output/`: regenerated outputs of the original analysis scripts.

`shared_baseline.py` is the importable Decimal baseline used by the cost-evidence
builder. The original `validate_baseline 2.py` remains for project history.
Review renderings, extracted source pages, operating-system files and Python
caches are excluded from version control.
