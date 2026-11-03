"""Bounded HTTP-Range inspection of the official Galar 21–29 solid 7z archive.

This is a metadata-only technical probe. It NEVER requests image compressed data,
never makes a full-file request, and refuses 200 OK before reading its body.
The resulting sparse metadata file is logical-archive-sized but consumes only
index space on a sparse-capable filesystem; it is never uploaded or committed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import urllib.request
from urllib.parse import urlparse
import zlib

FILE_ID = 45258019
ARCHIVE_SIZE = 31_989_399_751
SOURCE_URL = f'https://ndownloader.figshare.com/files/{FILE_ID}'
EXPECTED_FULL_MD5 = 'dedad47ee55c83a4b991ca60d26fb6ee'
MAX_TRANSFER = 8 * 1024 * 1024
SIGNATURE = b'7z\xbc\xaf\x27\x1c'
ALLOWED_REDIRECT_HOSTS = frozenset({'ndownloader.figshare.com', 'figshare.com', 'api.figshare.com'})


def allowed_redirect(url: str) -> bool:
    p = urlparse(url)
    name = (p.hostname or '').lower()
    return (p.scheme == 'https' and p.username is None and p.password is None
            and p.port in (None, 443)
            and (name in ALLOWED_REDIRECT_HOSTS
                 or name.endswith('.amazonaws.com')
                 or name.endswith('.figshare.com')
                 or name.endswith('.figstatic.com')))


def unpack_int(data: bytes, pos: int) -> tuple[int, int]:
    """Read a 7z unsigned variable-length integer without undefined shifts."""
    if pos >= len(data):
        raise ValueError('Truncated 7z integer.')
    first = data[pos]
    pos += 1
    mask = 0x80
    value = 0
    for index in range(8):
        if not first & mask:
            return value | ((first & (mask - 1)) << (8 * index)), pos
        if pos >= len(data):
            raise ValueError('Truncated 7z integer payload.')
        value |= data[pos] << (8 * index)
        pos += 1
        mask >>= 1
    return value, pos


class RangeClient:
    """Account exact HTTP bytes at the remote official source, fail closed."""

    def __init__(self, url: str, size: int, cap: int = MAX_TRANSFER, *, allow_test_http=False):
        if not allow_test_http and (url != SOURCE_URL or size != ARCHIVE_SIZE):
            raise ValueError('Only official Galar 21–29 source URL and size are accepted.')
        if cap <= 0 or cap > MAX_TRANSFER:
            raise ValueError('Metadata transfer cap must not exceed 8 MiB.')
        self.url = url
        self.size = size
        self.cap = cap
        self.total = 0
        self.allow_test_http = allow_test_http

    def read(self, start: int, length: int) -> bytes:
        if (start < 0 or length <= 0 or start > self.size - length
                or self.total + length > self.cap):
            raise ValueError('Metadata range outside source or total transfer cap.')
        end = start + length - 1
        request = urllib.request.Request(self.url, headers={
            'Range': f'bytes={start}-{end}',
            'Accept-Encoding': 'identity',
            'User-Agent': 'capsule-review/0.2 Galar 7z index-only verification'})
        with urllib.request.urlopen(request, timeout=60) as response:
            if response.status != 206:
                raise ValueError(f'Required HTTP 206; got {response.status}. Stopped before body.')
            if (not self.allow_test_http and not allowed_redirect(response.geturl())):
                raise ValueError('Untrusted redirect host or scheme.')
            expected = f'bytes {start}-{end}/{self.size}'
            if response.headers.get('Content-Range') != expected:
                raise ValueError('Content-Range mismatch; possible source mutation.')
            if response.headers.get('Content-Encoding', 'identity') != 'identity':
                raise ValueError('Unexpected response content encoding.')
            declared = response.headers.get('Content-Length')
            if declared is not None and (not declared.isdecimal() or int(declared) != length):
                raise ValueError('Unexpected Content-Length.')
            data = response.read(length + 1)
        self.total += len(data)
        if len(data) != length:
            raise ValueError('Incomplete or oversized HTTP Range response.')
        return data


def encoded_header_streams(next_header: bytes, total_size: int) -> list[tuple[int, int]]:
    """Return index-only compressed streams; refuse unfamiliar layouts.

    7z EncodedHeader (0x17) -> PackInfo (0x06), PackPos, NumPackStreams,
    Size (0x09) and one size per compressed index stream. No image streams.
    """
    if not next_header or next_header[0] not in (1, 0x17):
        raise ValueError('Unknown 7z NextHeader type.')
    if next_header[0] == 1:
        return []
    if len(next_header) < 3 or next_header[1] != 0x06:
        raise ValueError('Unsupported encoded-header format; no image request.')
    pos = 2
    packed_offset, pos = unpack_int(next_header, pos)
    count, pos = unpack_int(next_header, pos)
    if count < 1 or count > 4 or pos >= len(next_header) or next_header[pos] != 0x09:
        raise ValueError('Invalid compressed-index PackInfo.')
    pos += 1
    cursor = 32 + packed_offset
    ranges = []
    for _ in range(count):
        length, pos = unpack_int(next_header, pos)
        if length < 1 or length > MAX_TRANSFER or cursor > total_size - length:
            raise ValueError('Compressed header size outside safe bounds.')
        ranges.append((cursor, length))
        cursor += length
    return ranges


def inspect(client: RangeClient, destination: Path, *, sparse_path: Path | None = None) -> dict:
    """Save index-only parts; optionally create a sparse file for `7z l`.

    Destination must be a new private directory; never write raw image bytes.
    """
    if destination.exists():
        raise FileExistsError('Index destination exists; refuse to overwrite.')
    destination.mkdir(parents=True, exist_ok=False)
    parts = []

    def acquire(name: str, start: int, count: int) -> bytes:
        data = client.read(start, count)
        (destination / name).write_bytes(data)
        parts.append({'name': name, 'offset': start, 'length': len(data),
                      'sha256': hashlib.sha256(data).hexdigest()})
        return data

    header = acquire('signature-header.bin', 0, 32)
    if header[:6] != SIGNATURE or header[6] != 0:
        raise ValueError('Unexpected 7z signature/version.')
    if zlib.crc32(header[12:32]) != struct.unpack_from('<I', header, 8)[0]:
        raise ValueError('Corrupted 7z start header CRC.')
    next_offset, next_size, next_crc = struct.unpack_from('<QQI', header, 12)
    if next_size < 1 or next_size > client.cap - client.total:
        raise ValueError('NextHeader too large for remaining metadata budget.')
    if next_offset > client.size - 32 - next_size:
        raise ValueError('NextHeader lies outside full archive.')
    next_header = acquire('next-header.bin', 32 + next_offset, next_size)
    if zlib.crc32(next_header) != next_crc:
        raise ValueError('Corrupted 7z NextHeader CRC.')
    for i, (start, size) in enumerate(encoded_header_streams(next_header, client.size)):
        acquire(f'encoded-index-{i}.bin', start, size)

    receipt = {
        'record_type': 'galar-21-29-7z-index-only-v1',
        'official_file_id': FILE_ID if client.url == SOURCE_URL else None,
        'official_full_archive_bytes': client.size,
        'official_full_archive_md5_expected_not_verified': EXPECTED_FULL_MD5 if client.url == SOURCE_URL else None,
        'actual_index_only_bytes_transferred': client.total,
        'full_archive_downloaded': False,
        'pixels_acquired': 0,
        'parts': parts,
        'next_header_type': 'encoded' if next_header[0] == 0x17 else 'plain',
        'next_header_location': [32 + next_offset, next_size],
        'no_automatic_large_transfer': True,
    }
    (destination / 'receipt.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n', encoding='utf8')
    if sparse_path is not None:
        if sparse_path.exists():
            raise FileExistsError('Sparse index file exists; refuse to overwrite.')
        if sparse_path.parent != destination:
            raise ValueError('Sparse archive must remain inside index staging directory.')
        with sparse_path.open('xb') as f:
            f.truncate(client.size)
            for part in parts:
                with (destination / part['name']).open('rb') as pf:
                    f.seek(part['offset'])
                    f.write(pf.read())
    return receipt


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--destination', type=Path, required=True, help='New directory; metadata only.')
    ap.add_argument('--sparse', action='store_true', help='Create a sparse 31.99-GB *logical* archive file, with only verified header bytes.')
    args = ap.parse_args()
    client = RangeClient(SOURCE_URL, ARCHIVE_SIZE)
    report = inspect(client, args.destination, sparse_path=(args.destination / 'headers-only.7z') if args.sparse else None)
    print('Verified official 7z header CRCs and strict HTTP byte ranges.')
    print(json.dumps({k: v for k, v in report.items() if k not in {'parts'}}))


if __name__ == '__main__':
    main()