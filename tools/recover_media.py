"""Operator-run HTTPS recovery client. Prompts for token; never stores it."""
import argparse
import getpass
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import re
import sys
from urllib.error import HTTPError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener

from PIL import Image


MAX_BYTES = 25 * 1024 * 1024


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Redirect refused; bearer credentials were not forwarded')


def safe_destination(root, key):
    if (not isinstance(key, str) or not key or len(key) > 512
            or PurePosixPath(key).is_absolute() or '\\' in key or ':' in key
            or any(part in {'', '.', '..'} for part in key.split('/'))):
        raise ValueError('Unsafe image key')
    destination = (root / key).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ValueError('Image key escapes the backup directory')
    return destination


def save_original(root, row, payload):
    if len(payload) > MAX_BYTES or len(payload) != row['bytes']:
        raise ValueError('Image byte count mismatch')
    if hashlib.sha256(payload).hexdigest() != row['sha256']:
        raise ValueError('Image digest mismatch; no file was written')
    Image.open(BytesIO(payload)).verify()
    destination = safe_destination(root, row['key'])
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        if hashlib.sha256(destination.read_bytes()).hexdigest() == row['sha256']:
            return 'existing_identical'
        return 'conflict_not_overwritten'
    # Exclusive creation also protects a concurrent writer after exists().
    with destination.open('xb') as handle:
        handle.write(payload)
    return 'saved_verified'


def fetch(opener, origin, path, token, limit):
    request = Request(origin + path, headers={'Authorization': 'Bearer ' + token})
    try:
        with opener.open(request, timeout=90) as response:
            if response.status != 200:
                raise RuntimeError('Recovery returned non-200 status')
            body = response.read(limit + 1)
            if len(body) > limit:
                raise RuntimeError('Recovery response exceeds size limit')
            return body
    except HTTPError as exc:
        # Never print request/response bodies, headers, or exception URLs.
        raise RuntimeError('Recovery HTTP ' + str(exc.code)) from None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origin', required=True)
    parser.add_argument('--destination', required=True)
    parser.add_argument('--source', choices=['local', 'configured'], default='local')
    parser.add_argument('--download', action='store_true', help='Explicitly back up ready originals in addition to exporting keys.')
    args = parser.parse_args()
    parts = urlsplit(args.origin)
    if (parts.scheme != 'https' or not parts.hostname or parts.username or parts.password
            or parts.path not in {'', '/'} or parts.query or parts.fragment):
        parser.error('--origin must be an HTTPS origin without credentials, path or query')
    origin = args.origin.rstrip('/')
    destination = Path(args.destination).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    manifest_path = destination / 'manifest.json'
    if manifest_path.exists() or (destination / 'backup-report.json').exists():
        parser.error('Choose a new backup directory; existing reports are never overwritten')
    if not sys.stdin.isatty():
        parser.error('Run in an interactive terminal so the secret can be entered without echo')
    token = getpass.getpass('Temporary Render recovery secret (not stored): ')
    if not re.fullmatch(r'[A-Za-z0-9_-]{43,128}', token):
        parser.error('Secret must be 43–128 URL-safe characters')
    opener = build_opener(NoRedirect())
    rows = []
    offset = 0
    while True:
        path = '/internal/media-recovery/manifest/?' + urlencode({'source': args.source, 'offset': offset})
        page = json.loads(fetch(opener, origin, path, token, 1024 * 1024))
        rows.extend(page['images'])
        next_offset = page['next_offset']
        if next_offset is None:
            break
        if not isinstance(next_offset, int) or next_offset <= offset:
            raise RuntimeError('Invalid manifest pagination')
        offset = next_offset
    if len({row['key'] for row in rows}) != len(rows):
        raise RuntimeError('Manifest changed during export; pause image edits and retry in a new directory')
    # Do not persist bearer tokens, internal download IDs, database IDs or URLs.
    exported = [{key: value for key, value in row.items() if key != 'download_id'} for row in rows]
    with manifest_path.open('x', encoding='utf-8') as handle:
        json.dump({'source': args.source, 'images': exported}, handle, indent=2)
    report = []
    if args.download:
        for row in rows:
            status = row['status']
            if status == 'ready':
                try:
                    identifier = row['download_id']
                    if not re.fullmatch(r'[a-f0-9]{64}', identifier):
                        raise ValueError('Invalid download ID')
                    path = '/internal/media-recovery/original/' + identifier + '/?' + urlencode({'source': args.source})
                    payload = fetch(opener, origin, path, token, MAX_BYTES)
                    status = save_original(destination / 'originals', row, payload)
                except Exception as exc:
                    status = 'backup_error:' + type(exc).__name__
            report.append({'key': row['key'], 'status': status})
        with (destination / 'backup-report.json').open('x', encoding='utf-8') as handle:
            json.dump({'images': report}, handle, indent=2)
    print('Manifest exported:', manifest_path)
    print('Referenced image keys:', len(rows))
    if args.download:
        saved = sum(row['status'] in {'saved_verified', 'existing_identical'} for row in report)
        print('Verified originals backed up:', saved, '/', len(rows))
        return 0 if saved == len(rows) else 1
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        # Avoid traceback/frame dumps containing the in-memory bearer token.
        print('Recovery stopped:', type(exc).__name__, '(no existing files overwritten)')
        raise SystemExit(1)
