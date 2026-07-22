# Gotchas

Everything here was found by probing the live API during a real integration. None of it is in the official documentation, and each item cost anywhere from twenty minutes to half a day.

They're ordered roughly by how much time they'll save you.

---

## 1. The HMAC key is the private key *as a string*

The private key is 64 hex characters, so decoding it to 32 bytes before signing feels obviously correct. It isn't.

```python
key = PRIVATE_KEY.encode('utf-8')   # ✅ works
key = bytes.fromhex(PRIVATE_KEY)    # ❌ 401 on every request
```

Both are plausible, both produce a well-formed signature, and the API's `401` doesn't distinguish them from a dozen other causes. If you're stuck on `401` and everything else looks right, **this is it**.

**How to be sure:** try both against `/owners/search` with a nonsense contact.
- String key → `404` or `422` (auth passed, lookup failed) ✅
- Hex key → `401` ❌

---

## 2. `/dictionaries` is public — it can't validate your auth

`GET /dictionaries` returns `200` with the full reference data **even with a completely broken signature**. Every integration starts by calling it, sees `200`, and concludes auth works. It doesn't test auth at all.

Always smoke-test against an endpoint that actually requires credentials — `/owners/search` is the cheapest.

---

## 3. `payload` is always a list

The success envelope is `{"payload": [...]}` — and it is a **list even for single resources**. Create an animal, and you get a one-element list back. Fetch one animal by id, same thing.

```python
def first(payload):
    """Unwrap the always-a-list payload."""
    if isinstance(payload, list):
        return payload[0] if payload else {}
    return payload or {}

animal = first(client.create_animal(body))
animal_id = animal.get('id')
```

Without this you get `'list' object has no attribute 'get'` at the least convenient moment — usually right after a successful write, so the resource exists upstream but your local link never got saved.

---

## 4. Owners attach to animals by `user_gid`, not `public_id`

`POST /owners` returns both `user_gid` and `public_id`. When you then create an animal and link the owner, only one of them is accepted:

```json
{ "owners": [ { "user_gid": 12345 } ] }
```

Using `public_id` returns `422`. Store the **`user_gid`** on your local client record — that's the durable link.

Note it's a **number**, not a string. If you persist it as text, cast it back on the way out.

---

## 5. Search takes `email_or_phone`, not `email` or `phone`

Both `GET /owners/search` and `GET /animals/by-owner` accept a single combined parameter:

```
GET /owners/search?email_or_phone=jane@example.com
GET /animals/by-owner?email_or_phone=%2B13055551234
```

`?email=` / `?phone=` are silently ignored, which reads as "no results" rather than "wrong parameter" — a much slower failure to notice.

Normalize phones to E.164 (`+13055551234`) before searching.

---

## 6. `expand` is a header, not a query parameter

To embed related resources:

```
X-Eternity-Expand: ["owners"]
```

A JSON array, in a header. `?expand=owners` does nothing.

Since headers aren't part of the canonical string, this doesn't affect signing — but it does mean a typo here fails silently rather than with a `401`.

---

## 7. Photo upload is multipart and signs an *empty* body

`POST /animals/{id}/photos` is `multipart/form-data` with two fields:

| Field | Value |
|---|---|
| `file` | the image bytes, with a filename and content type |
| `kind` | `avatar`, `gallery`, or `nose` |

The catch: **the multipart body is not part of the signature.** Sign as if the body were empty:

```python
sig = sign('POST', '/v1/partner/animals/{id}/photos', b'', ts)   # empty body hash
```

Hashing the real multipart bytes → `401`. This is the only endpoint where the body hash and the actual body disagree.

---

## 8. There is no breeds dictionary

`/dictionaries` gives you species, sex, procedure types, countries and more — but **no breed list**. `breed` is a free-text string.

If you were planning a breed picker fed by the API: you'll need your own list. And don't build a UI whose only purpose is browsing the dictionary — there isn't enough there to be useful to a clinic on its own. Use the dictionary to *map* your data, not to display it.

Useful codes, so you don't have to fetch them to get started:

| Dictionary | Values |
|---|---|
| Species | Cats = `1`, Dogs = `3` |
| Sex (`gender_id`) | Female = `0`, Male = `1`, Unknown = `2` |

---

## 9. Procedure types and their required sub-payloads

Procedures are typed by an integer, and each type demands different fields inside `type_specific_payload`:

| Code | Procedure | `type_specific_payload` needs |
|---|---|---|
| `10` | Vaccination | `vaccine_name`, `batch_number` |
| `20` | Rabies vaccination | `vaccine_name`, `batch_number` |
| `30` | Transponder / microchip | identifier fields |
| `40` | QR token | token fields |
| `50` | Deworming | `drug` |
| `60` | Sterilization | `method`, `anesthesia_type` |
| `70` | Death | — |

`occurred_at` is a full ISO-8601 timestamp, not a date. If your local record only stores a date, pick a time (midday UTC is a reasonable convention) rather than sending a bare `YYYY-MM-DD`.

Rabies is its own type — don't file it as generic vaccination if the vaccine name says rabies, or it won't show up where a border official or another clinic expects it.

Don't guess the sub-payload for a type you haven't used: send `type` plus an empty `type_specific_payload` and read the `422`. See [ai-agent-guide.md](ai-agent-guide.md#the-422-probe).

---

## 10. A microchip is optional — but it's what makes a pet findable

You can register an animal with `is_microchip: false` and no `microchip` field. It gets a global ID and a profile.

But lookup by chip or QR is the whole point of the registry, and a chip-less profile isn't findable that way. Register chip-less pets if it helps your workflow — just know their record is inert until an identifier is added.

```python
body = {'species': 3, 'is_microchip': bool(chip), 'nickname': name,
        'owners': [{'user_gid': gid}]}
if chip:
    body['microchip'] = chip
```

---

## 11. The public profile URL is `/en/pets/{id}`

Once an animal is registered you'll want to link clients to its public page. The pattern is:

```
https://animal-id.net/en/pets/{animal_id}
```

Not `/{id}`, not `/animals/{id}`. It isn't documented — make it a config value rather than a hard-coded string, so a future change is a settings edit and not a deploy.

---

## 12. `animal-id.net` blocks non-browser User-Agents

The **public website** (not the API gateway) rejects requests from `curl`, monitoring probes and server-side fetches — you'll get a `502`/`403` even though the page is fine in a browser.

This matters if you planned to health-check profile links, prefetch OG metadata, or screenshot pages server-side. The API gateway `gw.animal-id.net` is a different host and behaves normally — but it still wants a custom UA (see [authentication.md](authentication.md#headers)).

---

## 13. Access to other clinics' pets is consent-based

You can *find* an animal registered by another clinic. You cannot read its full record until the owner approves.

- `POST /animals/{id}/access-request` — asks the owner
- `GET /animals/{id}/access-request` — `pending` / `approved` / `denied`
- Reading a record you don't have access to → `403`, not `404`

So `403` on an animal you can clearly see in search results is **expected behaviour**, not a bug. Build the UI around it: show what you can (name, species, that it exists), and a "request access" action for the rest.

The corresponding webhook lets you react when the owner answers — but verify the payload shape against your own deliveries before relying on specific field names, and code defensively.

---

## 14. `PATCH` may return `204` with no body

Updates can come back empty. Don't unconditionally parse JSON from a write response, and don't treat "no payload" as failure.

---

## Contributing a gotcha

Hit something that isn't here? Open an issue or a PR. Include the request you sent, the response you got, and what you expected — that's what makes these entries useful to the next clinic.
