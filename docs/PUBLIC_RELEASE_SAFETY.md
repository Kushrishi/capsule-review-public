# Public release safety

The repository contains software, synthetic test fixtures, immutable protocols and non-identifying aggregate research results. Raw medical images, original per-frame annotations/identities, individual predictions, model checkpoints and private reproducibility packages must stay outside Git and public Actions artifacts. Existing dataset attribution and all negative research findings remain in place. No software licence has been added or changed.

## Actions boundary

Ordinary Python 3.11/3.12/3.13 software tests, the synthetic browser/local-model integration and synthetic research integrity checks remain enabled. The thirteen source-acquisition, source-index, source-analysis and pretrained-weight workflows are manual-only and have a job-level repository-private guard. They cannot execute in a public repository. Use an independently controlled private environment for future real-data work; do not remove this guard to recover a public CI result.

Before changing visibility, disable the historical source workflows in repository Actions settings too, because old branches and reruns can retain earlier unguarded definitions. Remove sensitive retained artifacts only after matching their bytes and SHA-256 digests against durable private copies. Review historical logs and every reachable branch and PR, not just the current tree. Never rewrite history or delete workflow runs without the owner's explicit approval.

## Research integrity

Do not change frozen protocol files, aggregate outputs, held-out identities or study conclusions during release cleanup. Galar 11–20 and authors' 61–80 remain reserved; privacy auditing must not open their source labels or pixels. Public CI uses synthetic data and does not acquire medical source images. No clinical model is promoted by a successful CI run.

## Source history

This clean source snapshot incorporates the completed PR #35 implementation at original private commit `551af823b8821cec3cec80b7400ed8fa64f994ce`, plus public-execution workflow guards. The original private archive retains its history, private workflow artifacts and review discussion. The clean snapshot omits personal supervisor-planning prose from the draft research protocol. All frozen experiment specifications and original aggregate output bytes are preserved. No medical sources or pretrained weights are bundled. The source remains without a software licence until its owner selects one.
