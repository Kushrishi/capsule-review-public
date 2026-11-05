"""Conservative, metadata-only admission gate for a *future* external VCE study.

A positive result means "ready for independent human review", never that the
dataset is approved, clinically labelled or independent. There is no clinical
data access, implicit online lookup or medical inference in this module.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

REQUIRED = (
    "research_use_permission",
    "independent_patient_exam_grouping",
    "complete_source_chronology",
    "exhaustive_target_annotation",
    "clinician_approved_label_mapping",
    "source_integrity_and_duplicates",
    "native_frame_run_definition",
    "private_durable_storage",
    "prespecified_sample_size",
    "outcome_concealment_plan",
)
STATES = ("pass", "fail", "unknown")
MAX_NOTE = 800


@dataclass(frozen=True)
class GateResult:
    decision: str
    issues: tuple[dict[str, str], ...]
    passed: int
    total: int

    def public_summary(self) -> dict:
        # Deliberately exclude evidence refs, patient identifiers and source
        # details: CLI may display this output in a shared terminal.
        return {
            "decision": self.decision,
            "passed": self.passed,
            "total": self.total,
            "issues": list(self.issues),
            "approved_for_outcome_access": False,
            "clinical_validation": False,
        }


def assess(candidate: Any) -> GateResult:
    """Validate a human-authored gate worksheet; never certify its truth.

    Each required check has status 'pass'|'fail'|'unknown', a short public-safe
    explanation and an evidence reference. A pass requires a reference, but
    this program cannot independently authenticate a custodian or expert.
    Missing checks are UNKNOWN and block progression; unrecognized keys fail
    closed so a misspelled field cannot masquerade as a verification.
    """
    if not isinstance(candidate, dict) or candidate.get("schema_version") != 1:
        raise ValueError("Expected cohort admission worksheet schema_version=1.")
    name = candidate.get("candidate")
    if not isinstance(name, str) or not 0 < len(name.strip()) <= 128:
        raise ValueError("A short candidate dataset name is required.")
    checks = candidate.get("checks")
    if not isinstance(checks, dict):
        raise ValueError("checks must be a keyed object.")
    if set(checks) - set(REQUIRED):
        raise ValueError("Unrecognized gate key; correct the name instead of ignoring it.")

    problems: list[dict[str, str]] = []
    passed = 0
    for key in REQUIRED:
        item = checks.get(key)
        if item is None:
            problems.append({"check": key, "status": "unknown", "reason": "Not supplied"})
            continue
        if not isinstance(item, dict) or set(item) - {"status", "reason", "evidence_ref"}:
            raise ValueError(f"Invalid gate record: {key}")
        status = item.get("status")
        if status not in STATES or not isinstance(status, str):
            raise ValueError(f"Invalid gate status: {key}")
        reason = item.get("reason", "")
        evidence = item.get("evidence_ref", "")
        if not isinstance(reason, str) or len(reason) > MAX_NOTE:
            raise ValueError(f"Invalid or oversized public reason: {key}")
        if not isinstance(evidence, str) or len(evidence) > 1024:
            raise ValueError(f"Invalid evidence reference: {key}")
        if status == "pass" and not evidence.strip():
            problems.append({"check": key, "status": "unknown", "reason": "Pass lacks evidence reference"})
        elif status == "pass":
            passed += 1
        else:
            problems.append({
                "check": key,
                "status": status,
                # Reasons are supplied by a human; callers MUST only use
                # non-identifying, shareable text in these fields.
                "reason": reason or ("Evidence incomplete" if status == "unknown" else "Failed"),
            })

    decision = "HUMAN_REVIEW_REQUIRED" if not problems else "BLOCKED"
    return GateResult(decision=decision, issues=tuple(problems),
                      passed=passed, total=len(REQUIRED))
