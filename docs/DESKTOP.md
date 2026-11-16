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
