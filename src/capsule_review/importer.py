"""Import numbered images, preserving source identity and optional Galar labels."""

import csv
import hashlib
import io
import json
import re
import shutil
import tempfile
import uuid
import warnings
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from .store import Store

MAX_FILE_BYTES = 32 * 1024 * 1024
MAX_PIXELS = 24_000_000
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
FRAME_RE = re.compile(r"^frame_(\d+)\.(?:png|jpe?g|webp)$", re.I)
PUBLISHED_IMAGE_RE = re.compile(r"^image-(\d+)\.(?:png|jpe?g|webp)$", re.I)


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def natural_key(name: str):
    return tuple((0, int(p)) if p.isdigit() else (1, p.casefold())
                 for p in re.split(r"(\d+)", name))


def validate_filename(name: str) -> str:
    if not name or len(name) > 240 or any(ord(c) < 32 or c in '/\\' for c in name):
        raise ValueError("Use plain image filenames without directory paths.")
    if name.startswith(".") or Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported image: {name}")
    return name


def normalize_image(data: bytes) -> tuple[bytes, bytes, int, int]:
    if not data or len(data) > MAX_FILE_BYTES:
        raise ValueError("Each image must be nonempty and at most 32 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as image:
                if image.format not in {"PNG", "JPEG", "WEBP"}:
                    raise ValueError("Only PNG, JPEG and WebP images are supported.")
                if getattr(image, "n_frames", 1) != 1:
                    raise ValueError("Animated images are not supported.")
                if image.width * image.height > MAX_PIXELS:
                    raise ValueError("Image exceeds the 24-megapixel limit.")
                image = ImageOps.exif_transpose(image).convert("RGB")
                image.load()
                width, height = image.size
                display = io.BytesIO()
                # Lossless PNG retains decoded pixels; metadata is intentionally not copied.
                image.save(display, format="PNG")
                image.thumbnail((180, 180))
                thumb = io.BytesIO()
                image.save(thumb, format="JPEG", quality=85)
                return display.getvalue(), thumb.getvalue(), width, height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombWarning,
            Image.DecompressionBombError) as exc:
        raise ValueError("Cannot decode image safely.") from exc


def read_galar_labels(path: Path) -> dict[int, dict[str, str | None]]:
    """Read official per-examination frame CSVs without inventing absent negatives.

    Schema is based on the authors' generate_folds.py: a `frame` integer column
    and named annotation columns. Unknown/blank values remain explicit.
    """
    rows = {}
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or "frame" not in reader.fieldnames:
            raise ValueError("Galar annotations need a 'frame' column.")
        if len(set(reader.fieldnames)) != len(reader.fieldnames):
            raise ValueError("Duplicate annotation columns.")
        for line, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Malformed CSV row {line}.")
            try:
                index = int(row["frame"])
            except (ValueError, TypeError) as exc:
                raise ValueError(f"Invalid frame index on CSV row {line}.") from exc
            if index < 0 or index in rows:
                raise ValueError(f"Duplicate or negative frame index on row {line}.")
            rows[index] = {
                k: (v.strip() if v and v.strip() else None)
                for k, v in row.items() if k != "frame" and not k.startswith("Unnamed:")
            }
    return rows


def import_sources(store: Store, sources: Iterable[tuple[str, bytes]], *, title: str,
                   source: str = "Local research images", synthetic: bool = False,
                   reference: dict | None = None) -> dict:
    title, source = title.strip(), source.strip()
    if not title or len(title) > 120 or len(source) > 300:
        raise ValueError("A title of 1–120 characters and source up to 300 characters are required.")
    study_id = uuid.uuid4().hex
    temporary = Path(tempfile.mkdtemp(prefix=".import-", dir=store.root))
    destination = store.images / study_id
    rows, names, indices = [], set(), set()
    try:
        for position, (filename, data) in enumerate(sources):
            filename = validate_filename(filename)
            if filename.casefold() in names:
                raise ValueError(f"Duplicate image filename: {filename}")
            names.add(filename.casefold())
            # Galar labels apply only to the frame_<index> source namespace.
            galar_match = FRAME_RE.match(filename)
            if reference is not None and not galar_match:
                raise ValueError('Galar reference annotations require frame_<index> filenames.')
            # The verified Rhode Island published export uses image-00007.png,
            # image-00008.png, ... . Numbering alone does not prove capture time.
            match = galar_match or PUBLISHED_IMAGE_RE.match(filename)
            source_index = int(match.group(1)) if match else None
            if source_index is not None:
                if source_index in indices:
                    raise ValueError("Duplicate numbered source frame.")
                indices.add(source_index)
            display, thumb, width, height = normalize_image(data)
            (temporary / f"{position}.png").write_bytes(display)
            (temporary / f"{position}.jpg").write_bytes(thumb)
            labels = reference.get(source_index, {}) if reference else {}
            rows.append((study_id, position, source_index, filename, sha256(data),
                         sha256(display), width, height, json.dumps(labels, ensure_ascii=False)))
        if not rows:
            raise ValueError("No supported image files were supplied.")
        identity = [{"position": r[1], "source_index": r[2], "filename": r[3],
                     "sha256": r[4]} for r in rows]
        manifest_sha = sha256(json.dumps(identity, sort_keys=True).encode())
        temporary.rename(destination)
        with store.connect() as db:
            db.execute("INSERT INTO studies VALUES(?,?,?,?,?,?,?,?)",
                       (study_id, title, source, int(synthetic), len(rows), manifest_sha, now(), 0))
            db.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?)", rows)
        return store.study(study_id)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        shutil.rmtree(destination, ignore_errors=True)
        raise


def import_folder(store: Store, path: Path, *, title: str, source: str,
                  labels: Path | None = None) -> dict:
    path = path.expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("The image path must be a folder.")
    paths = sorted([p for p in path.iterdir() if p.suffix.lower() in ALLOWED_EXTENSIONS],
                   key=lambda p: natural_key(p.name))
    if any(p.is_symlink() or not p.is_file() for p in paths):
        raise ValueError("Image files must be regular files, not symlinks or folders.")
    annotations = read_galar_labels(labels) if labels else None
    if annotations and any(not FRAME_RE.match(p.name) for p in paths):
        raise ValueError("Galar reference labels require frame_000001-style filenames.")
    def sources():
        for p in paths:
            if p.stat().st_size > MAX_FILE_BYTES:
                raise ValueError(f"Image too large: {p.name}")
            yield p.name, p.read_bytes()
    return import_sources(store, sources(), title=title, source=source, reference=annotations)


def create_demo(store: Store) -> dict:
    """Geometric, numbered test images: never simulated medical evidence."""
    def frames():
        for n in range(24):
            im = Image.new("RGB", (640, 480), "#102a36")
            d = ImageDraw.Draw(im)
            for x in range(0, 640, 40):
                d.line((x, 0, x, 480), fill="#1b3946")
            for y in range(0, 480, 40):
                d.line((0, y, 640, y), fill="#1b3946")
            cx, cy = 150 + n * 14, 225
            d.ellipse((cx - 60, cy - 60, cx + 60, cy + 60), fill="#4ec6bb")
            d.rectangle((20, 18, 620, 78), fill="#ebc36a")
            d.text((34, 34), "SYNTHETIC TEST FRAME - NOT CLINICAL DATA", fill="#142731", font_size=20)
            d.text((30, 385), f"Frame {n + 1:02d} / 24", fill="white", font_size=30)
            d.text((30, 436), "Use this sequence to test navigation, notes and export.", fill="#bed0d4", font_size=16)
            buf = io.BytesIO()
            im.save(buf, format="PNG")
            yield f"frame_{n:06d}.PNG", buf.getvalue()
    return import_sources(store, frames(), title="Test sequence", source="Generated software-test images",
                          synthetic=True)
