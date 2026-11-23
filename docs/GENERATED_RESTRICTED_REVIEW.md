# Generated restricted review prototype

Opt-in software control, separate from the ordinary exploratory workbench.
After installing the existing desktop extra, a cloud operator can launch:

```sh
capsule-review-desktop --restricted-generated
```

No personal-computer commands, clinical images, installed model or existing
workspace are required. The flag rejects `--data-dir` and shortcut creation.
It creates the existing 24-frame geometric fixture in a temporary workspace,
adds the existing generated score stream, and freezes `score_bin`, K=2 and
source positions [6,12] before serving any study pixels. These are generated
numbers, not AI findings, and are not an approved scientific selection policy.

The same authenticated loopback desktop process, temporary browser profile and
shutdown supervisor are reused. This app registers only its dedicated routes;
ordinary study, import, model, static-image and export routes are unavailable.
Full-resolution PNGs and JPEG thumbnails are checked against frozen byte hashes
before authorization. Only the two selected source identities can be served or
exported, including after session exit. There is no context-image allowance,
replacement, selection edit, reset, or omitted-image reveal in this prototype.
Repeating or magnifying a permitted identity does not add a source identity.
All original images remain available in the separately launched ordinary viewer.

The export includes exactly the two selected PNGs and a JSON receipt with the
source manifest, filenames, indices, original/display/thumbnail hashes, generated
run identity, selected positions, session commitment and chained access records.
Authorization is recorded and fsynced **before** returning pixels; it is not proof
that a response arrived, pixels rendered, or a person saw them. Denied canonical
image requests record position and representation; alternate routes record a
route-denial event without copying caller-controlled paths or request bodies.
A changed/missing image or ledger-write failure invalidates the claim and blocks
further pixel authorization. The receipt is hash-linked, not signed or protected
against an OS administrator who can rewrite all files and recompute hashes.

**End restricted session** permanently invalidates this session's restricted
claim and clears its displayed image/navigation. Reloading cannot restore it.
The server continues to deny omitted images. Unrestricted exploration requires
the ordinary viewer separately; no claim may carry over to that exploration.
A new launch is a different session and cannot erase any prior exposure.
The temporary workspace and local ledger are removed on normal close: download
evidence before closing. A crash may leave a temporary directory; it is not a
resumable restricted session and cannot be reopened by this flag.

This limits server-authorized **unique source identities**, not human exposure,
dwell time or clinical review. It cannot erase images viewed before launch,
control another browser/app, police a same-user debugger/administrator or qualify
an actual reader study. No annotations or biomedical model are part of this small
control. R1/R2, their approved methods, frozen results and permission gates are
unchanged. A clinical locked-reader interaction policy remains a separate decision.

## Regression checks

```sh
python -m pytest -q tests/test_restricted_demo.py
python tests/restricted_browser_smoke.py
python tests/desktop_restricted_smoke.py
```

The last command runs native Qt on Linux or WKWebView on macOS and needs the
existing desktop dependencies and an available display environment. Hosted Mac
checks use automated interaction; physical presentation, permissions and actual
human seeing remain unverified. Linux offscreen tests may use the existing
test-only Qt renderer settings; they do not qualify production sandboxing.
