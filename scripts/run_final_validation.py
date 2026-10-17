"""Run the final analytical pipeline, preserving per-script logs and source hashes.

Use the bundled Python interpreter for reproducibility. No plotting or document
rendering is included. Those have separate visual checks.
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs/final_review"
LOGS = OUT / "pipeline_logs"
SOURCE = ROOT / "data/stories_transactions.csv"
STEPS = [
    ("validate_baseline", []),
    ("cost_gap_scenarios", []),
    ("price_matching", []),
    ("discount_comparison", []),
    ("feasibility", []),
    ("consolidated", []),
    ("basket_comparison", []),
    ("category_mix", []),
    ("common_price_reference", []),
    ("basket_types_and_months", []),
    ("order_type_demand", []),
    ("where_garden_does_well", []),
    ("08_gap_decomposition", []),
    ("09_matched_baskets", []),
    ("10_robustness", []),
    ("build_cost_evidence", ["--out", str(OUT / "cost_evidence")]),
    ("validate_final_report", []),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    LOGS.mkdir(parents=True, exist_ok=True)
    original_hash = sha(SOURCE)
    results = []
    started = datetime.now(timezone.utc).isoformat()
    for index, (name, arguments) in enumerate(STEPS, 1):
        script = ROOT / "scripts" / (name + ".py")
        before = time.perf_counter()
        command = [sys.executable, str(script), *arguments]
        try:
            completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=120)
            stdout, stderr, code = completed.stdout, completed.stderr, completed.returncode
        except subprocess.TimeoutExpired as exc:
            stdout, stderr, code = str(exc.stdout or ""), str(exc.stderr or ""), -1
            stderr += "\nPipeline step exceeded the 120-second timeout."
        log = LOGS / f"{index:02d}_{name}.log"
        log.write_text("STDOUT\n" + stdout + "\nSTDERR\n" + stderr)
        results.append(dict(step=index, script=str(script.relative_to(ROOT)), arguments=arguments,
            status="PASS" if code == 0 else "FAIL", exit_code=code,
            seconds=round(time.perf_counter()-before,3), script_sha256=sha(script),
            source_unchanged_after_step=sha(SOURCE)==original_hash, log=str(log.relative_to(ROOT))))
        print(f"{index:02d} {name}: {results[-1]['status']}", flush=True)

    crosschecks=[]
    def record(name, condition, detail):
        crosschecks.append(dict(check=name, passed=bool(condition),detail=detail))

    if all(r["status"]=="PASS" for r in results):
        independent=json.loads((OUT/"numeric_audit.json").read_text())
        baseline=pd.read_csv(ROOT/"output/tables/01_branch_summary.csv").set_index("Branch")
        for r in independent["branch_totals"]:
            branch=r["branch"]
            okay=all(abs(float(baseline.loc[branch,col])-float(r[key]))<1e-8 for col,key in
                     [("Revenue","revenue"),("GrossProfit","gross_profit"),("RecordedCost","recorded_cost"),
                      ("Transactions","transactions"),("Units","units")])
            record("Legacy baseline agrees with independent audit / "+branch,okay,"Revenue, gross profit, cost, units, transactions")
        dec=pd.read_csv(ROOT/"out/08_gap_decomposition.csv").set_index(["comparison","component"])
        component_map={"costs":"Recorded unit costs","prices":"List prices","discounts":"Realized discounts",
            "units_per_basket":"Units per basket","product_mix":"Product mix","rounding_residual":"Cent rounding of recorded lines"}
        for peer in ["Harbour","Uptown"]:
            okay=True
            for r in [r for r in independent["decomposition"] if r["peer"]==peer]:
                reported=dec.loc[("Garden -> "+peer,component_map[r["factor"]])]
                for legacy,key in [("declared_order_$","forward"),("reverse_order_$","reverse"),("all_orders_average_$","shapley")]:
                    okay=okay and abs(float(reported[legacy])-r[key])<=0.000051
            record("Decomposition agrees with independent audit / "+peer,okay,"All factors, declared/reverse/all-120-orders; 4-decimal export precision")
        matched=pd.read_csv(ROOT/"out/09_matched_baskets.csv").set_index(["comparison","variant"])
        for r in independent["matched_baskets"]:
            if r["variant"] != "all lines":
                continue
            v=matched.loc[("Garden vs "+r["peer"],"all lines")]
            okay=abs(float(v["Garden_coverage_%"])-r["garden_coverage_pct"])<=0.0051 and abs(float(v["matched_gap_$"])-r["gap_per_basket"])<=0.0051
            record("Matched baskets agree with independent audit / "+r["peer"],okay,"Coverage and gap; 2-decimal export precision")
        scenarios=json.loads((ROOT/"outputs/decision/calculation_validation.json").read_text())
        record("Complete scenario and sensitivity validation",scenarios["status"]=="passed" and scenarios["scenario_count"]==16 and scenarios["sensitivity_cells"]==384,"16 scenarios; 384 hypothetical sensitivity cells")
        cost=json.loads((OUT/"cost_evidence/manifest.json").read_text())
        record("Canonical cost-evidence reconciliation",cost["all_checks_match"],f"{cost['check_count']} reconciliation checks")
        record("Independent final report audit",all(c["passed"] for c in independent["checks"]),f"{len(independent['checks'])} numerical/data checks; {len(independent['source_claim_review'])} source-claim reviews")
    record("Original source hash unchanged",sha(SOURCE)==original_hash,original_hash)
    passed=all(r["status"]=="PASS" and r["source_unchanged_after_step"] for r in results) and all(c["passed"] for c in crosschecks)
    manifest=dict(status="PASS" if passed else "FAIL", started_at_utc=started,
        completed_at_utc=datetime.now(timezone.utc).isoformat(), python_executable=sys.executable,
        python_version=platform.python_version(), pandas_version=pd.__version__,
        source=str(SOURCE.relative_to(ROOT)),source_sha256_before=original_hash,source_sha256_after=sha(SOURCE),
        script_count=len(results),passed_scripts=sum(r["status"]=="PASS" for r in results),steps=results,
        crosschecks=crosschecks,
        scope="Analytical pipeline only; figures and document layout are validated separately.",
        caveats=["A successful script run does not establish causal effects, feasible savings, or estimated customer response.",
                 "Legacy baseline floating-point rounding diagnostic is superseded by the Decimal audit: all line GP identities exact and revenue deviations within half a cent.",
                 "Common-reference tables must be interpreted using signed effects; the independent audit supplies full precision."])
    (OUT/"pipeline_validation.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"status":manifest["status"],"passed_scripts":manifest["passed_scripts"],"crosschecks":len(crosschecks)},indent=2))
    return 0 if passed else 1


if __name__=="__main__":
    raise SystemExit(main())
