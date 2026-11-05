# Working on Capsule Review

Capsule Review is a **local research viewer** for capsule-endoscopy image sequences. Work in this public source-only repository. Keep the historical `Kushrishi/capsule-review` archive, original images, individual labels/predictions, weights and private research packages private.

## Read first (in this order)

- [README](README.md): short product entry point and run commands.
- [Current project status](docs/PROJECT_STATUS.md): the canonical software/research state and where to find evidence.
- [Adaptive roadmap](docs/ROADMAP.md): next scientific tasks, data gates and go/no-go criteria.
- [Verified selected-source audit](docs/GALAR_DEVELOPMENT_SOURCE_AUDIT_20261105.md): all 11,147 existing original image bytes checked; patient-group and complete-event claims still blocked.
- [Group/fold readiness](docs/GALAR_GROUP_AND_FOLD_READINESS_20261105.md): source uniform reference metrics, video-vs-patient separation and partial device metadata.
- [Research protocol](docs/RESEARCH_PROTOCOL.md): clinical terminology, data separation, and evaluation limits.
- [Research review queue](docs/RESEARCH_REVIEW_QUEUE.md): the four previously evaluated exact-K policies and one explicitly experimental bounded-gap candidate.
- [Locked evaluation design](docs/GALAR_UNSEEN_EVALUATION_PLAN.md) and [completed results](docs/GALAR_UNSEEN_11_20_RESULTS.md): original checkpoint, outcome-concealed eligibility amendment and Galar 11–20 findings.
- [Release boundary](docs/PUBLIC_RELEASE_SAFETY.md): data/CI restrictions.
- `docs/*RESULTS.md`, `experiments/`: original experimental records, including negative outcomes.

Historical results are evidence, not instructions to create new findings. Do not rewrite or remove frozen protocols, provenance, aggregate data or failures to simplify documentation.

## Non-negotiable scientific boundaries

1. **No clinical claims without corresponding evidence.** `blood=1` is a frame annotation, not a unique lesion, diagnosis, calibrated clinical probability, or reading-time benefit. Neither model accuracy nor image coverage proves patient safety.
2. **Maintain examination separation.** Galar 1–8 trained the original blood CNN; 9–10 were previously inspected. Examinations 21/23/25/27/29/30 supported exploratory model transfer. The locked 11–20 evaluation is now complete under amendment A1: its primary 10% comparison did not demonstrate improvement. Do not tune on these results and call 11–20 untouched or newly independent. The authors' reserved 61–80 remains unopened. A previous ZIP-wide CRC-only integrity traversal is documented; do not repeat it.
3. **No artificial coverage.** Missing labels are unknown, not negative. Source image ID gaps are not elapsed time. Sampled 512-image references are not dense complete video. At a fixed review count, report actual distinct annotated runs reached, not just positive sampled images.
4. **Preserve the human workflow.** Reviewer notes, source labels, model suggestions and exports stay distinct. Model navigation does not save findings or conceal unselected images. The viewer permits any exact K from 1 to all imported images; 10% is a research operating point, not a product cap.
5. **Preserve independent evaluation.** Before accessing any untouched source label or image, lock the model, preprocessing, source identities, selection policies, workloads, evaluation set and metrics. Do not retune against examined failures and call the next result independent. No model is currently promoted for clinical use.

## Engineering boundaries

- Keep the application local. No hosted patient-data service, network exposure, automatic data upload or private source acquisition in public CI.
- Public Git must contain only code, synthetic tests, non-identifying aggregates and explanatory documents. Run `python scripts/verify_public_source_boundary.py`; it is a precaution, not a complete secrets or history audit.
- Before merging: use a narrowly scoped branch/PR; run core tests on Python 3.11–3.13, browser/local-model smoke and the privacy workflow. State any unrun checks.
- Prefer small, readable changes, predictable interfaces and simple navigation. Read the status and roadmap before starting new experiments. Update the canonical guide only when a meaningful status/gate changes; link to detailed immutable historical reports instead of copying chronology into the README.
- Do not invent a code licence, publish a model checkpoint, alter source licensing, or make claims about clinical novelty, external validation or publication readiness.

**Current scientific record:** [issue #24](https://github.com/Kushrishi/capsule-review-public/issues/24) and the [locked results](docs/GALAR_UNSEEN_11_20_RESULTS.md) contain the completed full-source comparison, external prediction commitment and all negative findings. No model is promoted. Any new independent evaluation requires a new prespecified protocol; leave authors' 61–80 closed.
