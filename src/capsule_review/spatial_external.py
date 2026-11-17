"""Offline CR-SP-01 M1A–M5A arithmetic, separate from training/inference.

All inputs are UTF-8 JSON bytes. ``evaluate`` requires an independently trusted
contract digest; matching self-supplied hashes alone proves no custody, approval,
model execution or seal. No file/network/model access occurs in this module.
The generated tests define the v1 wire schema. Real raw tokens, row joins,
reference version and six-fit attestations must be independently reviewed and
sealed before use. No actual AIIMS vocabulary is assumed here.
"""
from collections import Counter
from decimal import Decimal
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import PurePosixPath
import re
import unicodedata

SEEDS = (19, 37, 73)
ARMS = ("classifier", "detector")
KINDS = {"vascular", "erosion", "ulcer", "normal", "other", "unknown"}
ENDPOINTS = ("vascular", "mucosal", "erosion", "ulcer",
             "normal_vascular", "normal_mucosal", "normal_any", "other_any", "unknown_any")
POLICY = "CR-SP-01-M1A-M2A-M3A-M4A-M5A"


class Invalid(ValueError):
    """An untrusted input cannot support a research verdict."""


def require(condition, message):
    if not condition:
        raise Invalid(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def _json(raw):
    require(type(raw) is bytes, "Expected JSON bytes")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=Decimal, parse_constant=lambda _: _bad_number())
    except (UnicodeError, ValueError, RecursionError) as error:
        raise Invalid("Invalid JSON input") from error


def _bad_number():
    raise Invalid("Nonfinite number")


def _object(value, keys):
    require(type(value) is dict and set(value) == set(keys.split()), "Unexpected schema fields")


def _list(value):
    require(type(value) is list, "Expected array")
    return value


def _hash(value):
    require(type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value), "Invalid SHA-256")
    return value


def _text(value):
    require(type(value) is str and 0 < len(value) <= 256
            and value == value.strip() and value.isprintable(), "Invalid token")
    return value


def _id(value):
    require(type(value) is str and re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value), "Invalid row key")
    return value


def _prob(value):
    require(type(value) in (int, Decimal) and 0 <= value <= 1, "Invalid probability")
    # Comparisons are exact without expanding compact Decimal exponents into
    # huge integer denominators. Fractions are only needed for metric counts.
    return value


def _scores(value):
    require(type(value) is list and len(value) == 2, "Expected vascular/mucosal score pair")
    return tuple(_prob(v) for v in value)


def _schema(doc, version, keys):
    _object(doc, "schema " + keys)
    require(doc["schema"] == "cr-sp01-" + version + "-v1", "Unsupported schema version")


def _key(model):
    require(type(model["seed"]) is int and model["seed"] in SEEDS
            and model["arm"] in ARMS, "Unexpected arm or seed")
    return model["seed"], model["arm"]


def _model_identity(model):
    key = _key(model)
    for field in ("checkpoint_sha256", "selection_sha256"):
        _hash(model[field])
    return key, _scores(model["thresholds"])


def _indexed(rows, keys):
    indexed, folded = {}, set()
    for row in _list(rows):
        _object(row, keys)
        ident = _id(row["row_id"])
        require(ident.casefold() not in folded, "Duplicate or ambiguous row key")
        folded.add(ident.casefold())
        indexed[ident] = row
    return indexed


def _contract(doc):
    _schema(doc, "contract", "policy scope population archive_sha256 population_sha256 "
            "predictions_sha256 references_sha256 reference_version mapping models "
            "six_selection_sha256 method_sha256 analysis_sha256")
    require(doc["policy"] == POLICY, "Unselected analysis policy")
    require(doc["scope"] in ("generated-control", "reserved-aiims"), "Invalid population scope")
    _object(doc["population"], "rows groups")
    rows, groups = doc["population"]["rows"], doc["population"]["groups"]
    require(type(rows) is int and type(groups) is int and 0 < groups <= rows, "Invalid population size")
    if doc["scope"] == "reserved-aiims":
        require((rows, groups) == (4385, 4377), "Changed reserved population")
        require(doc["archive_sha256"] ==
                "cab4b4f73786734b1805ec34c371379f6f0e9324213ea0b5f2e91c8c799896db",
                "Changed reserved archive")
    for field in ("archive_sha256", "population_sha256", "predictions_sha256", "references_sha256",
                  "six_selection_sha256", "method_sha256", "analysis_sha256"):
        _hash(doc[field])
    _text(doc["reference_version"])
    mapping = doc["mapping"]
    require(type(mapping) is dict and 0 < len(mapping) <= 32, "Invalid bounded token mapping")
    for token, kinds in mapping.items():
        _text(token)
        _list(kinds)
        require(bool(kinds) and all(type(k) is str and k in KINDS for k in kinds)
                and len(kinds) == len(set(kinds)), "Invalid canonical mapping")
        _reference_state(kinds)
    expected = {}
    for model in _list(doc["models"]):
        _object(model, "seed arm checkpoint_sha256 selection_sha256 thresholds")
        key, _ = _model_identity(model)
        require(key not in expected, "Duplicate committed model")
        expected[key] = model
    require(set(expected) == {(s, a) for s in SEEDS for a in ARMS}, "Incomplete committed model set")
    return expected


def _reference_state(kinds):
    state = frozenset(kinds)
    require(not ("normal" in state and state != {"normal"}), "Contradictory Normal reference")
    require(not ("unknown" in state and state != {"unknown"}), "Contradictory unknown reference")
    return state


def _population(doc, contract):
    _schema(doc, "population", "archive_sha256 rows")
    require(doc["archive_sha256"] == contract["archive_sha256"], "Archive identity differs")
    rows = _indexed(doc["rows"], "row_id member image_sha256")
    members = set()
    for row in rows.values():
        member = _text(row["member"])
        path = PurePosixPath(member)
        folded = unicodedata.normalize("NFKC", member).casefold()
        require(not path.is_absolute() and ".." not in path.parts and "\\" not in member
                and str(path) == member and member != "." and folded not in members,
                "Ambiguous archive member")
        members.add(folded)
        _hash(row["image_sha256"])
    counts = Counter(r["image_sha256"] for r in rows.values())
    require(len(rows) == contract["population"]["rows"]
            and len(counts) == contract["population"]["groups"], "Population membership size differs")
    return rows, counts


def _references(doc, contract, population):
    _schema(doc, "references", "version rows")
    require(doc["version"] == contract["reference_version"], "Reference version differs")
    rows = _indexed(doc["rows"], "row_id image_sha256 tokens")
    require(rows.keys() == population.keys(), "Reference row join differs")
    states = {}
    for ident, row in rows.items():
        require(row["image_sha256"] == population[ident]["image_sha256"], "Reference image join differs")
        tokens = _list(row["tokens"])
        require(bool(tokens) and all(type(t) is str and t in contract["mapping"] for t in tokens)
                and len(tokens) == len(set(tokens)), "Unmapped or ambiguous reference token")
        states[ident] = _reference_state(k for t in tokens for k in contract["mapping"][t])
    return states


def _eligibility(state):
    return ("vascular" in state, bool(state & {"erosion", "ulcer"}),
            "erosion" in state, "normal" in state)


def _models(doc, contract, expected, population):
    _schema(doc, "predictions", "six_selection_sha256 method_sha256 models")
    for field in ("six_selection_sha256", "method_sha256"):
        require(doc[field] == contract[field], "Prediction method/selection commitment differs")
    models, reasons = {}, []
    for model in _list(doc["models"]):
        _object(model, "seed arm checkpoint_sha256 selection_sha256 thresholds complete updates checkpoint_epochs rows")
        key, thresholds = _model_identity(model)
        require(key not in models, "Duplicate predicted model")
        for field in ("checkpoint_sha256", "selection_sha256"):
            require(model[field] == expected[key][field], "Model identity differs")
        require(thresholds == _scores(expected[key]["thresholds"]), "Threshold commitment differs")
        require(type(model["complete"]) is bool and type(model["updates"]) is int
                and type(model["checkpoint_epochs"]) is list
                and all(type(e) is int for e in model["checkpoint_epochs"]), "Invalid completion evidence")
        if not model["complete"] or model["updates"] != 14180 or model["checkpoint_epochs"] != [4, 8, 12, 16, 20]:
            reasons.append("Incomplete fit evidence")
        rows = _indexed(model["rows"], "row_id scores")
        require(rows.keys() == population.keys(), "Prediction row join differs")
        scores, by_image = {}, {}
        for ident, row in rows.items():
            scores[ident] = _scores(row["scores"])
            image = population[ident]["image_sha256"]
            require(image not in by_image or by_image[image] == scores[ident], "Identical-image scores differ")
            by_image[image] = scores[ident]
        models[key] = {ident: tuple(s > t for s, t in zip(pair, thresholds))
                       for ident, pair in scores.items()}
    if models.keys() != expected.keys():
        reasons.append("Incomplete six-model prediction set")
    return models, reasons


def _metric(eligible, alerts, weights, population):
    support = sum((weights[i] for i in eligible), Fraction())
    hits = sum((weights[i] for i in eligible if alerts[i]), Fraction())
    return {"hits": str(hits), "support": str(support),
            "rate": str(hits / support) if support else None, "rows": len(eligible),
            "groups": len({population[i]["image_sha256"] for i in eligible})}


def _analysis(population, counts, states, models, secondary):
    weights = {i: Fraction(1, counts[r["image_sha256"]] if secondary else 1)
               for i, r in population.items()}
    sets = {name: {i for i, st in states.items() if name in st}
            for name in ("vascular", "erosion", "ulcer", "normal", "other", "unknown")}
    sets["mucosal"] = sets["erosion"] | sets["ulcer"]
    results = {}
    for (seed, arm), decisions in sorted(models.items()):
        metrics = {}
        for endpoint in ENDPOINTS:
            subset = endpoint.split("_")[0]
            if endpoint in ("vascular", "erosion", "ulcer", "mucosal"):
                target = 0 if endpoint == "vascular" else 1
                alerts = {i: a[target] for i, a in decisions.items()}
            else:
                which = endpoint.split("_")[1]
                alerts = {i: any(a) if which == "any" else a[0 if which == "vascular" else 1]
                          for i, a in decisions.items()}
            metrics[endpoint] = _metric(sets[subset], alerts, weights, population)
        results[f"{seed}-{arm}"] = metrics
    differences, means = {}, {}
    for target in ("vascular", "mucosal", "erosion", "ulcer"):
        differences[target] = {}
        for seed in SEEDS:
            rates = [results.get(f"{seed}-{a}", {}).get(target, {}).get("rate") for a in ARMS]
            differences[target][str(seed)] = (str(Fraction(rates[1]) - Fraction(rates[0]))
                                              if all(r is not None for r in rates) else None)
        values = list(differences[target].values())
        means[target] = str(sum(map(Fraction, values), Fraction()) / 3) if all(v is not None for v in values) else None
    criteria = {
        "H1": all(Fraction(means[t]) >= Fraction(1, 10) for t in ("vascular", "mucosal"))
        if all(means[t] is not None for t in ("vascular", "mucosal")) else None,
        "H2": Fraction(means["erosion"]) >= 0 if means["erosion"] is not None else None,
        "H3": all(Fraction(v) > 0 for t in ("vascular", "mucosal") for v in differences[t].values())
        if all(v is not None for t in ("vascular", "mucosal") for v in differences[t].values()) else None,
        "H4": all(Fraction(results[f"{s}-detector"]["normal_any"]["rate"]) <= Fraction(1, 20) for s in SEEDS)
        if all(results.get(f"{s}-detector", {}).get("normal_any", {}).get("rate") is not None for s in SEEDS) else None,
    }
    return {"total_weight": str(sum(weights.values(), Fraction())), "models": results,
            "paired_differences": differences, "mean_paired_differences": means,
            "individual_erosion_losses": [s for s, v in differences["erosion"].items()
                                          if v is not None and Fraction(v) < 0],
            "criteria": criteria}


def evaluate(contract_raw, expected_contract_sha256, population_raw, predictions_raw, references_raw):
    """Compute aggregate M1A–M5A results or INCONCLUSIVE; never calibrate a model.

    Input hashes bind exact bytes, not reserialized objects. The caller must
    obtain ``expected_contract_sha256`` from independent approved custody.
    Completion fields are sealed attestations, not checkpoint execution proof;
    upstream verification of the six actual selection seals remains mandatory.
    ``generated-control`` results cannot be reported as reserved-AIIMS results.
    """
    report = {"schema": "cr-sp01-report-v1", "policy": POLICY, "verdict": "INCONCLUSIVE"}
    try:
        _hash(expected_contract_sha256)
        require(type(contract_raw) is bytes and sha256(contract_raw).hexdigest() == expected_contract_sha256,
                "Analysis contract digest differs")
        contract = _json(contract_raw)
        expected = _contract(contract)
        for raw, field in ((population_raw, "population_sha256"), (predictions_raw, "predictions_sha256"),
                           (references_raw, "references_sha256")):
            require(type(raw) is bytes and sha256(raw).hexdigest() == contract[field], "Input digest differs")
        population, counts = _population(_json(population_raw), contract)
        states = _references(_json(references_raw), contract, population)
        models, reasons = _models(_json(predictions_raw), contract, expected, population)
        vectors = {}
        for ident, state in states.items():
            vectors.setdefault(population[ident]["image_sha256"], set()).add(_eligibility(state))
        conflicts = sum(len(v) > 1 for v in vectors.values())
        if conflicts:
            reasons.append("Exact-image safeguard eligibility conflict")
        primary = _analysis(population, counts, states, models, False)
        secondary = _analysis(population, counts, states, models, True)
        if any(v is None for v in primary["criteria"].values()):
            reasons.append("Required safeguard support/evidence unavailable")
        report.update(scope=contract["scope"], contract_sha256=expected_contract_sha256,
                      primary=primary, secondary=secondary, conflicting_groups=conflicts,
                      reasons=sorted(set(reasons)))
        if not reasons:
            report["verdict"] = "MET" if all(primary["criteria"].values()) else "NOT MET"
    except (Invalid, TypeError, KeyError, ArithmeticError, RecursionError) as error:
        # No row keys, raw labels or private paths are echoed on invalid input.
        report["reasons"] = [str(error) if isinstance(error, Invalid) else "Malformed schema value"]
    return report
