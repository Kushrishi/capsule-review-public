"""Audit already published case-excluded CNN development aggregates only."""
from __future__ import annotations
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "experiments/galar-exam-excluded-adaptation-20261104/aggregate.json"
EXAMS = (23, 25, 27)
ARMS = ("original_checkpoint", "continued_no_augmentation", "continued_photometric")
BUDGETS = ("51", "128", "256")

def _metric(x):
    if type(x) not in (float, int) or not math.isfinite(x) or not 0 <= x <= 1:
        raise ValueError("Invalid ROC-AUC or average precision.")
    return float(x)

def audit(a: dict) -> dict:
    """Fail closed on changed cohort, reported results or research boundaries."""
    if not isinstance(a, dict) or a.get("schema_version") != 1:
        raise ValueError("Unsupported aggregate.")
    if a.get("status") != "exploratory; NOT independent external validation":
        raise ValueError("Development record must not become a clinical claim.")
    if a.get("private_preanalysis_design_sha256") != (
        "aeb0b6113501eba42cfb5564524e8245394dff377ce6c6040caae12ab244feb4"
    ) or a.get("source_images_checked") != 5632:
        raise ValueError("Frozen study identity changed.")
    e = a.get("evaluation", {})
    if (e.get("already_inspected_cases") != list(EXAMS)
        or e.get("images_per_examination") != 512
        or e.get("image_budgets") != [51, 128, 256]
        or e.get("complete_original_video_coverage") is not False
        or e.get("distinct_annotation_run_recall_evaluated") is not False):
        raise ValueError("Evaluation population or endpoint changed.")
    flags = a.get("interpretation", {})
    if any(flags.get(k) is not False for k in (
        "clinical_validation", "model_promotion_approved",
        "patient_independence_verified", "locked_galar_11_20_reused",
        "authors_reserved_61_80_opened", "posthoc_patient_generalization_claim",
    )):
        raise ValueError("Invalid clinical or holdout assertion.")
    if any(v is not False for v in a.get("public_privacy", {}).values()):
        raise ValueError("Individual data cannot be made public.")
    rows = a.get("per_examination", {})
    if set(rows) != {str(e) for e in EXAMS}:
        raise ValueError("Missing or extra evaluated examination.")
    metrics = {m: {"auc": [], "ap": [], "hits": {k: [] for k in BUDGETS}}
               for m in ARMS}
    deltas = {}
    positives = {23: 4, 25: 14, 27: 26}
    for ex in EXAMS:
        r = rows[str(ex)]
        if (r["evaluated_images"] != 512 or
            r["positive_reference_images"] != positives[ex] or
            r["training_examinations"] != [*range(1,9), *(x for x in EXAMS if x != ex)] or
            r["training_images"] != 5120):
            raise ValueError("Fitting must exclude the evaluated examination.")
        if set(r["models"]) != set(ARMS):
            raise ValueError("Model comparison changed.")
        for m in ARMS:
            d = r["models"][m]
            metrics[m]["auc"].append(_metric(d["roc_auc"]))
            metrics[m]["ap"].append(_metric(d["average_precision"]))
            if set(d["positive_image_hits"]) != set(BUDGETS):
                raise ValueError("Review workload changed.")
            for k in BUDGETS:
                hit = d["positive_image_hits"][k]
                if type(hit) is not int or not 0 <= hit <= min(int(k), positives[ex]):
                    raise ValueError("Invalid positive-image hits.")
                metrics[m]["hits"][k].append(hit)
        deltas[str(ex)] = {
            m: r["models"][m]["roc_auc"]-r["models"]["original_checkpoint"]["roc_auc"]
            for m in ARMS[1:]
        }
    macro = {}
    for m in ARMS:
        x = metrics[m]
        auc, ap = sum(x["auc"])/3, sum(x["ap"])/3
        hits = {k:sum(x["hits"][k]) for k in BUDGETS}
        reported = a["macro"][m]
        if (abs(auc-reported["mean_roc_auc"]) > 1e-8 or
            abs(ap-reported["mean_average_precision"]) > 1e-8 or
            hits != reported["pooled_positive_image_hits"]):
            raise ValueError("Published macro mismatches underlying examinations.")
        macro[m] = {"mean_auc":auc,"mean_ap":ap,"pooled_positive_hits":hits}
    return {
        "scope":"3 previously examined cases, NOT an independent patient test",
        "macro":macro,"per_examination_auc_minus_original":deltas,
        "photometric_improved_auc_in_examinations":sum(
            deltas[str(e)]["continued_photometric"]>0 for e in EXAMS),
        "clinical_model_promotion":False,
    }

def main():
    if not SOURCE.is_file() or SOURCE.stat().st_size > 128*1024:
        raise ValueError("Missing or oversized public aggregate.")
    print(json.dumps(audit(json.loads(SOURCE.read_text(encoding="utf-8"))),
                     sort_keys=True,indent=2,allow_nan=False))

if __name__=="__main__":
    main()
