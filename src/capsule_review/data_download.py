"""Inspect and download explicitly selected files from the official Galar record.

Never downloads an article-sized bundle. Files are selected by ID, byte-limited,
verified against the published MD5, then recorded with a local SHA-256.
"""

import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from .baseline_data import digest

ARTICLE_ID = 25304616
API = f'https://api.figshare.com/v2/articles/{ARTICLE_ID}'


def get_catalog(output: Path) -> dict:
    if output.exists():
        raise ValueError('Catalog file exists. Choose a new filename to preserve the previous release record.')
    request = Request(API, headers={'User-Agent': 'capsule-review/0.2 research data inspection'})
    with urlopen(request, timeout=30) as response:
        raw = response.read(8 * 1024 * 1024 + 1)
    if len(raw) > 8 * 1024 * 1024:
        raise ValueError('Unexpected metadata response size.')
    metadata = json.loads(raw)
    validate_catalog(metadata)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8') as handle:
        json.dump(metadata, handle, indent=2, allow_nan=False)
    return metadata


def validate_catalog(metadata: dict):
    if metadata.get('id') != ARTICLE_ID or not isinstance(metadata.get('files'), list):
        raise ValueError('Not an official Galar article metadata record.')
    if not isinstance(metadata.get('version'), int) or metadata['version'] < 2:
        raise ValueError('Use Galar version 2 or later, including the corrected annotations.')
    ids = [f.get('id') for f in metadata['files']]
    if len(set(ids)) != len(ids) or any(type(x) is not int or x <= 0 for x in ids):
        raise ValueError('Invalid or duplicate file IDs in catalog.')


def download_file(metadata: dict, file_id: int, destination: Path, *, max_bytes: int = 512 * 1024 * 1024) -> dict:
    validate_catalog(metadata)
    if max_bytes <= 0:
        raise ValueError('Download budget must be positive.')
    matches = [item for item in metadata['files'] if item['id'] == file_id]
    if len(matches) != 1:
        raise ValueError('File ID is not in this Galar release.')
    item = matches[0]
    size, name = item.get('size'), item.get('name', '')
    if type(size) is not int or not 0 < size <= max_bytes:
        raise ValueError(f'This file exceeds the download budget ({max_bytes} bytes) or has an invalid size.')
    if not name or name in {'.', '..'} or any(c in name for c in '/\\') or any(ord(c) < 32 for c in name):
        raise ValueError('Unsafe source filename.')
    expected_md5 = item.get('computed_md5') or item.get('supplied_md5')
    if not isinstance(expected_md5, str) or not re.fullmatch(r'[a-fA-F0-9]{32}', expected_md5):
        raise ValueError('The catalog does not provide a usable upstream checksum.')
    url = item.get('download_url', '')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port not in {None, 443}:
        raise ValueError('Only official HTTPS file URLs are accepted.')
    if parsed.hostname not in {'ndownloader.figshare.com', 'api.figshare.com', 'figshare.com', 'plus.figshare.com'}:
        raise ValueError('Unexpected download host; inspect the official metadata before proceeding.')
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / name
    receipt = destination / f'{name}.source.json'
    temporary = destination / f'.{file_id}.partial'
    if any(p.exists() for p in [target, receipt, temporary]):
        raise ValueError('Download or source record already exists; nothing was overwritten.')
    total, md5, sha = 0, hashlib.md5(usedforsecurity=False), hashlib.sha256()
    try:
        with urlopen(Request(url, headers={'User-Agent': 'capsule-review/0.2'}), timeout=45) as response:
            final = urlsplit(response.geturl())
            host = final.hostname or ''
            if final.scheme != 'https' or not (host.endswith('.figshare.com') or host.endswith('.amazonaws.com')
                                              or host.endswith('.figstatic.com') or host == 'figshare.com'):
                raise ValueError('Unexpected file redirect host.')
            with temporary.open('xb') as handle:
                while chunk := response.read(1024 * 1024):
                    total += len(chunk)
                    if total > size or total > max_bytes:
                        raise ValueError('Download exceeded its declared size or budget.')
                    handle.write(chunk)
                    md5.update(chunk)
                    sha.update(chunk)
        if total != size or md5.hexdigest().lower() != expected_md5.lower():
            raise ValueError('Download size/checksum mismatch; incomplete data discarded.')
        record = {'article_id': ARTICLE_ID, 'version': metadata['version'], 'file_id': file_id,
                  'filename': name, 'bytes': total, 'upstream_md5': md5.hexdigest(),
                  'sha256': sha.hexdigest(), 'source_url': url, 'license': metadata.get('license'),
                  'doi': metadata.get('doi'), 'authors': metadata.get('authors', []),
                  'metadata_sha256': digest(json.dumps(metadata, sort_keys=True).encode())}
        temporary.rename(target)
        with receipt.open('x', encoding='utf-8') as handle:
            json.dump(record, handle, indent=2, allow_nan=False)
        return record
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
