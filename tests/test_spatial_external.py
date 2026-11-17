"""Generated score/reference controls only; no models, images or source labels."""
import copy
from fractions import Fraction
from hashlib import sha256
import json

import pytest

from capsule_review.spatial_external import POLICY, evaluate


def h(value):
    return sha256(("generated:" + str(value)).encode()).hexdigest()


def raw(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def controls():
    population = {"schema": "cr-sp01-population-v1", "archive_sha256": h("archive"), "rows": []}
    reference = {"schema": "cr-sp01-references-v1", "version": "generated-v1", "rows": []}
    kinds = ["vascular", "vascular", "erosion", "erosion", "ulcer", "ulcer",
             "normal", "normal", "other", "unknown"]
    for i, kind in enumerate(kinds):
        ident = f"toy-{i}"
        population["rows"].append({"row_id": ident, "member": f"generated/{ident}.jpg", "image_sha256": h(i)})
        reference["rows"].append({"row_id": ident, "image_sha256": h(i), "tokens": [f"toy-{kind}"]})
    prediction = {"schema": "cr-sp01-predictions-v1", "six_selection_sha256": h("six"),
                  "method_sha256": h("method"), "models": []}
    for seed in (19, 37, 73):
        for arm in ("classifier", "detector"):
            scores = [[0.5, 0.5] for _ in kinds]
            if arm == "detector":
                scores = [[0.9 if k == "vascular" else 0.1,
                           0.9 if k in ("erosion", "ulcer") else 0.1] for k in kinds]
            prediction["models"].append({"seed": seed, "arm": arm,
                "checkpoint_sha256": h((seed, arm)), "selection_sha256": h((seed, arm, "selection")),
                "thresholds": [0.5, 0.5], "complete": True, "updates": 14180,
                "checkpoint_epochs": [4, 8, 12, 16, 20],
                "rows": [{"row_id": f"toy-{i}", "scores": s} for i, s in enumerate(scores)]})
    contract = {"schema": "cr-sp01-contract-v1", "policy": POLICY, "scope": "generated-control",
        "population": {}, "archive_sha256": h("archive"), "population_sha256": h("unset"),
        "predictions_sha256": h("unset"), "references_sha256": h("unset"),
        "reference_version": "generated-v1", "mapping": {f"toy-{k}": [k] for k in set(kinds)},
        "models": [{k: m[k] for k in ("seed", "arm", "checkpoint_sha256", "selection_sha256", "thresholds")}
                   for m in prediction["models"]],
        "six_selection_sha256": h("six"), "method_sha256": h("method"), "analysis_sha256": h("analysis")}
    return contract, population, prediction, reference


def packed(bundle):
    c, p, m, r = copy.deepcopy(bundle)
    c["population"] = {"rows": len(p["rows"]), "groups": len({x["image_sha256"] for x in p["rows"]})}
    inputs = [raw(x) for x in (p, m, r)]
    for key, data in zip(("population_sha256", "predictions_sha256", "references_sha256"), inputs):
        c[key] = sha256(data).hexdigest()
    cb = raw(c)
    return cb, sha256(cb).hexdigest(), *inputs


def run(bundle):
    return evaluate(*packed(bundle))


def duplicate(bundle, index, new_id):
    _, population, prediction, reference = bundle
    p = copy.deepcopy(population["rows"][index])
    p.update(row_id=new_id, member=f"generated/{new_id}.jpg")
    population["rows"].append(p)
    r = copy.deepcopy(reference["rows"][index])
    r["row_id"] = new_id
    reference["rows"].append(r)
    for m in prediction["models"]:
        row = copy.deepcopy(m["rows"][index])
        row["row_id"] = new_id
        m["rows"].append(row)


def test_met_exact_ratios_strict_ties_and_unknown_coverage():
    result = run(controls())
    assert result["verdict"] == "MET" and result["scope"] == "generated-control"
    assert result["primary"]["mean_paired_differences"]["vascular"] == "1"
    assert result["primary"]["criteria"] == dict.fromkeys(("H1", "H2", "H3", "H4"), True)
    metrics = result["primary"]["models"]["19-classifier"]
    assert metrics["vascular"] == {"hits": "0", "support": "2", "rate": "0", "rows": 2, "groups": 2}
    assert metrics["normal_any"]["rows"] == 2
    assert metrics["other_any"]["rows"] == metrics["unknown_any"]["rows"] == 1
    assert result == run(controls())


def test_group_weights_independently_recomputed():
    b = controls()
    for m in b[2]["models"]:
        if m["arm"] == "detector":
            m["rows"][1]["scores"][0] = 0.1
    duplicate(b, 0, "duplicate-v")
    r = run(b)
    assert r["conflicting_groups"] == 0
    # Independent direct-count oracle: two hits / three rows, one hit / two images.
    assert Fraction(r["primary"]["models"]["19-detector"]["vascular"]["rate"]) == Fraction(2, 3)
    assert Fraction(r["secondary"]["models"]["19-detector"]["vascular"]["rate"]) == Fraction(1, 2)
    assert r["primary"]["total_weight"] == "11" and r["secondary"]["total_weight"] == "10"


def test_independent_direct_count_oracle_and_order_invariance():
    b = controls()
    duplicate(b, 0, "v-copy"); duplicate(b, 6, "n-copy")
    for model in b[2]["models"]:
        for row, image in zip(model["rows"], b[1]["rows"]):
            n = int(image["image_sha256"][-2:], 16) + model["seed"] + (model["arm"] == "detector")
            row["scores"] = [(n % 3) / 2, ((n + 1) % 3) / 2]
    r = run(b)
    # Independent small-loop oracle: no production eligibility/metric helpers.
    for name, secondary in (("primary", False), ("secondary", True)):
        for model in b[2]["models"]:
            metrics = r[name]["models"][f'{model["seed"]}-{model["arm"]}']
            for endpoint, actual in metrics.items():
                total = hits = Fraction(0)
                for ref, pred, image in zip(b[3]["rows"], model["rows"], b[1]["rows"]):
                    label = ref["tokens"][0].removeprefix("toy-")
                    if endpoint == "mucosal": eligible = label in ("erosion", "ulcer")
                    else: eligible = label == endpoint.split("_")[0]
                    if not eligible: continue
                    weight = Fraction(1, sum(p["image_sha256"] == image["image_sha256"] for p in b[1]["rows"])) if secondary else Fraction(1)
                    a = [Fraction(str(s)) > Fraction(str(t)) for s, t in zip(pred["scores"], model["thresholds"])]
                    alert = any(a) if endpoint.endswith("_any") else a[0 if endpoint in ("vascular", "normal_vascular") else 1]
                    total += weight; hits += weight * alert
                assert actual["support"] == str(total) and actual["hits"] == str(hits)
                assert actual["rate"] == (str(hits / total) if total else None)
    # Joins are by exact key, not row positions, and arithmetic is deterministic.
    b[1]["rows"].reverse(); b[3]["rows"].reverse(); b[2]["models"].reverse()
    for model in b[2]["models"]: model["rows"].reverse()
    reordered = run(b)
    assert {k: v for k, v in r.items() if k != "contract_sha256"} == {
        k: v for k, v in reordered.items() if k != "contract_sha256"}


@pytest.mark.parametrize("rescue", [False, True])
def test_secondary_never_vetoes_or_rescues(rescue):
    b = controls()
    for m in b[2]["models"]:
        if m["arm"] == "detector":
            m["rows"][6]["scores"][0] = 0.9
    # Repeat either the alerting or the clean normal. Source group weight stays one.
    for i in range(20):
        duplicate(b, 6 if rescue else 7, f"normal-copy-{i}")
    r = run(b)
    assert r["secondary"]["criteria"]["H4"] is False
    assert r["verdict"] == ("NOT MET" if rescue else "MET")
    if not rescue:
        assert r["primary"]["models"]["19-detector"]["normal_any"]["rate"] == "1/22"


def test_secondary_cannot_rescue_primary_failure():
    b = controls()
    # Twenty normal images: one alert plus nineteen clean. Repeat the alert.
    for i in range(18):
        p = {"row_id": f"extra-{i}", "member": f"generated/extra-{i}.jpg", "image_sha256": h(("normal", i))}
        b[1]["rows"].append(p)
        b[3]["rows"].append({"row_id": p["row_id"], "image_sha256": p["image_sha256"], "tokens": ["toy-normal"]})
        for m in b[2]["models"]:
            m["rows"].append({"row_id": p["row_id"], "scores": [0.1, 0.1]})
    for m in b[2]["models"]:
        if m["arm"] == "detector":
            m["rows"][6]["scores"][0] = 0.9
    assert run(b)["primary"]["models"]["19-detector"]["normal_any"]["rate"] == "1/20"
    assert run(b)["primary"]["criteria"]["H4"] is True  # Inclusive exact 5% bound.
    duplicate(b, 6, "repeat-alert")
    r = run(b)
    assert r["primary"]["criteria"]["H4"] is False
    assert r["secondary"]["criteria"]["H4"] is True
    assert r["verdict"] == "NOT MET"


def test_exact_ten_percentage_point_boundary_without_rounding():
    b = controls()
    # Ten unique examples of each positive subtype; generated identities only.
    for source in (0, 2, 4):
        for i in range(8):
            duplicate(b, source, f"distinct-{source}-{i}")
            image = h((source, i, "distinct"))
            b[1]["rows"][-1]["image_sha256"] = image
            b[3]["rows"][-1]["image_sha256"] = image
    for m in b[2]["models"]:
        if m["arm"] == "classifier":
            seen = {"toy-vascular": 0, "toy-erosion": 0, "toy-ulcer": 0}
            for row, ref in zip(m["rows"], b[3]["rows"]):
                token = ref["tokens"][0]
                if token in seen:
                    seen[token] += 1
                    row["scores"][0 if token == "toy-vascular" else 1] = 0.9 if seen[token] <= 9 else 0.1
    r = run(b)
    assert r["primary"]["mean_paired_differences"]["vascular"] == "1/10"
    assert r["primary"]["mean_paired_differences"]["mucosal"] == "1/10"
    assert r["verdict"] == "MET"
    for m in b[2]["models"]:
        if m["arm"] == "classifier":
            m["rows"][0]["scores"][0] = 0.9
            # Find the sole missed vascular row without reading any real data.
            for row, ref in zip(m["rows"], b[3]["rows"]):
                if ref["tokens"] == ["toy-vascular"]:
                    row["scores"][0] = 0.9
    assert run(b)["primary"]["criteria"]["H1"] is False


@pytest.mark.parametrize("tokens", [["toy-unknown"], ["toy-ulcer"], ["toy-normal"]])
def test_m5_eligibility_conflicts_precede_not_met(tokens):
    b = controls()
    duplicate(b, 2, "conflict")
    b[3]["rows"][-1]["tokens"] = tokens
    # Known erosion versus unknown/ulcer/normal changes a required eligibility.
    for m in b[2]["models"]:
        if m["arm"] == "detector":
            m["rows"][0]["scores"] = [0.1, 0.1]
            m["rows"][1]["scores"] = [0.1, 0.1]
    r = run(b)
    assert r["primary"]["criteria"]["H1"] is False
    assert r["verdict"] == "INCONCLUSIVE" and r["conflicting_groups"] == 1
    assert r["primary"]["total_weight"] == "11"  # No reference-dependent deletions.


def test_reference_difference_without_safeguard_eligibility_difference_is_not_veto():
    b = controls()
    duplicate(b, 8, "unassessed-copy")
    b[3]["rows"][-1]["tokens"] = ["toy-unknown"]
    r = run(b)
    assert r["verdict"] == "MET" and r["conflicting_groups"] == 0


def test_explicit_dual_target_and_repeated_raw_target_mapping():
    b = controls()
    b[0]["mapping"]["toy-dual"] = ["vascular", "erosion"]
    b[3]["rows"][0]["tokens"] = ["toy-dual", "toy-vascular"]
    r = run(b)
    # Union of explicit references, not repeated-class counting.
    assert r["primary"]["models"]["19-detector"]["erosion"]["rows"] == 3
    assert r["primary"]["models"]["19-detector"]["vascular"]["rows"] == 2


def test_individual_erosion_loss_does_not_veto_nonnegative_mean():
    b = controls()
    for m in b[2]["models"]:
        if m["seed"] == 19:
            if m["arm"] == "classifier":
                m["rows"][2]["scores"][1] = m["rows"][3]["scores"][1] = 0.9
            else:
                m["rows"][2]["scores"][1] = 0.1
    r = run(b)
    assert r["verdict"] == "MET"
    assert r["primary"]["paired_differences"]["erosion"]["19"] == "-1/2"
    assert r["primary"]["mean_paired_differences"]["erosion"] == "1/2"
    assert r["primary"]["individual_erosion_losses"] == ["19"]


@pytest.mark.parametrize("seed", [19, 37, 73])
def test_every_paired_seed_must_improve(seed):
    b = controls()
    for m in b[2]["models"]:
        if m["seed"] == seed and m["arm"] == "detector":
            for row in m["rows"][:2]:
                row["scores"][0] = 0.5
    r = run(b)
    assert r["primary"]["criteria"]["H1"] is True
    assert r["primary"]["criteria"]["H3"] is False and r["verdict"] == "NOT MET"


@pytest.mark.parametrize("label,required", [("erosion", True), ("normal", True), ("vascular", True), ("ulcer", False)])
def test_zero_support_is_na_never_imputed(label, required):
    b = controls()
    for row in b[3]["rows"]:
        if row["tokens"] == [f"toy-{label}"]:
            row["tokens"] = ["toy-unknown"]
    r = run(b)
    metric = "normal_any" if label == "normal" else label
    assert r["primary"]["models"]["19-detector"][metric]["rate"] is None
    assert r["verdict"] == ("INCONCLUSIVE" if required else "MET")


@pytest.mark.parametrize("failure", ["missing-model", "incomplete", "updates", "schedule"])
def test_incomplete_precedes_failed_assessable_safeguard(failure):
    b = controls()
    for m in b[2]["models"]:
        if m["arm"] == "detector":
            m["rows"][6]["scores"][0] = 0.9  # H4 fails even when H1 is unassessable.
    if failure == "missing-model":
        b[2]["models"].pop(0)
    elif failure == "incomplete":
        b[2]["models"][0]["complete"] = False
    elif failure == "updates":
        b[2]["models"][0]["updates"] = 512
    else:
        b[2]["models"][0]["checkpoint_epochs"] = [20]
    r = run(b)
    assert r["primary"]["criteria"]["H4"] is False and r["verdict"] == "INCONCLUSIVE"


@pytest.mark.parametrize("problem", ["missing-reference", "extra-reference", "duplicate-reference", "image-join",
    "unmapped", "empty-tokens", "normal-positive", "missing-prediction", "duplicate-prediction", "duplicate-model",
    "wrong-model", "threshold-change", "method-change", "duplicate-scores", "member-traversal", "member-case",
    "duplicate-id", "bad-hash", "wrong-version", "wrong-schema", "bool-seed", "bool-score", "out-of-range"])
def test_fail_closed_input_schemas(problem):
    b = controls()
    if problem == "missing-reference": b[3]["rows"].pop()
    elif problem == "extra-reference":
        row = copy.deepcopy(b[3]["rows"][0]); row["row_id"] = "extra"; b[3]["rows"].append(row)
    elif problem == "duplicate-reference": b[3]["rows"].append(b[3]["rows"][0])
    elif problem == "image-join": b[3]["rows"][0]["image_sha256"] = h("wrong")
    elif problem == "unmapped": b[3]["rows"][0]["tokens"] = ["not-approved"]
    elif problem == "empty-tokens": b[3]["rows"][0]["tokens"] = []
    elif problem == "normal-positive": b[3]["rows"][0]["tokens"] = ["toy-normal", "toy-vascular"]
    elif problem == "missing-prediction": b[2]["models"][0]["rows"].pop()
    elif problem == "duplicate-prediction": b[2]["models"][0]["rows"].append(b[2]["models"][0]["rows"][0])
    elif problem == "duplicate-model": b[2]["models"].append(b[2]["models"][0])
    elif problem == "wrong-model": b[2]["models"][0]["checkpoint_sha256"] = h("other")
    elif problem == "threshold-change": b[2]["models"][0]["thresholds"] = [0, 0]
    elif problem == "method-change": b[2]["method_sha256"] = h("other")
    elif problem == "duplicate-scores":
        duplicate(b, 0, "inconsistent-copy"); b[2]["models"][0]["rows"][-1]["scores"] = [0.8, 0.8]
    elif problem == "member-traversal": b[1]["rows"][0]["member"] = "../outside.jpg"
    elif problem == "member-case": b[1]["rows"][1]["member"] = b[1]["rows"][0]["member"].upper()
    elif problem == "duplicate-id": b[1]["rows"][1]["row_id"] = b[1]["rows"][0]["row_id"].upper()
    elif problem == "bad-hash": b[1]["rows"][0]["image_sha256"] = "abc"
    elif problem == "wrong-version": b[3]["version"] = "another-reference-version"
    elif problem == "wrong-schema": b[1]["schema"] = "v2"
    elif problem == "bool-seed": b[2]["models"][0]["seed"] = True
    elif problem == "bool-score": b[2]["models"][0]["rows"][0]["scores"] = [True, 0]
    else: b[2]["models"][0]["rows"][0]["scores"] = [1.01, 0]
    r = run(b)
    assert r["verdict"] == "INCONCLUSIVE" and r["reasons"] and "primary" not in r


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_json_scores_rejected(value):
    b = controls(); b[2]["models"][0]["rows"][0]["scores"][0] = value
    assert run(b)["verdict"] == "INCONCLUSIVE"


@pytest.mark.parametrize("case", ["score", "threshold", "tie", "equivalent-tie"])
def test_extreme_decimal_comparisons_are_resource_bounded(case):
    import subprocess
    import sys
    import time
    if sys.platform != "linux":
        pytest.skip("Linux RLIMIT_AS/CPU regression; never run hostile conversion unbounded")
    pytest.importorskip("resource")
    args = list(packed(controls()))
    tiny = b"1e-1000000000"
    if case != "threshold":
        args[3] = args[3].replace(b'"scores":[0.5,0.5]', b'"scores":[' + tiny + b',0.5]', 1)
    if case != "score":
        threshold = b"10e-1000000001" if case == "equivalent-tie" else tiny
        args[3] = args[3].replace(b'"thresholds":[0.5,0.5]',
                                b'"thresholds":[' + threshold + b',0.5]', 1)
    contract = json.loads(args[0])
    contract["predictions_sha256"] = sha256(args[3]).hexdigest()
    args[0] = raw(contract)
    if case != "score":
        args[0] = args[0].replace(b'"thresholds":[0.5,0.5]',
                                b'"thresholds":[' + threshold + b',0.5]', 1)
    args[1] = sha256(args[0]).hexdigest()
    # Inner JSON remains bytes encoded as outer strings: no float underflow in
    # the fixture builder. Import/evaluation both run behind hard Linux limits.
    child = """
import json, resource, sys
resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024,) * 2)
resource.setrlimit(resource.RLIMIT_CPU, (2, 2))
from capsule_review.spatial_external import evaluate
args = [v if i == 1 else v.encode() for i, v in enumerate(json.load(sys.stdin))]
print(json.dumps(evaluate(*args), sort_keys=True))
"""
    payload = json.dumps([a.decode() if type(a) is bytes else a for a in args])
    started = time.monotonic()
    command = [sys.executable, "-I"] + (["-O"] if sys.flags.optimize else [])
    result = subprocess.run(command + ["-c", child], input=payload,
                            capture_output=True, text=True, timeout=5)
    elapsed = time.monotonic() - started
    assert result.returncode == 0, (result.returncode, result.stderr)
    report = json.loads(result.stdout)
    # Independent strict Decimal ordering: 0.5 > tiny; tiny == 10e-(N+1).
    expected_rate = {"score": "0", "threshold": "1", "tie": "1/2", "equivalent-tie": "1/2"}[case]
    assert report["primary"]["models"]["19-classifier"]["vascular"]["rate"] == expected_rate
    assert report["verdict"] == ("NOT MET" if case == "threshold" else "MET")
    print(f"bounded generated {case}: {elapsed:.3f}s, exit 0, {report['verdict']}")


def test_equivalent_decimal_spellings_preserve_exact_results():
    b = controls()
    for model in b[2]["models"]:
        model["rows"][0]["scores"][0] = 0.5
    args = list(packed(b))
    args[3] = args[3].replace(b'"scores":[0.5,', b'"scores":[5e-1,', 1)
    c = json.loads(args[0]); c["predictions_sha256"] = sha256(args[3]).hexdigest()
    args[0] = raw(c).replace(b'"thresholds":[0.5,0.5]', b'"thresholds":[0.5000,0.50]', 1)
    args[1] = sha256(args[0]).hexdigest()
    report = evaluate(*args)
    baseline = run(b)
    assert {k: v for k, v in report.items() if k != "contract_sha256"} == {
        k: v for k, v in baseline.items() if k != "contract_sha256"}


@pytest.mark.parametrize("index", [0, 2, 3, 4])
def test_exact_byte_hashes_are_not_self_repaired(index):
    args = list(packed(controls())); args[index] += b" "
    r = evaluate(*args)
    assert r["verdict"] == "INCONCLUSIVE" and "primary" not in r


def test_duplicate_json_fields_and_bad_hash_anchor():
    args = list(packed(controls()))
    args[0] = args[0].replace(b'{', b'{"policy":"hidden",', 1)
    args[1] = sha256(args[0]).hexdigest()
    assert evaluate(*args)["verdict"] == "INCONCLUSIVE"


@pytest.mark.parametrize("problem", ["extra-field", "bad-model-hash", "missing-committed-model",
    "unselected-policy", "empty-mapping", "bad-canonical-state", "bad-population-count", "surrogate-token"])
def test_contract_is_bounded_and_self_validating(problem):
    args = list(packed(controls())); c = json.loads(args[0])
    if problem == "extra-field": c["unexpected"] = True
    elif problem == "bad-model-hash": c["models"][0]["selection_sha256"] = "short"
    elif problem == "missing-committed-model": c["models"].pop()
    elif problem == "unselected-policy": c["policy"] = "M1B"
    elif problem == "empty-mapping": c["mapping"] = {}
    elif problem == "bad-canonical-state": c["mapping"]["toy-vascular"] = ["invented"]
    elif problem == "bad-population-count": c["population"]["rows"] = 9
    else: c["mapping"]["\ud800"] = ["unknown"]
    args[0] = raw(c); args[1] = sha256(args[0]).hexdigest()
    assert evaluate(*args)["verdict"] == "INCONCLUSIVE"
    args = list(packed(controls())); args[1] = "not-a-digest"
    assert evaluate(*args)["verdict"] == "INCONCLUSIVE"


def test_reserved_population_cannot_be_silently_replaced_by_toy_population():
    b = controls(); b[0]["scope"] = "reserved-aiims"
    assert run(b)["verdict"] == "INCONCLUSIVE"


def test_no_file_network_or_training_channel(monkeypatch):
    import ast
    import builtins
    from pathlib import Path
    import socket
    import subprocess
    import sys
    import capsule_review.spatial_external as module
    root = Path(module.__file__).parent
    for name in ("spatial_training.py", "spatial_data.py", "spatial_executor.py"):
        tree = ast.parse((root / name).read_text())
        assert not any(isinstance(n, ast.ImportFrom) and n.module and "spatial_external" in n.module
                       for n in ast.walk(tree))
    args = packed(controls())
    def forbidden(*a, **k):
        raise AssertionError("Unexpected external I/O")
    with monkeypatch.context() as m:
        m.setattr(builtins, "open", forbidden)
        m.setattr(socket, "socket", forbidden)
        assert evaluate(*args)["verdict"] == "MET"
    # The arithmetic engine has no Torch import or model/training dependency.
    assert not any(k.startswith("torch") for k in module.__dict__)
    fresh = subprocess.run([sys.executable, "-I", "-c",
        "import sys; import capsule_review.spatial_external; "
        "assert 'torch' not in sys.modules; "
        "assert 'capsule_review.spatial_training' not in sys.modules"], capture_output=True)
    assert fresh.returncode == 0, fresh.stderr
