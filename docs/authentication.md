# Authentication

Every request to the Animal-ID partner API carries an **HMAC-SHA256 signature** over a canonical string. There is no OAuth dance, no token endpoint, no refresh flow — you sign each request with your private key and send it. That's the whole scheme.

If you only read one section, read [The canonical string](#the-canonical-string) and [The key is a string](#the-key-is-a-string-not-hex-bytes).

---

## Getting credentials

1. **Create an organization page in Animal-ID.** This is the only manual prerequisite. A personal account is not enough — the partner API is issued to organizations.
2. Open the organization's developer / API section. You get four values:

| Value | Used for |
|---|---|
| **App ID** | `X-Eternity-App-Id` header — identifies your integration |
| **Public key** | `X-Eternity-Public-Key` header — identifies the key pair |
| **Private key** | The HMAC secret. Never leaves your server. |
| **Webhook secret** | Verifying inbound webhooks (prefix `whsec_`) |

Keep all four in environment variables. Never put the private key in frontend code, a mobile app, or a repo — anything holding it can act as your clinic.

---

## Base URL

```
https://gw.animal-id.net/v1/partner
```

The `/v1/partner` prefix is **part of the signed path**. Getting this wrong is the single most common cause of a `401`.

---

## Headers

Every request:

| Header | Value |
|---|---|
| `X-Eternity-App-Id` | your App ID |
| `X-Eternity-Public-Key` | your public key |
| `X-Eternity-Timestamp` | current Unix time, seconds, as a string |
| `X-Eternity-Signature` | hex HMAC-SHA256 — see below |

Write requests (`POST`, `PATCH`, `DELETE`) additionally:

| Header | Value |
|---|---|
| `X-Eternity-Idempotency-Key` | a UUID (see [Idempotency](#idempotency)) |

Optional, on some `GET`s:

| Header | Value |
|---|---|
| `X-Eternity-Expand` | JSON array, e.g. `["owners"]` — **a header, not a query param** |

One more practical note: **set a real `User-Agent`.** Cloudflare fronts the gateway and rejects the default `python-urllib` UA. Any identifiable string works:

```
User-Agent: my-clinic/1.0 (+https://myclinic.example)
```

---

## The canonical string

Four lines, joined with `\n`:

```
METHOD
/v1/partner/path?query=string
sha256_hex(raw_request_body)
unix_timestamp
```

Rules that matter:

- **Line 1** — uppercase HTTP method: `GET`, `POST`, `PATCH`, `DELETE`.
- **Line 2** — the path **including the `/v1/partner` prefix** and **including the query string** exactly as it appears in the URL. Encode the query once and reuse the same bytes for both signing and the request — re-encoding differently breaks the signature.
- **Line 3** — SHA-256 **hex digest of the raw request body bytes**. For a request with no body, this is the digest of the empty string: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`. Hash the *exact* bytes you send — serialize your JSON once, hash it, send it.
- **Line 4** — the same timestamp you put in `X-Eternity-Timestamp`.

Then:

```
signature = hmac_sha256_hex(key = PRIVATE_KEY, message = canonical_string)
```

Lowercase hex.

---

## The key is a string, not hex bytes

The private key *looks* like hex — 64 hex characters. It is tempting to decode it to 32 bytes before using it as the HMAC key. **Don't.**

The HMAC key is the private key **as raw ASCII text**, all 64 characters.

```python
key = PRIVATE_KEY.encode('utf-8')          # correct
key = bytes.fromhex(PRIVATE_KEY)           # wrong — every request 401s
```

This is not stated anywhere in the docs and is the reason most first integrations fail. See [gotchas.md](gotchas.md#1-the-hmac-key-is-the-private-key-as-a-string).

---

## Working example (Python, stdlib only)

No dependencies. Copy it as-is.

```python
import hashlib, hmac, json, time, urllib.parse, urllib.request

BASE = 'https://gw.animal-id.net/v1/partner'
APP_ID, PUBLIC_KEY, PRIVATE_KEY = '...', '...', '...'
EMPTY_SHA = hashlib.sha256(b'').hexdigest()


def call(method, endpoint, query=None, body=None):
    method = method.upper()

    qs = ''
    if query:
        clean = {k: v for k, v in query.items() if v not in (None, '')}
        if clean:
            qs = '?' + urllib.parse.urlencode(clean)

    body_bytes = b''
    headers = {'Accept': 'application/json',
               'User-Agent': 'my-clinic/1.0 (+https://myclinic.example)'}
    if body is not None:
        body_bytes = json.dumps(body, separators=(',', ':')).encode()
        headers['Content-Type'] = 'application/json'

    ts = str(int(time.time()))
    body_sha = hashlib.sha256(body_bytes).hexdigest() if body_bytes else EMPTY_SHA
    # NOTE: '/v1/partner' is part of the signed path.
    canonical = f'{method}\n/v1/partner{endpoint}{qs}\n{body_sha}\n{ts}'
    sig = hmac.new(PRIVATE_KEY.encode(), canonical.encode(), hashlib.sha256).hexdigest()

    headers.update({
        'X-Eternity-App-Id': APP_ID,
        'X-Eternity-Public-Key': PUBLIC_KEY,
        'X-Eternity-Timestamp': ts,
        'X-Eternity-Signature': sig,
    })
    if method in ('POST', 'PATCH', 'DELETE'):
        import uuid
        headers['X-Eternity-Idempotency-Key'] = str(uuid.uuid4())

    req = urllib.request.Request(BASE + endpoint + qs, method=method,
                                 data=body_bytes or None, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            data = json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e:
        data = json.loads(e.read() or b'{}')
        raise RuntimeError(f'HTTP {e.code}: {data}')
    # The success envelope wraps everything under "payload" — always a LIST.
    return data.get('payload', data)


# Smoke test — no auth needed for this one, but it proves your transport works.
print(call('GET', '/dictionaries')[:1])

# Real auth check — this one IS authenticated.
print(call('GET', '/owners/search', query={'email_or_phone': 'test@example.com'}))
```

> **Verify against an authenticated endpoint.** `/dictionaries` is public — it returns `200` even with a broken signature, so it proves nothing about your auth. Use `/owners/search` instead: a `401` means your signature is wrong; a `404` (owner not found) or `422` means your signature is **correct**.

---

## Idempotency

`POST`, `PATCH` and `DELETE` take `X-Eternity-Idempotency-Key` (a UUID).

- Replaying the **same key with the same body** returns the first response — safe retry.
- The **same key with a different body** returns `409 Conflict`.

Two practical patterns:

**Stable keys for create-once resources.** Derive the key deterministically from your own primary key, so a retry — or a second process, or a redeploy mid-request — can never create a duplicate upstream:

```python
import uuid
NS = uuid.UUID('6ba7b812-9dad-11d1-80b4-00c04fd430c8')   # any fixed namespace
key = str(uuid.uuid5(NS, f'animal:{pet.id}'))
```

**Fresh keys for updates.** `PATCH` is naturally idempotent, and a stable key would `409` the second time you edit the same record with different values. Use a fresh `uuid4()` for updates.

---

## Timestamps and clock skew

`X-Eternity-Timestamp` is Unix seconds and is signed, so a stale clock breaks every request with a `401` that looks exactly like a bad key. If auth suddenly fails on a server that worked yesterday, check NTP before you check your code.

---

## Errors

Errors come back in a consistent envelope:

```json
{
  "errors": [
    {
      "status": 422,
      "type": "validation_error",
      "detail": "The given data was invalid.",
      "validation_errors": [
        {"field": "microchip", "message": "The microchip field is required."}
      ]
    }
  ]
}
```

| Status | Meaning | Usual cause |
|---|---|---|
| `401` | Signature rejected | string-vs-hex key, missing `/v1/partner` in the signed path, query encoded differently for signing than for the URL, clock skew |
| `403` | Access denied | the owner hasn't granted your clinic access to this animal |
| `404` | Not found | no such owner / animal / procedure |
| `409` | Conflict | idempotency key reused with a different body |
| `422` | Validation failed | read `validation_errors` — it names the exact fields |

`422` is not just an error, it's documentation. See [ai-agent-guide.md](ai-agent-guide.md#the-422-probe) for how to use it to discover a payload shape.

Map these to typed exceptions in your client rather than passing raw HTTP errors up the stack — callers want to distinguish "owner must consent" (`403`) from "you broke the request" (`422`).

---

## Webhooks

Inbound webhooks use the **same signing scheme**, with different header names:

| Header | Meaning |
|---|---|
| `X-Eternity-Webhook-Id` | delivery id — use it to dedupe replays |
| `X-Eternity-Webhook-Event` | event name |
| `X-Eternity-Webhook-Timestamp` | Unix seconds |
| `X-Eternity-Webhook-Signature` | hex HMAC-SHA256, keyed with the **webhook secret** |

> The webhook secret starts with `whsec_`, which is the Svix convention — but this is **not** Svix. Don't reach for a Svix SDK; verify it yourself with the same HMAC you already wrote.

Verify before you trust anything in the body, and compare in constant time:

```python
expected = hmac.new(WEBHOOK_SECRET.encode(), canonical.encode(), hashlib.sha256).hexdigest()
if not hmac.compare_digest(expected, received_signature):
    return HttpResponse(status=401)
```

Also reject timestamps outside a few minutes of now, so a captured delivery can't be replayed later.

---

## Checklist when a request 401s

Work down the list — it's almost always one of these:

- [ ] HMAC key is the private key **as a string**, not `bytes.fromhex(...)`
- [ ] Signed path includes the **`/v1/partner`** prefix
- [ ] Signed path includes the **query string**, byte-identical to the URL
- [ ] Body hash is over the **exact bytes sent** (serialize once)
- [ ] Empty body → sha256 of empty string, not of `"{}"`
- [ ] `X-Eternity-Timestamp` matches the timestamp in the canonical string
- [ ] Server clock is accurate
- [ ] Custom `User-Agent` is set (otherwise Cloudflare may `403` before auth even runs)
- [ ] You're testing against an **authenticated** endpoint, not `/dictionaries`
