# Case study: Green Pines Veterinary Clinic

The integration this cookbook came out of. A working veterinary practice with a public marketing site, an online booking funnel, a client portal and a staff CRM — all one Django application, none of it built with Animal-ID in mind.

The question was: how much of the registry can you bring **into** software that already exists, without sending anyone to `animal-id.net`?

Answer: all of it.

---

## What was built

### Public site — "Found a pet?"

A microchip lookup on the clinic's own home page. Anyone who finds a stray types the chip number and gets the pet's registry card, with a link to its public profile.

No login, no account, no redirect to a third-party site. It's the clinic's page, doing something genuinely useful, powered entirely by `GET /animals/by-identifier/{value}`.

→ [`recipes/lookup.md`](../../recipes/lookup.md)

### Booking funnel — register while you book

A client booking an appointment sees **one** pet list: the pets the clinic already knows about *and* the pets linked to their contact in the registry, deduped so nothing appears twice. Registry-sourced pets carry a badge.

Pick one, and the booking creates the local record with the `animalid_id` and microchip already attached — so the link is live from the first appointment rather than something staff have to reconcile later.

There's also a chip lookup right in the flow: type a number, and if the pet is in the registry, its details fill themselves in.

→ [`recipes/by-owner.md`](../../recipes/by-owner.md) · [`recipes/lookup.md`](../../recipes/lookup.md)

### Client portal — the pet's global record

Owners see, on their pet's page:

- an **Add to Animal-ID** action for pets that aren't registered yet
- the **global record** — every procedure logged by every partner clinic, not just this one
- **your pets in Animal-ID** — including animals registered by a previous vet

The last one surprised people in the best way: clients discovered records for pets they'd forgotten were registered at all.

→ [`recipes/register.md`](../../recipes/register.md) · [`recipes/history.md`](../../recipes/history.md)

### Staff CRM — the registry beside the chart

On a pet's clinical page, staff see the Animal-ID record next to the clinic's own notes, clearly marked as external and read-only. An `Animal-ID` badge on linked pets. A microchip field that feeds registration. Owner's-animals lookup at intake.

Vaccinations recorded in the CRM push to the registry on save, as typed procedures — rabies filed as rabies, not as generic vaccination.

→ [`recipes/procedures.md`](../../recipes/procedures.md) · [`recipes/access.md`](../../recipes/access.md)

### Behind the scenes

- Pet photos sync to the registry as profile avatars → [`recipes/photos.md`](../../recipes/photos.md)
- Access requests for animals belonging to other clinics, with a webhook receiver for the owner's answer → [`recipes/access.md`](../../recipes/access.md)
- Pet edits (breed, colour, sterilization) `PATCH` upstream so the registry doesn't drift

---

## What it cost

A few days of working sessions. The code that talks to Animal-ID is roughly:

| Piece | Size |
|---|---|
| Signed API client | ~350 lines, standard library only |
| Mapping / sync service | ~280 lines |
| API endpoints exposed to the frontends | ~12 handlers |
| Database changes | 2 columns + 1 table |

That last row is worth dwelling on. Linking an existing clinic system to the registry needed **two columns** — an owner `user_gid` on the client, an `animalid_id` on the pet — plus one table to track pending access requests. It is not an architecture change.

---

## What was hard (and what wasn't)

**Not hard:** the API. Auth is one function. Endpoints are predictable. Errors name the fields they don't like. There is no SDK for Python and none was needed.

**Hard:** the undocumented details. The HMAC key being a string rather than hex bytes cost the most. `payload` always being a list cost the second most, and cost it *after* a successful write, which is the worst time to discover something. Those and eleven others are now in [`docs/gotchas.md`](../../docs/gotchas.md) so they cost you nothing.

**Also hard, but not the API's fault:** deciding where things belong. The first version put a chip lookup inside the CRM appointment drawer. Staff didn't want it there — they don't add animals by hand. It moved. A registry dictionary browser got built and then deleted, because a species list with no breeds isn't useful to anyone. Product decisions, not integration problems.

---

## Who did the work

Most of it: an AI coding agent — writing the signed client, mapping the data model, building the UI, deploying, and verifying against the live API.

The human supplied API credentials, the product decisions above, and approval before anything touched production.

That's the argument this repo exists to make. If an agent can do this end to end, the barrier for your clinic isn't technical difficulty — see [`docs/ai-agent-guide.md`](../../docs/ai-agent-guide.md).

---

*Screenshots of each surface are being added. Want a specific one — booking flow, portal, CRM — open an issue.*
