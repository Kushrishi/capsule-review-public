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
512 MiB total) still apply. Larger local imports use the existing CLI with the
same explicit workspace path. Export actions open a native save dialog.

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
on reopening. Interrupted image imports can leave unreferenced staging/image
folders on disk, but no partially committed study is listed. These folders are not
automatically deleted: they may need manual recovery/cleanup after backing up the
workspace. Force termination cannot recover edits that were never saved. Do not
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

### Checks executed for this PR (Linux, Python 3.12)

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
