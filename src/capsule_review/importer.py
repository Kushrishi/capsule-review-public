"""Import numbered images, preserving source identity and optional Galar labels."""

import csv
import hashlib
import io
import errno
import os
import sqlite3
import stat
import json
import re
import shutil
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


class ImportCancelled(ValueError):
    """Import cancelled before the examination became visible."""


def _check_cancel(cancelled):
    if cancelled and cancelled():
        raise ImportCancelled('Import cancelled. No examination was added.')


def _remove_import_metadata(folder):
    for name in ('.import.sqlite3', '.import.sqlite3-journal', '.import-pending'):
        (folder / name).unlink(missing_ok=True)


def recover_interrupted_imports(store):
    """Desktop-lock owner only: clean marked imports; preserve committed studies.

    Never remove legacy/unmarked paths, links, source files or completed frames.
    """
    recovered = 0
    for parent, pattern in ((store.root, '.import-*'), (store.images, '*')):
        for folder in parent.glob(pattern):
            study_id = folder.name.removeprefix('.import-') if parent == store.root else folder.name
            if not re.fullmatch(r'[0-9a-f]{32}', study_id) or folder.is_symlink() or not folder.is_dir():
                continue
            marker = folder / '.import-pending'
            if marker.is_symlink() or not marker.is_file() or marker.stat().st_size != 32:
                continue
            if marker.read_text() != study_id:
                continue
            if parent == store.images and store.study(study_id):
                _remove_import_metadata(folder)
            else:
                shutil.rmtree(folder)
                recovered += 1
    return recovered


def import_sources(store: Store, sources: Iterable[tuple[str, bytes]], *, title: str,
                   source: str = "Local research images", synthetic: bool = False,
                   reference: dict | None = None, progress=None, cancelled=None,
                   total: int | None = None) -> dict:
    title, source = title.strip(), source.strip()
    if not title or len(title) > 120 or len(source) > 300:
        raise ValueError("A title of 1–120 characters and source up to 300 characters are required.")
    _check_cancel(cancelled)
    study_id = uuid.uuid4().hex
    temporary = store.root / ('.import-' + study_id)
    destination = store.images / study_id
    temporary.mkdir(mode=0o700)
    metadata = None
    published = False
    count = source_bytes = output_bytes = 0
    identity = hashlib.sha256(b'[')
    try:
        (temporary / '.import-pending').write_text(study_id)
        metadata = sqlite3.connect(temporary / '.import.sqlite3')
        metadata.execute('CREATE TABLE frames (study_id TEXT, position INTEGER PRIMARY KEY, '
                         'source_index INTEGER UNIQUE, filename TEXT, source_sha256 TEXT, '
                         'display_sha256 TEXT, width INTEGER, height INTEGER, reference_labels TEXT, '
                         'folded_name TEXT UNIQUE)')
        if progress:
            progress({'phase': 'importing', 'completed': 0, 'total': total})
        for position, (filename, data) in enumerate(sources):
            _check_cancel(cancelled)
            filename = validate_filename(filename)
            if metadata.execute('SELECT 1 FROM frames WHERE folded_name=?', (filename.casefold(),)).fetchone():
                raise ValueError(f"Duplicate image filename: {filename}")
            galar_match = FRAME_RE.match(filename)
            if reference is not None and not galar_match:
                raise ValueError('Galar reference annotations require frame_<index> filenames.')
            match = galar_match or PUBLISHED_IMAGE_RE.match(filename)
            source_index = int(match.group(1)) if match else None
            if source_index is not None and metadata.execute(
                    'SELECT 1 FROM frames WHERE source_index=?', (source_index,)).fetchone():
                raise ValueError("Duplicate numbered source frame.")
            try:
                display, thumb, width, height = normalize_image(data)
            except ValueError as exc:
                raise ValueError(f'{filename}: {exc}') from exc
            _check_cancel(cancelled)
            needed = len(display) + len(thumb) + 16 * 1024**2
            if shutil.disk_usage(store.root).free < needed:
                raise OSError(errno.ENOSPC, 'Not enough free workspace space to import the next frame safely.')
            (temporary / f"{position}.png").write_bytes(display)
            (temporary / f"{position}.jpg").write_bytes(thumb)
            labels = reference.get(source_index, {}) if reference else {}
            source_hash = sha256(data)
            metadata.execute('INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?,?)',
                (study_id, position, source_index, filename, source_hash, sha256(display),
                 width, height, json.dumps(labels, ensure_ascii=False), filename.casefold()))
            # Byte-for-byte equivalent to the previous json.dumps(list, sort_keys=True),
            # without retaining rows or the manifest list in Python memory.
            if count:
                identity.update(b', ')
            identity.update(json.dumps({'position': position, 'source_index': source_index,
                                       'filename': filename, 'sha256': source_hash}, sort_keys=True).encode())
            count += 1
            source_bytes += len(data)
            output_bytes += len(display) + len(thumb)
            if progress:
                progress({'phase': 'importing', 'completed': count, 'total': total,
                          'source_bytes': source_bytes, 'output_bytes': output_bytes, 'filename': filename})
        _check_cancel(cancelled)
        if not count:
            raise ValueError("No supported image files were supplied.")
        identity.update(b']')
        metadata.commit()
        # The progress consumer can atomically reject cancellation or enter the
        # short, uncancellable publication transaction. Nothing is visible yet.
        if progress:
            progress({'phase': 'committing', 'completed': count, 'total': count})
        metadata.close()
        metadata = None
        temporary.rename(destination)
        metadata = sqlite3.connect(destination / '.import.sqlite3')
        created_at = now()
        with store.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            db.execute("INSERT INTO studies VALUES(?,?,?,?,?,?,?,?)",
                       (study_id, title, source, int(synthetic), count, identity.hexdigest(), created_at, 0))
            rows = metadata.execute('SELECT study_id,position,source_index,filename,source_sha256,'
                                    'display_sha256,width,height,reference_labels FROM frames ORDER BY position')
            db.executemany("INSERT INTO frames VALUES(?,?,?,?,?,?,?,?,?)", rows)
        published = True
        metadata.close()
        metadata = None
        try:
            _remove_import_metadata(destination)
        except OSError:
            pass  # Recovery removes only these marked metadata files on reopen.
        return {'id': study_id, 'title': title, 'source': source, 'synthetic': bool(synthetic),
                'frame_count': count, 'manifest_sha256': identity.hexdigest(), 'created_at': created_at,
                'last_position': 0, 'bookmark_count': 0, 'runs': []}
    finally:
        if metadata:
            metadata.close()
        if not published:
            shutil.rmtree(temporary, ignore_errors=True)
            shutil.rmtree(destination, ignore_errors=True)


def _file_identity(info):
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def _read_folder_image(path, expected):
    """Bound the read and reject replaced files/links, including scan/open races."""
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    with os.fdopen(os.open(path, flags), 'rb') as handle:
        before = os.fstat(handle.fileno())
        if not stat.S_ISREG(before.st_mode) or _file_identity(before) != expected or path.is_symlink():
            raise ValueError(f'Source file changed since folder scan: {path.name}')
        data = handle.read(MAX_FILE_BYTES + 1)
        if (_file_identity(os.fstat(handle.fileno())) != expected or
                _file_identity(path.lstat()) != expected or path.is_symlink()):
            raise ValueError(f'Source file changed during import: {path.name}')
    if len(data) > MAX_FILE_BYTES:
        raise ValueError(f'Image too large: {path.name}')
    return data


def import_folder(store: Store, path: Path, *, title: str, source: str,
                  labels: Path | None = None, progress=None, cancelled=None,
                  max_files: int | None = None) -> dict:
    path = path.expanduser().resolve(strict=True)
    if not path.is_dir():
        raise ValueError("The image path must be a folder.")
    paths, ignored, scanned = [], 0, 0
    if progress:
        progress({'phase': 'scanning', 'completed': 0, 'total': None, 'ignored_files': 0})
    with os.scandir(path) as entries:
        for item in entries:
            entry = Path(item.path)
            _check_cancel(cancelled)
            scanned += 1
            if entry.suffix.lower() not in ALLOWED_EXTENSIONS:
                ignored += 1
            else:
                info = entry.lstat()
                if not stat.S_ISREG(info.st_mode):
                    raise ValueError("Image files must be regular files, not symlinks or folders.")
                validate_filename(entry.name)
                if info.st_size > MAX_FILE_BYTES:
                    raise ValueError(f'Image too large: {entry.name}')
                paths.append((entry, _file_identity(info)))
                if max_files is not None and len(paths) > max_files:
                    raise ValueError(f'Desktop folder import supports at most {max_files:,} images per examination.')
            if progress and scanned % 128 == 0:
                progress({'phase': 'scanning', 'scanned_entries': scanned, 'ignored_files': ignored})
    paths.sort(key=lambda item: (natural_key(item[0].name), item[0].name))
    annotations = read_galar_labels(labels) if labels else None
    if annotations and any(not FRAME_RE.match(p.name) for p, _ in paths):
        raise ValueError('Galar reference labels require frame_000001-style filenames.')
    if progress:
        progress({'phase': 'scanning', 'scanned_entries': scanned, 'ignored_files': ignored})
    def sources():
        for p, expected in paths:
            _check_cancel(cancelled)
            yield p.name, _read_folder_image(p, expected)
    return import_sources(store, sources(), title=title, source=source, reference=annotations,
                          progress=progress, cancelled=cancelled, total=len(paths))


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
