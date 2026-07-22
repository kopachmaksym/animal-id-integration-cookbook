"""Minimal Animal-ID partner API client — standard library only.

No dependencies, no framework. Drop it next to your code, set four
environment variables, and every recipe in this cookbook will run.

    export ANIMALID_APP_ID=...
    export ANIMALID_PUBLIC_KEY=...
    export ANIMALID_PRIVATE_KEY=...
    export ANIMALID_WEBHOOK_SECRET=...      # only needed for webhooks

The signing scheme is documented in docs/authentication.md. The two
non-obvious parts are marked with NOTE below.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE_URL = os.environ.get('ANIMALID_BASE_URL', 'https://gw.animal-id.net/v1/partner')
APP_ID = os.environ.get('ANIMALID_APP_ID', '')
PUBLIC_KEY = os.environ.get('ANIMALID_PUBLIC_KEY', '')
PRIVATE_KEY = os.environ.get('ANIMALID_PRIVATE_KEY', '')

# Cloudflare fronts the gateway and 403s the default python-urllib UA.
USER_AGENT = os.environ.get('ANIMALID_USER_AGENT', 'animal-id-cookbook/1.0')

_BASE_PATH = urllib.parse.urlsplit(BASE_URL).path.rstrip('/')   # '/v1/partner'
_EMPTY_SHA256 = hashlib.sha256(b'').hexdigest()

# Stable namespace for deterministic idempotency keys.
_NS = uuid.UUID('6ba7b812-9dad-11d1-80b4-00c04fd430c8')


class AnimalIDError(Exception):
    """API returned an error. `.status` and `.errors` carry the details."""

    def __init__(self, message, status=None, errors=None, payload=None):
        super().__init__(message)
        self.status = status
        self.errors = errors or []
        self.payload = payload


def idempotency_key(*parts) -> str:
    """Deterministic key from your own identifiers, e.g. idempotency_key('animal', pet.id).

    Same inputs -> same key -> a retry can never create a duplicate upstream.
    Use a plain uuid4() for PATCH instead: a stable key 409s on the second
    differing edit.
    """
    return str(uuid.uuid5(_NS, ':'.join(str(p) for p in parts)))


def first(payload):
    """Unwrap the always-a-list payload to its single object.

    The success envelope wraps every resource in a list, even single ones.
    """
    if isinstance(payload, list):
        return payload[0] if payload else {}
    return payload or {}


def _sign(method: str, path_with_query: str, body: bytes, ts: str) -> str:
    body_sha = hashlib.sha256(body).hexdigest() if body else _EMPTY_SHA256
    canonical = f'{method}\n{path_with_query}\n{body_sha}\n{ts}'
    # NOTE: the HMAC key is the private key as an ASCII STRING.
    # bytes.fromhex(PRIVATE_KEY) looks right and 401s on every request.
    return hmac.new(PRIVATE_KEY.encode('utf-8'), canonical.encode('utf-8'),
                    hashlib.sha256).hexdigest()


def call(method, endpoint, *, query=None, body=None, idem=None, headers=None):
    """Perform one signed request and return the parsed `payload`.

    endpoint -- relative to the partner base, e.g. '/owners/search'
    query    -- dict of plain values; encoded once and reused for sign + URL
    body     -- JSON-serialisable dict for POST/PATCH
    """
    method = method.upper()

    qs = ''
    if query:
        clean = {k: v for k, v in query.items() if v not in (None, '')}
        if clean:
            qs = '?' + urllib.parse.urlencode(clean)

    # NOTE: the signed path includes the /v1/partner prefix AND the query
    # string, byte-identical to what goes in the URL.
    path_with_query = f'{_BASE_PATH}{endpoint}{qs}'

    body_bytes = b''
    hdrs = {
        'Accept': 'application/json',
        'User-Agent': USER_AGENT,
        'X-Eternity-App-Id': APP_ID,
        'X-Eternity-Public-Key': PUBLIC_KEY,
    }
    if body is not None:
        body_bytes = json.dumps(body, separators=(',', ':')).encode('utf-8')
        hdrs['Content-Type'] = 'application/json'
    if method in ('POST', 'PATCH', 'DELETE'):
        hdrs['X-Eternity-Idempotency-Key'] = idem or str(uuid.uuid4())
    if headers:
        hdrs.update(headers)

    ts = str(int(time.time()))
    hdrs['X-Eternity-Timestamp'] = ts
    hdrs['X-Eternity-Signature'] = _sign(method, path_with_query, body_bytes, ts)

    req = urllib.request.Request(f'{BASE_URL}{endpoint}{qs}', method=method,
                                 data=body_bytes if body is not None else None,
                                 headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return _parse(resp.status, resp.read())
    except urllib.error.HTTPError as exc:
        return _parse(exc.code, exc.read() if exc.fp else b'')
    except urllib.error.URLError as exc:
        raise AnimalIDError(f'transport error: {exc.reason}') from exc


def _parse(status, raw):
    try:
        data = json.loads(raw.decode('utf-8')) if raw else {}
    except ValueError:
        if 200 <= status < 300:
            return {}                      # PATCH can return 204, empty body
        raise AnimalIDError(f'HTTP {status} with non-JSON body', status=status)

    if 200 <= status < 300:
        return data.get('payload', data) if isinstance(data, dict) else data

    errors = (data.get('errors') if isinstance(data, dict) else None) or []
    head = errors[0] if errors else {}
    raise AnimalIDError(head.get('detail') or head.get('title') or f'HTTP {status}',
                        status=status,
                        errors=head.get('validation_errors') or [],
                        payload=data)


def upload_photo(animal_id, data: bytes, *, filename='pet.jpg',
                 content_type='image/jpeg', kind='avatar', idem=None):
    """POST /animals/{id}/photos — multipart, fields `file` + `kind`.

    NOTE: the multipart body is NOT part of the signature. Sign an EMPTY
    body hash; hashing the real bytes 401s. This is the only such endpoint.
    """
    endpoint = f'/animals/{urllib.parse.quote(str(animal_id), safe="")}/photos'
    boundary = '----aid' + uuid.uuid4().hex
    body = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="kind"\r\n\r\n{kind}\r\n'.encode()
        + (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
           f'filename="{filename}"\r\nContent-Type: {content_type}\r\n\r\n').encode()
        + data + b'\r\n' + f'--{boundary}--\r\n'.encode()
    )
    ts = str(int(time.time()))
    hdrs = {
        'Accept': 'application/json',
        'User-Agent': USER_AGENT,
        'X-Eternity-App-Id': APP_ID,
        'X-Eternity-Public-Key': PUBLIC_KEY,
        'X-Eternity-Timestamp': ts,
        'X-Eternity-Signature': _sign('POST', f'{_BASE_PATH}{endpoint}', b'', ts),
        'X-Eternity-Idempotency-Key': idem or str(uuid.uuid4()),
        'Content-Type': f'multipart/form-data; boundary={boundary}',
    }
    req = urllib.request.Request(f'{BASE_URL}{endpoint}', method='POST',
                                 data=body, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return _parse(resp.status, resp.read())
    except urllib.error.HTTPError as exc:
        return _parse(exc.code, exc.read() if exc.fp else b'')


def verify_webhook(secret, method, path, raw_body: bytes, timestamp, signature) -> bool:
    """Verify an inbound webhook — same scheme, keyed with the webhook secret.

    The `whsec_` prefix is the Svix convention, but this is NOT Svix.
    Reject timestamps more than a few minutes old to block replays.
    """
    body_sha = hashlib.sha256(raw_body).hexdigest() if raw_body else _EMPTY_SHA256
    canonical = f'{method.upper()}\n{path}\n{body_sha}\n{timestamp}'
    expected = hmac.new(secret.encode('utf-8'), canonical.encode('utf-8'),
                        hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or '')


if __name__ == '__main__':
    # Smoke test. /dictionaries is PUBLIC — it proves transport, not auth.
    print('dictionaries reachable:', bool(call('GET', '/dictionaries')))

    # This one is authenticated. 404/422 = signature OK. 401 = signature wrong.
    try:
        call('GET', '/owners/search', query={'email_or_phone': 'nobody@example.com'})
        print('auth OK (owner found)')
    except AnimalIDError as exc:
        print('auth OK' if exc.status in (404, 422) else f'AUTH FAILED: {exc}')
