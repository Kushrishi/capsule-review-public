# Privately connect verified original Galar CNN scores to the research review queue

**November 3, 2026 | Already examined research scores, NOT clinical validation**

## Purpose

The new Capsule Review browser queue works with a complete per-frame model score stream, but its built-in local model is an **anatomy classifier**, not pathology detection. The earlier, original experimental Galar blood-CNN research already has verified private per-image score files. This import tool connects those exact prior research scores to an existing local **original-image** Capsule Review study. The application can then prioritize those frames at any workload and navigate suggestions without changing human-authored notes.

It **does not train or execute** the historical CNN, bundle its checkpoints, discover independent data, publish original images, or establish clinical sensitivity. The scores are uncalibrated and all examinations here have already been inspected.

## Exact permitted private packages

Both the WHOLE archived ZIP and the one named score CSV must match hard-pinned SHA-256s. ZIP CRC is checked only on the intended named score member—never by traversing every entry. Permitted studies:

| Source | Previously examined examinations | Named score stream | Score column |
|---|---|---|---|
| frozen-transfer | 21, 23, 30 | private/source-scores.csv | cnn_score |
| appearance-audit | 25, 27, 29 | PRIVATE/private-per-image-features.csv | original_checkpoint |

The frozen-transfer stream uses only the already selected reference_uniform=1 rows; pathology-enriched fitting rows cannot be silently included. The appearance-audit stream contains precisely 512 chronological reference images per permitted examination. The source CSVs include individual clinical annotation columns, but these are **never used for ranking or written to model predictions**. The importer reads only the allowlisted exam, original source frame ID, source-image SHA-256, required reference role and numerical CNN score. It cannot be used on future evaluation examinations 11–20 or reserved author holdout 61–80.

## Use only in a private local study

First import **the exact previously source-verified 512 original reference images** for your selected fitting/transfer examination, preserving their numerical source frame IDs, into Capsule Review. In the same local/private workspace, run:

    python scripts/import_private_galar_original_scores.py \
      --data-dir /private/capsule-review-workspace \
      --study-id YOUR_EXISTING_LOCAL_STUDY_ID \
      --source frozen-transfer \
      --examination 23 \
      --private-archive /private/capsule-galar-frozen-transfer-private-repro.zip \
      --receipt /private/new-galar-score-import-receipt.json

For 25/27/29, choose source appearance-audit and its previously verified private ZIP.

The command rejects if the exact 512 imported source-image IDs/cryptographic hashes differ, if an included display PNG was modified after import, if the examination is synthetic, if the reference-score CSV is incomplete, or if a prediction run was already imported. The app persists **512 separate uncalibrated model suggestions**, without modifying notes, bookmarks, review intervals or source reference labels. The optional receipt contains **only aggregate verification facts**, not original image identifiers, frame-level scores, source annotations or notes. The tool never overwrites an existing receipt.

## Working browser workflow

Open the matching study, locate **Research review queue**, select the complete experimental blood-score label, and choose any K between 1 and all 512 imported images. Build the queue using highest scores, score with imported-ordinal separation, one highest score per chronology bin, or exact midpoint uniform. The coverage-first browser default is chronology-bin score selection for a transparent imported-position spacing guard, **not a clinically validated winning algorithm**. None of these policies hides the remaining imported images or automatically saves reviewer findings.

## Tests and limitations

Public tests use **generated geometric PNG fixtures**, never private original medical pixels. They synthesize a pinned private-style score ZIP, match all 512 source and display checksums, check the real SQLite prediction import and browser-facing queue API, and reject wrong source IDs, altered ZIP bytes, nonfinite scores, missing frames and tampered local images. They also verify preservation of human-authored review notes and no automatically added labels.

For the already verified original-CNN retrospective experiment and major negative results on Galar23/25, consult [GALAR_PRIORITY_SCORE_REPLAY.md](GALAR_PRIORITY_SCORE_REPLAY.md). This is an **usability bridge for an exploratory model**, not independent pathology detection, source annotation-run sensitivity, or measured physician review time. The real scientific priority remains independent examination-separated evaluation on denser original-image inputs with full corrected source-run ground truth.
