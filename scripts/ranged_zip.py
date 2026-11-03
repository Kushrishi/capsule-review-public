"""Bounded, HTTP-Range-only inspection/extraction of individual ZIP members.

This tool is for research-data *access feasibility*. It never falls back to a full
archive transfer. Use only source repositories and images you are permitted to use.
"""
from __future__ import annotations

import argparse
from hashlib import sha256
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile, ZipInfo

_MIB = 1024 * 1024
_CONTENT_RANGE = re.compile(r"\Abytes (\d+)-(\d+)/(\d+)\Z")
_MAX_ARCHIVE_SIZE = 50 * 1024 * 1024 * 1024


class AcquisitionError(RuntimeError):
    """Acquisition was refused because its access or integrity gate failed."""


class HTTPRangeReader:
    """Seekable read-only file backed by exact, bounded HTTP 206 byte ranges.

    No normal GET, HTTP 200 fallback, or unbounded response-body reads are used.
    A single small read-ahead window avoids one HTTP request per ZIP stream chunk.
    """

    def __init__(self, url: str, *, max_transfer_bytes: int = 128 * _MIB,
                 read_ahead_bytes: int = _MIB, timeout: float = 25.0,
                 allow_http_for_tests: bool = False):
        parsed = urlsplit(url)
        valid_scheme = parsed.scheme == "https" or (allow_http_for_tests and parsed.scheme == "http")
        if not valid_scheme or not parsed.netloc or parsed.username or parsed.password or parsed.fragment:
            raise AcquisitionError("Use an HTTPS dataset download URL without credentials or fragment")
        if not 1 <= max_transfer_bytes <= 512 * _MIB:
            raise AcquisitionError("Transfer cap must be between 1 byte and 512 MiB")
        if not 1 <= read_ahead_bytes <= 2 * _MIB:
            raise AcquisitionError("Read-ahead must be between 1 byte and 2 MiB")
        self.url = url
        self.max_transfer_bytes = max_transfer_bytes
        self.read_ahead_bytes = read_ahead_bytes
        self.timeout = timeout
        self.allow_http_for_tests = allow_http_for_tests
        self.transferred_bytes = 0
        self.request_count = 0
        self._cache_start = -1
        self._cache = b""
        self._pos = 0
        self.closed = False
        self.size = 0
        # A one-byte probe learns the real archive size; do NOT use a normal GET.
        self._cache = self._fetch(0, 0, initial=True)
        self._cache_start = 0

    def _fetch(self, start: int, end: int, *, initial: bool = False) -> bytes:
        requested = end - start + 1
        if start < 0 or requested < 1 or requested > 2 * _MIB:
            raise AcquisitionError("Invalid or oversized remote range request")
        if requested > self.max_transfer_bytes - self.transferred_bytes:
            raise AcquisitionError("Remote transfer would exceed the byte budget")
        req = Request(self.url, headers={
            "Range": f"bytes={start}-{end}",
            "Accept-Encoding": "identity",
            "User-Agent": "CapsuleReviewResearch/0.2 (range-only)",
        })
        try:
            with urlopen(req, timeout=self.timeout) as response:
                self.request_count += 1
                final = urlsplit(response.geturl())
                if final.scheme != "https" and not (self.allow_http_for_tests and final.scheme == "http"):
                    raise AcquisitionError("Unsafe redirect scheme")
                if response.status != 206:
                    # Crucial: reject HTTP 200 BEFORE reading its 3+ GB body.
                    raise AcquisitionError(f"Server returned HTTP {response.status}, not 206; no full-download fallback")
                if response.headers.get("Content-Encoding", "identity").lower() not in ("identity", ""):
                    raise AcquisitionError("Range response was transformed by HTTP content encoding")
                match = _CONTENT_RANGE.fullmatch(response.headers.get("Content-Range", ""))
                if not match:
                    raise AcquisitionError("Missing or malformed Content-Range")
                actual_start, actual_end, total = map(int, match.groups())
                if total > _MAX_ARCHIVE_SIZE or total < 22:
                    raise AcquisitionError("Remote ZIP size is outside the allowed bounds")
                if (actual_start, actual_end) != (start, end) or actual_end >= total:
                    raise AcquisitionError("Server delivered an unexpected byte range")
                if not initial and total != self.size:
                    raise AcquisitionError("Remote archive length changed mid-read")
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) != requested:
                    raise AcquisitionError("Unexpected Content-Length")
                data = response.read(requested + 1)
        except AcquisitionError:
            raise
        except (OSError, ValueError) as exc:
            raise AcquisitionError(f"Range request failed: {exc}") from exc
        if len(data) != requested:
            raise AcquisitionError("Remote range returned truncated or extra bytes")
        self.transferred_bytes += len(data)
        if initial:
            self.size = total
        return data

    def read(self, length: int = -1) -> bytes:
        if self.closed:
            raise ValueError("I/O operation on closed reader")
        remaining = self.size - self._pos
        if remaining <= 0:
            return b""
        if length is None or length < 0:
            if remaining > self.read_ahead_bytes:
                raise AcquisitionError("Unbounded remote read refused")
            length = remaining
        length = min(length, remaining)
        parts = []
        while length:
            offset = self._pos - self._cache_start
            available = len(self._cache) - offset if offset >= 0 else 0
            if available <= 0:
                # Bounded read-ahead: never request beyond the end of archive.
                take = min(max(min(length, 2 * _MIB), self.read_ahead_bytes),
                           2 * _MIB, self.size - self._pos,
                           self.max_transfer_bytes - self.transferred_bytes)
                if take < 1:
                    raise AcquisitionError("Remote transfer would exceed the byte budget")
                self._cache = self._fetch(self._pos, self._pos + take - 1)
                self._cache_start = self._pos
                offset, available = 0, len(self._cache)
            take = min(available, length)
            parts.append(self._cache[offset:offset + take])
            self._pos += take
            length -= take
        return b"".join(parts)

    def tell(self) -> int:
        return self._pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if self.closed:
            raise ValueError("I/O operation on closed reader")
        if whence == io.SEEK_SET:
            new_pos = offset
        elif whence == io.SEEK_CUR:
            new_pos = self._pos + offset
        elif whence == io.SEEK_END:
            new_pos = self.size + offset
        else:
            raise ValueError("Unknown seek mode")
        if not 0 <= new_pos <= self.size:
            raise AcquisitionError("Seek beyond ZIP boundaries")
        self._pos = new_pos
        return new_pos

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def close(self) -> None:
        self.closed = True
        self._cache = b""

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


def _safe_member(info: ZipInfo) -> str:
    raw = info.filename
    name = PurePosixPath(raw)
    permissions = info.external_attr >> 16
    if (not raw or "\\" in raw or "\x00" in raw or name.is_absolute()
            or any(part in ("", ".", "..") for part in raw.split("/"))
            or name.name in ("", ".", "..") or ":" in name.parts[0]
            or info.is_dir() or stat.S_ISLNK(permissions)):
        raise AcquisitionError(f"Unsafe archive member path or file type: {raw!r}")
    if info.flag_bits & 1:
        raise AcquisitionError(f"Encrypted archive member: {raw!r}")
    return name.name


def _index_members(zf: ZipFile) -> list[ZipInfo]:
    infos = zf.infolist()
    names = [info.filename for info in infos]
    if len(names) > 100_000 or len(set(names)) != len(names):
        raise AcquisitionError("ZIP index has too many or duplicate member paths")
    return infos


def _choose(zf: ZipFile, selected: list[str], max_file_bytes: int) -> list[tuple[ZipInfo, str]]:
    if not selected or len(selected) != len(set(selected)):
        raise AcquisitionError("Select one or more distinct exact member names")
    names = {info.filename: info for info in _index_members(zf)}
    result = []
    used_basenames = set()
    for name in selected:
        if name not in names:
            raise AcquisitionError(f"Member not found: {name}")
        info = names[name]
        base = _safe_member(info)
        if base in used_basenames:
            raise AcquisitionError(f"Duplicate output filename: {base}")
        used_basenames.add(base)
        if info.file_size > max_file_bytes:
            raise AcquisitionError(f"Uncompressed member exceeds size cap: {name}")
        if info.compress_size == 0 and info.file_size:
            raise AcquisitionError(f"Member has impossible compressed size: {name}")
        if info.file_size > max(info.compress_size, 1) * 200:
            raise AcquisitionError(f"Suspected decompression bomb: {name}")
        result.append((info, base))
    return result


def inspect(url: str, *, max_transfer_bytes: int = 128 * _MIB,
            match: str = "", allow_http_for_tests: bool = False) -> dict:
    with HTTPRangeReader(url, max_transfer_bytes=max_transfer_bytes,
                         allow_http_for_tests=allow_http_for_tests) as reader:
        with ZipFile(reader, "r", allowZip64=True) as archive:
            matches = [info for info in _index_members(archive) if match.lower() in info.filename.lower()]
            entries = [{"name": info.filename, "size_bytes": info.file_size,
                        "compressed_bytes": info.compress_size, "crc32": f"{info.CRC:08x}"}
                       for info in matches]
        return {"url": url, "archive_bytes": reader.size, "matched_members": len(entries),
                "members": entries, "transferred_bytes": reader.transferred_bytes,
                "requests": reader.request_count, "source_identity": "size only; not full-file checksum verified"}


def extract(url: str, selected: list[str], dest: Path, *,
            max_transfer_bytes: int = 128 * _MIB,
            max_file_bytes: int = 128 * _MIB,
            allow_http_for_tests: bool = False) -> dict:
    if not 1 <= max_file_bytes <= 512 * _MIB:
        raise AcquisitionError("Member extraction cap must be 1 byte to 512 MiB")
    with HTTPRangeReader(url, max_transfer_bytes=max_transfer_bytes,
                         allow_http_for_tests=allow_http_for_tests) as reader:
        with ZipFile(reader, "r", allowZip64=True) as archive:
            chosen = _choose(archive, selected, max_file_bytes)
            if sum(info.file_size for info, _ in chosen) > 512 * _MIB:
                raise AcquisitionError("Selected uncompressed output exceeds 512 MiB")
            # Verify every destination before writing anything, including symlink parents.
            if dest.exists() and (not dest.is_dir() or dest.is_symlink()):
                raise AcquisitionError("Output directory is not a safe ordinary directory")
            dest.mkdir(parents=True, exist_ok=True)
            output_dir = dest.resolve(strict=True)
            for _, basename in chosen:
                target = dest / basename
                if target.exists() or target.is_symlink() or target.parent.resolve() != output_dir:
                    raise AcquisitionError(f"Destination exists or escapes directory: {target}")
            results = []
            # Verify *all* selected members before publishing any final output.
            with tempfile.TemporaryDirectory(prefix=".ranged-zip-", dir=dest) as stage:
                for info, basename in chosen:
                    digest = sha256()
                    total = 0
                    with (Path(stage) / basename).open("xb") as out:
                        with archive.open(info, "r") as member:
                            while True:
                                chunk = member.read(min(_MIB, max_file_bytes + 1 - total))
                                if not chunk:
                                    break
                                total += len(chunk)
                                if total > info.file_size or total > max_file_bytes:
                                    raise AcquisitionError(f"Extracted member grew beyond cap: {basename}")
                                out.write(chunk)
                                digest.update(chunk)
                    if total != info.file_size:
                        raise AcquisitionError(f"Uncompressed size mismatch: {basename}")
                    results.append({"member": info.filename, "file": basename,
                                    "bytes": total, "sha256": digest.hexdigest(),
                                    "source_crc32": f"{info.CRC:08x}"})
                for _, basename in chosen:
                    if (dest / basename).exists() or (dest / basename).is_symlink():
                        raise AcquisitionError(f"Destination changed during extraction: {basename}")
                for _, basename in chosen:
                    os.replace(Path(stage) / basename, dest / basename)
        return {"url": url, "archive_bytes": reader.size,
                "source_identity": "archive length and per-member CRC; full archive checksum not verified",
                "transferred_bytes": reader.transferred_bytes,
                "requests": reader.request_count, "extracted": results}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", help="HTTPS ZIP download URL from the official dataset publisher")
    parser.add_argument("--max-transfer-mib", type=int, default=128,
                        help="Remote byte cap; 128 MiB by default, hard maximum 512")
    sub = parser.add_subparsers(dest="command", required=True)
    p_list = sub.add_parser("list", help="Read ZIP central directory only")
    p_list.add_argument("--match", default="", help="Optional case-insensitive member-name substring")
    p_get = sub.add_parser("extract", help="Download explicitly selected, small ZIP members only")
    p_get.add_argument("--member", required=True, action="append", help="Exact ZIP member path; repeatable")
    p_get.add_argument("--output-dir", required=True, type=Path)
    p_get.add_argument("--max-member-mib", type=int, default=128)
    args = parser.parse_args(argv)
    if not 1 <= args.max_transfer_mib <= 512:
        parser.error("--max-transfer-mib must be between 1 and 512")
    try:
        if args.command == "list":
            result = inspect(args.url, max_transfer_bytes=args.max_transfer_mib * _MIB,
                             match=args.match)
        else:
            result = extract(args.url, args.member, args.output_dir,
                             max_transfer_bytes=args.max_transfer_mib * _MIB,
                             max_file_bytes=args.max_member_mib * _MIB)
    except (AcquisitionError, BadZipFile, OSError, NotImplementedError) as exc:
        print(f"Range-only dataset access stopped: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
