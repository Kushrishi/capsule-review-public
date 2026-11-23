# Desktop prototype v0.1

The optional desktop launcher opens the existing Capsule Review viewer in a native
pywebview window. FastAPI, import, review, detection records, queue comparison and
exports use the same application code and database as browser mode. No server,
account, cloud connection or model download is needed during use. This is research
software, not a clinical application. No model weights or medical images are bundled.

## One-time setup from a source checkout

Python 3.11–3.13 is supported by the project. Keep the checkout and its virtual
environment in a stable location: the shortcut points to that environment.
Installation of Python dependencies requires internet access; normal use does not.

Windows PowerShell, from the repository directory:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\python -m pip install -e ".[desktop]"
.venv\Scripts\capsule-review-desktop.exe --create-shortcut
```

Double-click **Capsule Review.vbs** on the Desktop. It invokes the virtual
environment's `pythonw.exe` without a terminal. Windows needs Microsoft Edge
WebView2 Runtime. If Windows Script Host is disabled by your organization, create
a normal Windows shortcut targeting `.venv\Scripts\capsule-review-desktop.exe`.

macOS or Linux, from the repository directory:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[desktop]'
.venv/bin/python -m capsule_review.desktop --create-shortcut
```

Double-click **Capsule Review.command** on macOS or **Capsule Review.desktop** on
Linux. Linux desktops may require **Allow Launching** / marking the shortcut as
trusted. The macOS command shortcut opens Terminal automatically; no commands need
to be entered, and the viewer opens in its own window. These are source launch
shortcuts, not installers or self-contained application bundles.

macOS uses the system WebKit renderer. Linux uses Qt WebEngine; the desktop extra
includes its Python bindings. Native Linux libraries (including OpenGL/EGL and XCB)
and a functioning graphical session must also be available. Do not disable the
WebEngine sandbox in normal use. A missing native dependency may stop Qt before
Python can show an error dialog.

For a direct development launch:

```sh
.venv/bin/python -m capsule_review.desktop
```

The installed `capsule-review-desktop` GUI entrypoint is equivalent. Optional desktop
dependencies are not needed for `capsule-review serve` or existing API/browser tests.

## Workspace and existing studies

| System | Default desktop workspace |
| --- | --- |
| Windows | `%LOCALAPPDATA%\Capsule Review` |
| macOS | `~/Library/Application Support/Capsule Review` |
| Linux | `$XDG_DATA_HOME/Capsule Review`, normally `~/.local/share/Capsule Review` |

The desktop default is separate from browser mode's `~/.capsule-review`. It does
not silently move or copy old studies. To open an existing workspace, pass its
absolute path; include the same option when creating the shortcut:

```sh
.venv/bin/python -m capsule_review.desktop --data-dir "$HOME/.capsule-review"
.venv/bin/python -m capsule_review.desktop --data-dir "$HOME/.capsule-review" --create-shortcut
```

On Windows use `.venv\Scripts\capsule-review-desktop.exe --data-dir "C:\path\to\workspace"`.
Remove an existing shortcut before recreating it. Desktop mode uses its own default
or `--data-dir`; `CAPSULE_REVIEW_DATA` remains a browser-app setting.

The workspace owns imported full-resolution decoded frames and thumbnails,
`reviews.sqlite3` and its SQLite journal files, saved notes/bookmarks, intervals,
predictions, detection runs and installed local models. Moving or removing the
original import folder does not remove imported frames. As in browser mode,
imports preserve decoded pixels in normalized PNGs, source hashes and filenames;
they do not archive original compressed file bytes or EXIF metadata. Keep source
files separately if byte-for-byte source preservation is required.

Use **Import examination**, **Open test sequence**, the ordinary review controls
and JSON score/detection imports in the window. All imported frames stay reachable,
including those outside a selected queue. Browser import limits (1,000 files,
512 MiB total) still apply to uploads. Larger local folders use the desktop
workflow below; the existing CLI remains compatible. Export actions open a native
save dialog.

## Import a full examination from the window

1. Select **Import frames**, enter a title and optional source attribution.
2. Under **Full examination folder**, select **Choose local folder** and choose
   the folder in the native picker.
3. Select **Import full examination**. The dialog closes; scanning, frame counts,
   bytes written, elapsed time and skipped-entry counts appear above the viewer.
4. Use **Cancel import** to stop before publication, or **Open imported
   examination** when it completes. Existing studies remain reviewable meanwhile.

Folder paths travel only over the private launcher/backend pipe. The authenticated
HTTP interface accepts a one-use native-selection grant, never a path. These routes
are not registered by the ordinary browser server. Native selection verifies the
local viewer's origin before and after the picker. No JavaScript/Python bridge or
relaxed content-security policy is used. Browser upload limits remain unchanged.

The importer scans only the selected directory, naturally orders PNG/JPEG/WebP
filenames, then reads and normalizes one bounded file at a time. Unsupported entries
and subfolders are counted and skipped; supported-extension symlinks, duplicate
case-folded names or source indices, changed files, unreadable images and decode
failures stop the whole import with an error. Source identity hashes, source-index
semantics, decoded pixels and existing annotations are preserved. Reference-label
CSVs remain available through the CLI; this folder picker does not infer labels.

Frame metadata and duplicate detection use temporary SQLite storage; the manifest
hash matches the existing serialized identity exactly. A small sorted inventory
of filenames and file identities remains in memory. Pixel memory depends on the
current image, rather than total examination bytes. A final SQLite transaction
publishes the entire study after image staging; it is never listed half-imported.
Cancellation stops at file/image boundaries, cleans staging and publishes nothing.
Once **Saving examination** begins, cancellation is disabled: publication finishes
atomically or is rolled back/recovered after termination.

Desktop guard: **100,000 supported images per folder**, not a tested scalability
claim. Existing per-image limits remain **32 MiB compressed / 24 megapixels**.
At least the next normalized image's output size plus **16 MiB** must be free before
writing; later disk errors still abort safely. PNG storage can exceed JPEG source
size substantially. Keep the source folder unchanged during import. Slow or stalled
filesystem operations may delay cancellation; shutdown remains bounded and recovery
cleans a force-stopped job on reopening. No automatic partial-import resume is offered.

## Lifecycle and local access

Each launch reserves an OS-assigned IPv4 loopback port; there is no LAN listener,
port probing race, or fixed-port dependency. A one-use random launch ticket is
exchanged for a session cookie before any page, API, image or static asset can be
read. The ticket disappears from the visible URL after redirect. The cookie is
HttpOnly and SameSite Strict; write requests still need the existing review token.
Exact Host and Origin checks remain enforced. HTTP request/access logging is off.
Credentials are regenerated each launch and are not saved in the workspace or
passed in process command-line arguments. No application Python API is exposed to
JavaScript, and the webview uses a temporary browser profile.

Closing the window asks for confirmation and stops its backend. **Save review**
before closing: confirmation does not save an unfinished text draft. A lost launcher
pipe, including forced termination of the parent, shuts down the backend too.
Shutdown is bounded; a stuck worker is terminated after a grace period. If the
backend fails while the window is open, the launcher closes the window and reports
an error. Workspace initialization and duplicate desktop launches also report errors.
Only one desktop backend may use a workspace at a time; the OS releases its lock
after a crash, so an old `.desktop.lock` file does not prevent reopening.

Completed SQLite transactions survive restart; incomplete transactions roll back
on reopening. Interrupted imports do not expose a partial study. At desktop startup,
while holding the workspace lock, the app removes staging/image folders bearing
its exact import marker when no committed study references them. Completed studies
retain their images; only leftover staging metadata is removed. Legacy unmarked
folders are left alone. The interface reports recovered interrupted imports; choose
the original folder again to restart. Force termination cannot recover edits that
were never saved. Do not
run the browser server or CLI writers concurrently against a desktop workspace;
the desktop lock does not coordinate those older entrypoints. Back up the entire
workspace after closing all processes, rather than copying only the SQLite file
while it is open.

Session checks prevent accidental or unauthenticated local HTTP access. They do
not protect against malware running as the same OS user, administrators or someone
who can read the workspace directly. Data are not encrypted; choose a private local
folder. The launcher does not change browser mode's existing access boundary.

## Verification and remaining limits

Automated process/HTTP tests:

```sh
python -m pip install -e '.[dev,desktop]'
python -m pytest -q tests/test_desktop.py
```

These exercise authenticated startup, denied reads/writes without a session,
one-use ticket replay rejection, foreign origins/ports, retained write-token
checks, generated study and image import, invalid input, persisted original-size
pixels/annotations/detections, review export, workspace locking, failed startup,
startup timeout, normal shutdown, killed backend recovery and parent-death cleanup.

A separate real Qt window smoke test drives native DOM rendering, synthetic-study
navigation, saved annotation and native blob-export download, then closes the
window and checks persisted review data. The second invocation kills the backend
and checks that the production window supervisor reports the failure:

```sh
python tests/desktop_gui_smoke.py
python tests/desktop_gui_smoke.py --kill-backend
```

For a displayless Linux test environment only:

```sh
QT_API=pyqt6 QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 python tests/desktop_gui_smoke.py
python tests/desktop_gui_smoke.py --kill-backend
```

The native save picker is replaced with a temporary generated-output path by that
test; it does not verify human file-dialog interaction. Offscreen success is not
verification of screen presentation, accessibility, OS shortcut trust prompts,
Windows WebView2, or macOS WebKit. Windows/macOS launches and interactive native
file/folder selection require testing on those systems before packaging.

The shell contains a small compatibility hook for pywebview 6.2's Qt download
handler, which otherwise calls the removed Qt5 `setPath` method under Qt6. It uses
Qt6's download-directory and filename setters for both ordinary and blob exports.
The pywebview minor range is bounded so upgrades receive a new native export test.
No installers, signed binaries or releases are provided by this change.

### Desktop v0.1 validation (before the full-examination follow-up)

- Full repository suite with local-model dependencies installed: **1,284 passed**.
  Three additional desktop error/shortcut tests were then added; the final focused
  desktop suite passed **9 tests**.
- Real pywebview 6.2.1 / PyQt6 6.12 / Qt WebEngine smoke passed in offscreen mode:
  authenticated viewer, full-size synthetic images, navigation, saved annotation,
  native blob ZIP download, window shutdown and retained data. The backend-failure
  variant also passed.
- The existing Playwright browser smoke was attempted with system Chromium and
  blocked at browser startup by the execution environment's Unix-socket restriction
  (`ProcessSingleton` socket creation denied), before any viewer assertion ran.
  Downloading Playwright's Chromium also failed with an invalid archive response.
  The existing browser/local-model CI jobs are retained for a normal runner.
- No interactive screen, OS shortcut launch, human file picker, Windows or macOS
  GUI test was executed here. Native smoke replaces only the save-picker choice;
  it uses the real webview, production launcher, HTTP transport and export bytes.

### Full-examination import measurements

Linux / Python 3.12; deterministic generated 256×256 JPEG, repeated under distinct
filenames. Every frame is decoded, hashed, normalized and stored. Source fixtures
use hard links where available; filesystem cache and concurrent test load affect
throughput. These are software measurements, not clinical data or medical results.

| Run | Images | Source MiB | Image output MiB | Import seconds | Images/s | Peak RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Import core, fresh process | 1,000 | 73.82 | 206.47 | 23.941 | 41.77 | 23.08 |
| Import core, fresh process | 12,000 | 885.78 | 2,477.69 | 301.406 | 39.81 | 36.94 |
| Actual desktop backend | 3,000 | 221.45 | 619.42 | 111.709 | 26.86 | 54.01 |

The 12,000-frame run exceeds both browser-upload limits. Its importer RSS was
34.06 MiB after scanning/sorting, 35.70 MiB at 6,000 frames and 36.94 MiB at 12,000.
The growth includes the filename inventory and SQLite caches; memory is not claimed
to be constant or independent of image dimensions. The core figures exclude the
FastAPI, GUI and renderer processes. The actual backend row includes FastAPI and
its import job, measured through `/proc`; baseline backend RSS was 45.73 MiB before
import. It excludes the native-window and renderer processes. Last-frame metadata lookup took 1.054 ms in
that run; this is not a GUI interaction or end-to-end image latency measurement.
100,000 images and 24-megapixel inputs have not been benchmarked.

Reproduce generated-data measurements on Linux, one fresh process per size:

```sh
python tests/desktop_import_benchmark.py --frames 1000
python tests/desktop_import_benchmark.py --frames 12000
python tests/desktop_import_benchmark.py --frames 3000 --desktop
python -m pytest -q tests/test_desktop_folder_import.py
```

The folder-import native smoke adds the real desktop selection IPC, authenticated
job requests, cancellation/retry, a 3,000-frame import, last-frame navigation and
12-thumbnail filmstrip checks. It observed at most three full-resolution image
requests during that large-study navigation. The native picker result is stubbed
with a generated folder, so human picker interaction remains unverified:

```sh
QT_API=pyqt6 QT_QPA_PLATFORM=offscreen QTWEBENGINE_DISABLE_SANDBOX=1 python tests/desktop_gui_smoke.py --folder-import
```

Windows/macOS native picking, permissions/reparse points, platform-specific disk
failures, and interactive shutdown during a picker still need platform testing.
macOS verification is deferred to the separate interactive session. No private
clinical images, model training, installers or binaries are part of this change.

Follow-up validation: full repository suite **1,306 passed** on Linux/Python 3.12;
focused desktop/importer/API/detection checks **114 passed**; source privacy gate
**593 tracked paths passed**. Tests cover native grant boundaries, changed sources,
duplicates, decoding/read failures, simulated space and transaction failures,
cancellation/publication races, restart persistence, process-kill recovery and
shutdown during import. GUI results above are actual offscreen Qt execution with
only picker choices stubbed. Existing browser smoke remains subject to the v0.1
environment restriction described above; no new interactive macOS/Windows claim
is made.

## Apple Silicon macOS qualification

The dedicated [macOS workflow](../.github/workflows/macos-desktop.yml) uses the
standard `macos-15` runner, verifies a genuine `Darwin` / `arm64` Python process,
and installs `.[desktop,dev]` with Python 3.12. It does not install model extras,
train models, use MPS or run the large performance benchmark. Existing Linux jobs
remain unchanged. It can also be started with **Run workflow** in GitHub Actions.

Process/API tests cover package/entrypoint startup, authenticated loopback access,
workspace locking, persistence, folder jobs, cancellation, process-kill recovery,
annotations and exports. The separate `tests/macos_desktop_smoke.py` invokes the
production launcher with real AppKit/WKWebView: a visible native window, session
bootstrap, 64 generated frames, native selection IPC, last-frame navigation,
notes, blob review download, authenticated full-span download and window shutdown.
Its second invocation kills the backend and verifies native failure handling.
Folder and save-dialog choices and confirmation responses are automated; network
requests, WebKit rendering, import, ZIP bytes and persistence are not replaced.
A timeout fails the native test, rather than reporting process-only coverage as GUI
success. No screenshots or generated examinations are published as CI artifacts.

To repeat the native test on a Mac after installing the desktop/test extras:

```sh
python tests/macos_desktop_smoke.py
python tests/macos_desktop_smoke.py --kill-backend
```

Final physical-Mac check (generated images only):

1. Launch the existing `.command` shortcut by double-clicking it. Check window
   layout, Retina scaling, keyboard navigation/focus and close confirmation.
2. Use the real folder picker: cancel once, then choose a test folder with spaces
   or Unicode in its name. Check macOS access prompts for Desktop/Documents/
   Downloads; denying permission must show an error and permit a later retry.
3. Cancel a folder import, retry, then close during another import. Reopen through
   the shortcut and confirm completed studies/notes persist without a partial study.
   Also check the second-window workspace-lock message.
4. Cancel a native save dialog, then export review and full spans to a chosen
   folder. Open both ZIPs in Finder. Quit/relaunch and confirm the saved annotation,
   last reviewed frame and any generated detection fixture remain available.

Automated window creation/DOM checks do not establish human picker usability,
visual presentation, TCC permission behavior or Finder/shortcut restart behavior.

Qualification result (16 November 2026): [Apple Silicon CI run](https://github.com/Kushrishi/capsule-review-public/actions/runs/43955403141)
passed on macOS 15.8.2 / arm64 with Python 3.12.10: **114 process/API tests**, real
Cocoa/WKWebView window/import/review/blob and authenticated-span downloads, normal
shutdown and forced-backend failure. Picker/save choices and confirmation were
automated as described above. No production-code defect was found. A case-sensitive
filesystem assumption in a duplicate-name fixture was corrected; the active-workflow
allowlist also includes this intentional new CI job, with archived workflow hashes
unchanged.

## Suggestions through review and export

Standard and full-span JSON exports retain `model_suggestions` separately from
human `review` entries. They include the prediction/detection run identifiers,
imported model/provenance metadata and suggestion records for exported frames only.
Suggestions on omitted frames are not silently included. The original detection
payload SHA-256 identifies the **complete imported run**, not the exported subset;
its scope is labeled explicitly. Imported provenance remains an unverified claim
about model execution. Existing image/reviewer evidence audits do not turn these
claims into authenticated model execution or clinical findings.

Both exports fail if a retained display image differs from its imported SHA-256.
Suggestion metadata has an 8-MiB accumulation bound; normal/full-span manifests
also retain their 32-/64-MiB verification limits. An export over a bound fails
explicitly rather than silently dropping model provenance. AI suggestions alone
do not select images for export or create reviewer findings.

Hosted verification uses the existing nonmedical synthetic study and generated
suggestion fixture, through real Chromium and native macOS WebKit controls. These
fixtures test the workflow; they do not demonstrate a medically trained model.
Normal folder imports remain ineligible for synthetic detection fixtures.

A zero-install **synthetic workflow demonstration is feasible as a separate static
browser build** with generated frames, fixed example scores and in-browser review
state. It should have no clinical-image upload, native folder bridge, arbitrary
filesystem access or connection to the desktop backend. The existing standalone
HTML export already supports zero-install viewing of an illustrated review, but
is not an interactive viewer demonstration. The current desktop application still
requires its local Python/backend environment. No static demo or public deployment
is created by this qualification; forwarding the real desktop service is not the
recommended route to a demonstration.

Remote integration evidence: the generated-data [macOS run](https://github.com/Kushrishi/capsule-review-public/actions/runs/44003308341)
passed **120 tests** and both native WebKit flows, including category filtering,
abnormality navigation, selected/unselected access, unchanged human notes and
suggestion provenance in the actual downloaded review ZIP. Sealed-inference
regressions separately passed **78 generated-data tests**. This validates fixture
transport and review/export behavior, not execution of a medically trained detector.


## Closing a draft

Closing the ordinary desktop window with an unsaved frame draft offers **Save and close**, **Discard**, and **Cancel**. Save uses the existing revision-checked API while the backend is alive. A conflict, failed save or unconfirmed eight-second save keeps the window open with the draft and an error. Cancel returns to editing. Discard closes without writing that draft; earlier saved entries remain intact. Browser tabs retain their existing unload warning.

Close negotiation uses native-to-page calls, with no JavaScript/Python bridge or filesystem API. Native replies are bounded to two seconds; a choice expires after two minutes and leaves the window open. If the web engine stops replying, close is rejected rather than silently discarding the draft. A permanently stalled engine may require an operating-system force quit; unsaved text cannot be recovered after a force quit, process kill, power loss or backend failure. Signals/backend failure still use the existing forced shutdown and import recovery. This protects ordinary native close, not crash recovery of unsaved drafts.

`python tests/desktop_close_smoke.py` and `python tests/desktop_close_smoke.py --discard` exercise genuine native close events, generated draft choices, revision conflict, save failure/timeout, persistence and workspace reopening. They use Qt on Linux or Cocoa/WKWebView on macOS. Automated choices are not a physical-user usability test.
