"""Exercise the blinded reviewer packet in a real Chromium browser.

Synthetic pixels only. This does not open the private 137-image pilot, collect
clinical annotations, authorize image sharing, or validate medical accuracy.
Both direct file opening and localhost static serving must work.
"""
from __future__ import annotations

from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sys
import tempfile
from threading import Thread
from zipfile import ZipFile

from PIL import Image
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_blinded_short_event_review import build_packet


def _synthetic_image(color: tuple[int, int, int]) -> bytes:
    image = Image.new("RGB", (512, 512), color)
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _make_packet(directory: Path) -> str:
    # These deliberately simple coloured fixtures contain no medical imagery.
    inputs = [(23, 10, 1), (23, 15, 0), (25, 30, 1), (25, 35, 0)]
    originals = {}
    records = []
    for exam, frame, blood in inputs:
        pixels = _synthetic_image((exam, frame, 45 + blood * 100))
        originals[(exam, frame)] = pixels
        records.append({
            "exam": exam, "frame": frame, "blood": blood,
            "sha256": sha256(pixels).hexdigest(), "bytes": len(pixels),
        })
    manifest = {
        "images": records,
        "pairs": [
            {"exam": 23, "run_id": 0, "run_length": 1,
             "positive_index": 0, "negative_index": 1},
            {"exam": 25, "run_id": 1, "run_length": 2,
             "positive_index": 2, "negative_index": 3},
        ],
    }
    blinded, _escrow, receipt = build_packet(
        manifest, originals, [],
        manifest_sha=sha256(b"synthetic-browser-only").hexdigest(),
        expected_pairs=2,
        deterministic_ids={i: f"{i + 1:024x}" for i in range(len(inputs))},
        packet_id="d" * 24,
    )
    assert receipt["status"] == "PREPARED_NOT_CLINICALLY_REVIEWED"
    with ZipFile(BytesIO(blinded)) as packet:
        names = set(packet.namelist())
        assert "PRIVATE_KEY.json" not in names
        packet.extractall(directory)
    return "d" * 24


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, _format: str, *_args: object) -> None:
        pass


def _exercise(browser, origin: str, mode: str, packet_id: str, directory: Path) -> None:
    context = browser.new_context(accept_downloads=True)
    context.set_default_timeout(10_000)
    errors: list[str] = []
    requested: list[str] = []
    page = context.new_page()
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.on("request", lambda request: requested.append(request.url))
    page.goto(origin + "/index.html", wait_until="load")
    expect(page.locator("#viewer")).to_be_visible()
    expect(page.locator("#progress")).to_have_text("Image 1 / 4")
    expect(page.locator("#scan")).to_have_js_property("naturalWidth", 512)

    page.locator("#reviewer").fill("reviewer-smoke")
    for field, value in [
        ("fresh_blood", "uncertain"),
        ("hematin", "no"),
        ("artifact", "no"),
        ("image_quality", "adequate"),
        ("needs_context", "yes"),
    ]:
        page.locator(f'[data-field="{field}"] input[value="{value}"]').check()
    page.locator("#note").fill("Synthetic fixture; no medical judgement.")
    page.locator("#next").click()
    expect(page.locator("#progress")).to_have_text("Image 2 / 4")
    page.locator("#previous").click()
    expect(page.locator("#note")).to_have_value("Synthetic fixture; no medical judgement.")

    with page.expect_download() as download_event:
        page.locator("#export").click()
    download = download_event.value
    exported = directory / f"{mode}-response.json"
    download.save_as(exported)
    response = json.loads(exported.read_text(encoding="utf-8"))
    assert response["packet_id"] == packet_id
    assert response["reviewer_code"] == "reviewer-smoke"
    assert len(response["responses"]) == 1
    answer = next(iter(response["responses"].values()))
    assert answer["fresh_blood"] == "uncertain"
    assert answer["needs_context"] == "yes"
    assert answer["note"] == "Synthetic fixture; no medical judgement."
    assert "source_exam" not in exported.read_text(encoding="utf-8")

    restored = context.new_page()
    restored.on("pageerror", lambda error: errors.append(str(error)))
    restored.on("request", lambda request: requested.append(request.url))
    restored.goto(origin + "/index.html", wait_until="load")
    restored.locator("#restore").set_input_files(str(exported))
    expect(restored.locator("#reviewer")).to_have_value("reviewer-smoke")
    expect(restored.locator("#note")).to_have_value("Synthetic fixture; no medical judgement.")
    expect(restored.locator('[data-field="fresh_blood"] input[value="uncertain"]')).to_be_checked()

    if mode == "file":
        assert all(url.startswith("file://") for url in requested), requested
    else:
        assert all(url.startswith(origin + "/") for url in requested), requested
    assert not errors, errors
    context.close()
    print(f"PASS blinded reviewer actual Chromium {mode} launch, navigation, export and restore", flush=True)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="capsule-blinded-browser-") as temp:
        directory = Path(temp)
        packet_id = _make_packet(directory)
        handler = partial(_QuietHandler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True, args=["--no-sandbox"])
                try:
                    _exercise(browser, directory.as_uri(), "file", packet_id, directory)
                    _exercise(browser, f"http://127.0.0.1:{server.server_port}", "localhost", packet_id, directory)
                finally:
                    browser.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()
