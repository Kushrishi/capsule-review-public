"""Exercise the blinded reviewer packet in a real Chromium browser.

Synthetic pixels only. This does not open the private 137-image pilot, collect
clinical annotations, authorize image sharing, or validate medical accuracy.
Both direct file opening and localhost static serving must work.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
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
from playwright.sync_api import Error as PlaywrightError, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_blinded_short_event_review import build_packet
from audit_blinded_review_responses import compare, validate_response


ANSWERS = {
    "fresh_blood": "uncertain",
    "hematin": "no",
    "artifact": "no",
    "image_quality": "adequate",
    "needs_context": "yes",
}


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


def _export(page, destination: Path) -> dict:
    with page.expect_download() as event:
        page.locator("#export").click()
    event.value.save_as(destination)
    return json.loads(destination.read_text(encoding="utf-8"))


def _restore(page, response: dict, name: str) -> None:
    page.locator("#restore").set_input_files({
        "name": name,
        "mimeType": "application/json",
        "buffer": json.dumps(response).encode("utf-8"),
    })


def _assert_incomplete(response: dict, manifest: dict) -> None:
    try:
        validate_response(response, manifest)
    except ValueError as error:
        assert "Every preselected" in str(error) or "Incomplete" in str(error)
    else:
        raise AssertionError("Incomplete browser export was accepted for dual review")


def _exercise(browser, origin: str, mode: str, packet_id: str, directory: Path) -> None:
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    requested: list[str] = []

    def make_context():
        context = browser.new_context(accept_downloads=True)
        context.set_default_timeout(10_000)
        context.on("request", lambda request: requested.append(request.url))
        context.on("page", lambda page: page.on("pageerror", lambda error: errors.append(str(error))))
        return context

    def open_page(context):
        page = context.new_page()
        page.goto(origin + "/index.html", wait_until="load")
        expect(page.locator("#viewer")).to_be_visible()
        expect(page.locator("#progress")).to_have_text("Image 1 / 4")
        expect(page.locator("#previous")).to_be_disabled()
        expect(page.locator("#scan")).to_have_js_property("naturalWidth", 512)
        return page

    context = make_context()
    independent_context = make_context()
    try:
        page = open_page(context)
        first_radio = page.locator('[data-field="fresh_blood"] input[value="uncertain"]')
        expect(first_radio).to_be_disabled()
        expect(page.locator("#note")).to_be_disabled()
        page.locator("#reviewer").fill("invalid reviewer code")
        expect(first_radio).to_be_disabled()
        page.locator("#reviewer").fill("reviewer-A")
        expect(first_radio).to_be_enabled()
        first_radio.check()
        expect(page.locator("#reviewer")).to_have_js_property("readOnly", True)
        note = "Synthetic fixture; no medical judgement."
        page.locator("#note").fill(note)

        # First-image edits must be protected before Next or Export has saved them.
        dialogs: list[str] = []

        def keep_work(dialog):
            dialogs.append(dialog.type)
            dialog.dismiss()

        page.on("dialog", keep_work)
        try:
            page.reload(wait_until="load")
        except PlaywrightError as error:
            assert "ERR_ABORTED" in str(error), str(error)
        assert dialogs == ["beforeunload"], dialogs
        page.remove_listener("dialog", keep_work)
        expect(page.locator("#note")).to_have_value(note)

        response = _export(page, directory / f"{mode}-partial.json")
        first_id = manifest["items"][0]["item_id"]
        assert response["packet_id"] == packet_id
        assert response["reviewer_code"] == "reviewer-A"
        assert set(response["responses"]) == {first_id}
        answer = response["responses"][first_id]
        assert answer["fresh_blood"] == "uncertain"
        assert all(answer[field] is None for field in ANSWERS if field != "fresh_blood")
        assert answer["note"] == note
        _assert_incomplete(response, manifest)
        partial_page = open_page(context)
        _restore(partial_page, response, "partial.json")
        expect(partial_page.locator("#reviewer")).to_have_js_property("readOnly", True)
        assert partial_page.locator("#answers input:checked").count() == 1
        partial_roundtrip = _export(partial_page, directory / f"{mode}-partial-roundtrip.json")
        assert partial_roundtrip["responses"] == response["responses"]
        partial_page.close()

        # Corrupt imports cannot erase saved answers or the current unsaved note.
        pending_note = note + " Unsaved edit."
        page.locator("#note").fill(pending_note)
        invalid = []
        for value in ([], None, "not a response object"):
            bad = deepcopy(response)
            bad["responses"] = value
            invalid.append(bad)
        bad = deepcopy(response)
        bad["responses"][first_id] = []
        invalid.append(bad)
        bad = deepcopy(response)
        bad["responses"][first_id]["fresh_blood"] = "unknown-as-negative"
        invalid.append(bad)
        bad = deepcopy(response)
        bad["packet_id"] = "a" * 24
        invalid.append(bad)
        bad = deepcopy(response)
        bad["reviewer_code"] = "invalid reviewer code"
        invalid.append(bad)
        for index, bad in enumerate(invalid):
            # Also verify schema validation in a clean tab, so an existing-work
            # guard alone cannot make malformed input appear safely rejected.
            clean = open_page(context)
            _restore(clean, bad, f"bad-clean-{index}.json")
            expect(clean.locator("#status")).to_contain_text("Cannot restore")
            expect(clean.locator("#reviewer")).to_have_value("")
            expect(clean.locator("#note")).to_have_value("")
            clean.close()
            _restore(page, bad, f"bad-active-{index}.json")
            expect(page.locator("#status")).to_contain_text("Cannot restore")
            expect(page.locator("#reviewer")).to_have_value("reviewer-A")
            expect(page.locator("#note")).to_have_value(pending_note)
            expect(first_radio).to_be_checked()

        for code in ("reviewer-A", "reviewer-B"):
            conflicting = deepcopy(response)
            conflicting["reviewer_code"] = code
            _restore(page, conflicting, f"conflicting-{code}.json")
            expect(page.locator("#status")).to_contain_text("Open a new tab")
            expect(page.locator("#reviewer")).to_have_value("reviewer-A")
            expect(page.locator("#note")).to_have_value(pending_note)
        retained = _export(page, directory / f"{mode}-retained.json")
        assert retained["responses"][first_id]["note"] == pending_note

        # Every synthetic image renders; first/last navigation and field values
        # survive a full export/restore round trip.
        for index, item in enumerate(manifest["items"]):
            expect(page.locator("#progress")).to_have_text(f"Image {index + 1} / 4")
            expect(page.locator("#scan")).to_have_attribute("src", item["image"])
            expect(page.locator("#scan")).to_have_js_property("complete", True)
            expect(page.locator("#scan")).to_have_js_property("naturalWidth", 512)
            for field, value in ANSWERS.items():
                page.locator(f'[data-field="{field}"] input[value="{value}"]').check()
            page.locator("#note").fill(f"Synthetic image {index + 1}; no clinical judgement.")
            if index == 3:
                expect(page.locator("#next")).to_have_text("Save final image")
            page.locator("#next").click()
        expect(page.locator("#progress")).to_have_text("Image 4 / 4")
        complete = _export(page, directory / f"{mode}-complete.json")
        validate_response(complete, manifest)
        assert all(set(value) == set(ANSWERS) | {"note"} for value in complete["responses"].values())
        assert set(complete) == {"schema_version", "packet_id", "reviewer_code", "responses", "exported_at"}
        assert all(set(item) == {"item_id", "image"} for item in manifest["items"])
        assert not any(key in json.dumps(complete) for key in (
            "source_exam", "source_frame", "published_blood_label", "positive_index", "negative_index",
        ))

        restored = open_page(context)
        _restore(restored, complete, "complete.json")
        expect(restored.locator("#reviewer")).to_have_value("reviewer-A")
        expect(restored.locator("#reviewer")).to_have_js_property("readOnly", True)
        for index in range(4):
            for field, value in ANSWERS.items():
                expect(restored.locator(f'[data-field="{field}"] input[value="{value}"]')).to_be_checked()
            expect(restored.locator("#note")).to_have_value(f"Synthetic image {index + 1}; no clinical judgement.")
            if index < 3:
                restored.locator("#next").click()
        restored.locator("#previous").click()
        expect(restored.locator("#progress")).to_have_text("Image 3 / 4")
        roundtrip = _export(restored, directory / f"{mode}-roundtrip.json")
        assert roundtrip["responses"] == complete["responses"]

        independent = open_page(independent_context)
        expect(independent.locator("#reviewer")).to_have_value("")
        expect(independent.locator("#note")).to_have_value("")
        assert independent.locator("#answers input:checked").count() == 0
        independent.locator("#reviewer").fill("reviewer-B")
        for index in range(4):
            for field, value in ANSWERS.items():
                chosen = "yes" if index == 0 and field == "fresh_blood" else value
                independent.locator(f'[data-field="{field}"] input[value="{chosen}"]').check()
            independent.locator("#next").click()
        other = _export(independent, directory / f"{mode}-independent.json")
        agreement = compare(manifest, complete, other)
        assert agreement["images_with_any_disagreement"] == 1
        assert agreement["field_agreement"]["fresh_blood"] == {"agree": 3, "disagree": 1}
        assert agreement["both_uncertain"]["fresh_blood"] == 3
        assert agreement["arbitration_required"] is True
        assert agreement["status"] == "DUAL_REVIEW_AGREEMENT_ONLY_NO_CLINICAL_REFERENCE_STANDARD"

        # This observes normal-operation requests; it does not simulate an attack
        # or claim that the browser test actively exercised CSP enforcement.
        assert all(url.startswith(origin + "/") for url in requested), requested
        assert not errors, errors
    finally:
        independent_context.close()
        context.close()
    print(f"PASS blinded reviewer Chromium {mode}: identity, partial answers, safe restore, navigation, export and independent response comparison", flush=True)


def main() -> None:
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--browser-executable", help="Optional installed Chromium path; CI uses Playwright's Chromium")
    args = cli.parse_args()
    with tempfile.TemporaryDirectory(prefix="capsule-blinded-browser-") as temp:
        directory = Path(temp)
        packet_id = _make_packet(directory)
        handler = partial(_QuietHandler, directory=str(directory))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    headless=True, args=["--no-sandbox"], executable_path=args.browser_executable,
                )
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
