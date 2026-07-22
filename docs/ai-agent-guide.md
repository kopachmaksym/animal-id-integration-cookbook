# Integrating with an AI agent

The integration this cookbook documents was built mostly by an AI coding agent, working against the live API. This page is about **why that worked**, and how to reproduce it — whether your "agent" is Claude Code, Cursor, or a junior developer with a terminal.

It's also an honest account of what the agent could *not* do.

---

## Why this API is agent-friendly

Three properties make the difference:

**1. Auth is one function.** No OAuth redirect, no browser consent screen, no token refresh, no SDK. An agent can write the signing function, run it, and see whether it worked — all in one loop, no human in the middle. Anything requiring a browser login flow immediately needs a human.

**2. Errors name the fields.** A `422` comes back with `validation_errors`, each naming the exact field and what's wrong with it. That turns "read the docs and hope" into a mechanical loop: send, read the error, fix, resend. See [the 422 probe](#the-422-probe).

**3. Writes are idempotent.** `X-Eternity-Idempotency-Key` means a retry can't create duplicates. An agent that's unsure whether its last request landed can just repeat it. Without that, exploratory writes against a real registry would be reckless.

**4. There is a test organization.** You can create records, break things, and iterate without polluting real data — which is what makes exploratory probing acceptable at all.

---

## The 422 probe

The fastest way to learn an endpoint's contract is to send it something deliberately incomplete and read the complaint.

```python
# What does a deworming procedure need?
call('POST', f'/animals/{aid}/procedures',
     body={'type': 50, 'occurred_at': '2026-01-01T12:00:00Z',
           'type_specific_payload': {}})
```

```json
{"errors": [{"status": 422, "validation_errors": [
  {"field": "type_specific_payload.drug", "message": "The drug field is required."}
]}]}
```

There's the answer: type 50 needs `drug`. One request, no guessing.

This works for any endpoint whose payload you're unsure about. Most of [gotchas.md](gotchas.md) was discovered this way. Two rules:

- **Probe on a test organization**, never a production one.
- **Probe reads before writes** where you can — `GET /owners/search?email_or_phone=nobody@example.com` tells you your auth works without creating anything.

---

## Verify auth against the right endpoint

An agent's first instinct is to call the simplest endpoint to confirm the setup. `/dictionaries` is public — it returns `200` with a completely invalid signature. An agent that "verifies" against it will confidently report success and then fail on every real call.

Make this explicit in your instructions: **verification means an authenticated endpoint.** `/owners/search` returning `404`/`422` proves auth; `401` disproves it.

This generalizes beyond this API — "the check I ran doesn't actually test the thing I claimed" is the most common way agents produce false confidence.

---

## What the agent couldn't do

Be clear-eyed about the boundary. In the reference integration, a human was required for exactly these:

**Credentials.** Creating the Animal-ID organization, generating keys, and putting them into the server environment. An agent should never be handed a route to obtain production credentials on its own.

**Product decisions.** Where the microchip lookup belongs in the UI. Whether staff should be able to register pets themselves, or only the owner. Whether to build a "report as lost" flow at all. These aren't technical questions and the agent guessed wrong on several until corrected.

**Anything touching production.** Deploys, database migrations on live data, and pushes were gated on explicit human approval. Development and staging were the agent's to work in freely.

**Judging its own output.** The agent verified that requests succeeded. Whether the resulting UI made sense to a receptionist at 8am was a human call.

The pattern that worked: **the agent owns the mechanism, the human owns the intent.**

---

## A working loop

If you're pointing an agent at this API, this sequence is what produced a working integration:

1. **Read the reference.** Point it at [authentication.md](authentication.md) and [gotchas.md](gotchas.md) *first*. Every hour in those files is an hour it doesn't spend rediscovering the string-vs-hex key.
2. **Write the signed client.** ~150 lines, standard library only. Typed exceptions per status code, not raw HTTP errors.
3. **Prove auth** against `/owners/search`. Don't proceed until this is unambiguous.
4. **Map the data model.** Your species/sex/procedure enums → Animal-ID's integer codes. Probe with `422`s where the shape is unclear.
5. **One capability end to end.** Microchip lookup is the best first one: read-only, immediately visible, no consent needed.
6. **Then writes.** Register owner → register animal → attach procedures. Stable idempotency keys derived from your own primary keys.
7. **Verify against the live API after every step** — not by re-reading the code, but by making the call and inspecting what came back.

Step 7 is the one agents skip. Insist on it.

---

## Instructions worth putting in your agent's context

Concretely, these lines saved the most time:

```
- The HMAC key is the private key as an ASCII string, not hex-decoded bytes.
- The signed path includes the /v1/partner prefix and the query string.
- `payload` in the success envelope is always a list, even for one resource.
- /dictionaries is public — it does NOT verify auth. Use /owners/search.
- Owners link to animals by user_gid (a number), not public_id.
- Search params are `email_or_phone`, not `email` / `phone`.
- `expand` is the X-Eternity-Expand header (JSON array), not a query param.
- Photo upload is multipart and signs an EMPTY body hash.
- Never touch production. Ask before deploying, pushing, or deleting.
- "Verified" means you made the call and read the response, not that the code looks right.
```

---

## How long it actually took

A few days of working sessions, for: a dependency-free signed client, data-model mapping, microchip lookup on the public site, pet registration from the client portal, procedure sync from the clinic's records, global history display, owner's-animals lookup, photo upload, access requests, and a webhook receiver.

The slow parts weren't the API. They were the undocumented details now collected in [gotchas.md](gotchas.md) — which is why that file exists.

See [`case-studies/green-pines`](../case-studies/green-pines) for what was built, with screenshots.
