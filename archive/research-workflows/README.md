# Historical research workflow archive

These 14 GitHub Actions YAML files were moved **without modifying their contents** from `.github/workflows/` in main commit `8d6993035ed866c001acee149229ee0385a9b2a9` during the 2026-11-10 repository consolidation.

They are **historical research, acquisition, or source-index recipes**, not part of current routine CI. Most jobs are gated to private repositories; the old Galar 31–40 index job also had an obsolete branch-specific push trigger. The four active workflow definitions remain in [GitHub Actions](../../.github/workflows/): `tests.yml`, `public-source-privacy.yml`, `galar-frozen-mobilenet.yml`, and `galar-negative-expansion-cv.yml`.

**Archive is not executable in GitHub Actions.** GitHub only discovers workflow definitions in `.github/workflows/`. Keeping these source files here preserves the exact historical run configurations and dependency references while removing obsolete buttons and one-off triggers from the active Actions menu. **All referenced Python scripts, tests, dated research reports and result aggregates remain untouched.** Original execution context, Actions logs and private data are not reproduced by this archive.

## Byte-for-byte provenance

Every archived file retains its original Git blob SHA-1. `tests/test_workflow_archive.py` independently verifies Git blob hashes and the live workflow allowlist.

| Archived YAML | Original Git blob SHA-1 |
| --- | --- |
| `galar-21-29-index.yml` | `9ca3b6648153a8f55251ceebf8ab478fa88e335a` |
| `galar-31-40-index-only.yml` | `762f71dc6150eb9cf0d1652a90ff80e7204c021f` |
| `galar-block0-acquisition.yml` | `fd26783f78e215f8eee7a94121bc816132af814b` |
| `galar-block1-exam23.yml` | `68359d21229aa82b72299f1b30279de0918fc0db` |
| `galar-density-ceiling.yml` | `2071570cb2657f62e3babca5f86df13b214dde59` |
| `galar-exam29-acquisition.yml` | `4386b4ffbac33bfb3a9255c04355cb42bd381723` |
| `galar-multiblock-exam30.yml` | `cc0260fb3b0e54d82166f840163ac1637e857ab4` |
| `galar-negative-22-24.yml` | `632e564f6ea2eed0b14d65f0ef913fa82f4d9fea` |
| `galar23-pixel-density.yml` | `03e47000f46e3d96191c4e6b1b7c8bd8193fc468` |
| `galar25-streamed-acquisition.yml` | `98823a86977f7c57e46221461f51491aa059078a` |
| `galar27-streamed-acquisition.yml` | `b8293e8b164c2c2a066756fba7fa48e5916a9630` |
| `pretrained-weights.yml` | `c544fd825c858bcc56bff18fedaba1c0b948e825` |
| `red-lesion-gate.yml` | `1dc7bcc488e06847698eac5b7da58206c0b00fdb` |
| `rhode-replication.yml` | `30cd2575ff0a4d9f2430a0d0d2694f1dbb8a27a4` |

## Reproducing a historical run

Read the original dated protocol and source commit first. The original workflow definition is available here or in the parent Git commit; moving it does not alter previous GitHub Actions run records. Re-enabling an archived workflow would require a **separately reviewed change** returning its file under `.github/workflows/`, rechecking artifact retention, source permissions, credentials, dataset links, privacy risks and scope. Never run archival acquisition workflows against clinical data in public CI.

This consolidation **does not** improve pathology-model accuracy or qualify an independent study; it preserves reproducibility infrastructure and reduces inactive automation clutter.
