# Endpoint reference

The partner API surface, as verified against a live organization — with notes on what each endpoint is actually good for inside a clinic.

Base URL: `https://gw.animal-id.net/v1/partner`
Auth: every endpoint except `/dictionaries` requires a signed request — see [authentication.md](authentication.md).

> Remember: the success envelope is `{"payload": [...]}` and **`payload` is always a list**, even for a single resource.

---

## Reference data

### `GET /dictionaries`

Species, sex, procedure types, countries, languages.

**Public — no auth required.** Do not use it to test your credentials ([why](gotchas.md#2-dictionaries-is-public--it-cant-validate-your-auth)).

There is **no breed dictionary**; `breed` is free text.

Codes you'll need immediately:

| Field | Values |
|---|---|
| `species` | Cats `1`, Dogs `3` |
| `gender_id` | Female `0`, Male `1`, Unknown `2` |

**Use it for:** mapping your internal enums onto Animal-ID's at integration time. Fetch once, hard-code or cache — it doesn't change often.

---

## Owners

An owner is a person in the registry. Your clinic's client becomes an Animal-ID owner so their pets can be linked to them globally.

### `GET /owners/search?email_or_phone=...`

One combined parameter — not `email` / `phone` ([gotcha](gotchas.md#5-search-takes-email_or_phone-not-email-or-phone)). Normalize phone numbers to E.164 (`+13055551234`).

Returns `404` when nobody matches.

**Use it for:** checking whether a new client already exists in the registry before creating a duplicate. Also the cheapest way to prove your signing works.

### `POST /owners`

Creates or resolves an owner.

```json
{
  "email": "jane@example.com",
  "phone": "+13055551234",
  "first_name": "Jane",
  "last_name": "Doe",
  "language": "en",
  "consent": { "account_creation": true }
}
```

Returns `user_gid` **and** `public_id`. **Store the `user_gid`** — it's the one that links owners to animals ([gotcha](gotchas.md#4-owners-attach-to-animals-by-user_gid-not-public_id)).

`consent.account_creation` is you asserting the person agreed to have an account created. Get that consent for real — this is someone's identity in a global registry, not a CRM row.

**Use it for:** onboarding a client once, at their first visit or first portal signup. Use a stable idempotency key derived from your own client id.

---

## Animals

### `GET /animals/by-identifier/{value}`

Search across identifier types — the "scan and see" endpoint.

### `GET /animals/by-identifier/{type}/{value}`

Narrower: `type` is e.g. `microchip`.

**Use it for:** the single highest-value feature you can ship. A found-stray lookup on your public site, or a chip check at intake that pulls up a pet you've never seen before. Read-only, no consent required, instantly demonstrable.

Both return only the fields you're allowed to see. Full records for animals belonging to other clinics' clients need [access](#access).

### `GET /animals/by-owner?email_or_phone=...`

Every animal linked to that owner contact — **including pets registered by other clinics**.

**Use it for:** intake. A client books an appointment; you already know they have three pets, one of which you've never treated. Also good in a booking flow: offer their registry pets alongside the ones you have locally, deduped by chip/name so the same animal doesn't appear twice.

### `GET /animals/{id}`

The full record. Add related data with the `X-Eternity-Expand: ["owners"]` **header** — not a query param ([gotcha](gotchas.md#6-expand-is-a-header-not-a-query-parameter)).

Returns `403` if the owner hasn't granted you access. That's expected, not a bug.

### `POST /animals`

Register an animal.

```json
{
  "species": 3,
  "is_microchip": true,
  "microchip": "9411000000000",
  "nickname": "Rex",
  "gender_id": 1,
  "breed": "Labrador",
  "color": "black",
  "dob": "2021-04-17",
  "sterilization": true,
  "owners": [ { "user_gid": 12345 } ]
}
```

Returns the animal `id` (a NanoID) — persist it on your local pet record; it's the key to everything else.

`microchip` is optional (`is_microchip: false`), but a chip-less profile isn't findable by lookup ([gotcha](gotchas.md#10-a-microchip-is-optional--but-its-what-makes-a-pet-findable)).

**Use it for:** giving your patients an ID that follows them to any other clinic. Register at chip implantation, at first vaccination, or on portal signup — whichever moment your staff already treat as "this pet is now ours".

### `PATCH /animals/{id}`

Update core fields. Naturally idempotent, so use a **fresh** idempotency key — a stable one `409`s on the second differing edit. May return `204` with no body.

**Use it for:** keeping the registry honest when staff correct a breed, colour, or sterilization status locally.

---

## Procedures

The medical record. This is what makes the registry more than a phone book.

### `POST /animals/{id}/procedures`

```json
{
  "type": 10,
  "occurred_at": "2026-03-14T12:00:00+00:00",
  "summary": "Annual booster, no reaction",
  "revaccination_date": "2027-03-14",
  "type_specific_payload": {
    "vaccine_name": "Nobivac DHPPi",
    "batch_number": "A1234-5"
  }
}
```

| Code | Procedure | `type_specific_payload` |
|---|---|---|
| `10` | Vaccination | `vaccine_name`, `batch_number` |
| `20` | Rabies vaccination | `vaccine_name`, `batch_number` |
| `30` | Transponder / microchip | identifier fields |
| `40` | QR token | token fields |
| `50` | Deworming | `drug` |
| `60` | Sterilization | `method`, `anesthesia_type` |
| `70` | Death | — |

`occurred_at` is a full ISO-8601 timestamp, not a date. Rabies is its own type — file it as `20`, not `10`.

**Use it for:** mirroring what you already record. If your system stores vaccinations, push them here on save; the client's pet now has a portable vaccination history that doesn't depend on your clinic still existing in ten years.

### `GET /animals/{id}/procedures`

Optional `type`, `since`, `until` filters.

**Use it for:** the payoff. This returns procedures logged by **every** partner clinic, not just yours — so a new patient arrives with a real history instead of "the owner thinks she had her shots last spring". Show it as a read-only "global record" next to your own notes, clearly labelled as coming from the registry.

---

## Access

Consent-gated access to animals you didn't register.

### `POST /animals/{id}/access-request`

Asks the owner to grant your clinic access.

### `GET /animals/{id}/access-request`

`pending` / `approved` / `denied`.

**Use it for:** the intake case where a client's pet is in the registry under a previous clinic. Show what you can, and offer a one-click "request access" instead of a dead end. Store the request locally with its status so staff can see it's pending rather than re-requesting.

---

## Photos

### `POST /animals/{id}/photos`

`multipart/form-data`, fields `file` and `kind` (`avatar` / `gallery` / `nose`).

**Sign an empty body hash**, not the multipart bytes ([gotcha](gotchas.md#7-photo-upload-is-multipart-and-signs-an-empty-body)).

Key the idempotency key off the stored file path, so re-runs don't duplicate but a genuinely new photo uploads fresh.

### `DELETE /animals/{id}/photos/{photo_id}`

Soft delete.

**Use it for:** a real photo on the profile. It matters more than it sounds — a found-stray lookup that returns a photo is a recognisable animal; one that returns a chip number is a database row.

---

## Webhooks

Same signing scheme as the API, different headers ([details](authentication.md#webhooks)):

| Header |
|---|
| `X-Eternity-Webhook-Id` |
| `X-Eternity-Webhook-Event` |
| `X-Eternity-Webhook-Timestamp` |
| `X-Eternity-Webhook-Signature` |

**Use it for:** reacting when an owner approves or denies an access request, so staff don't have to poll. Dedupe on `X-Eternity-Webhook-Id`, reject stale timestamps, and **verify the signature before parsing anything**.

Code your handler defensively and confirm the payload shape against your own deliveries — don't build tight coupling to field names you haven't seen arrive.

---

## The public profile

Not an API call, but you'll want it:

```
https://animal-id.net/en/pets/{animal_id}
```

**Use it for:** giving clients somewhere to send a link. Keep it in config, not hard-coded ([gotcha](gotchas.md#11-the-public-profile-url-is-enpetsid)).

Note the public site rejects non-browser User-Agents, so don't build server-side health checks against it ([gotcha](gotchas.md#12-animal-idnet-blocks-non-browser-user-agents)).
