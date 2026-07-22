# Animal-ID Integration Cookbook

> Practical recipes for the [Animal-ID](https://animal-id.net) partner API — bring the global pet registry into the software your clinic already uses.

**The point:** your clinic doesn't have to send staff or clients to `animal-id.net`. Everything the registry offers — microchip lookup, pet registration, medical history, owner consent — is available through the partner API. It can live inside your own site, booking flow, client portal or CRM.

This repo shows **how**, with working recipes and one real integration as a case study.

---

## What you can build

| Capability | What it gives the clinic | Recipe |
|---|---|---|
| Lookup by microchip / QR | Identify any pet in the registry — found strays, new patients at intake | [`recipes/lookup`](recipes/lookup.md) |
| Register owner + pet | Your patients get a global ID that follows them between clinics | [`recipes/register`](recipes/register.md) |
| Medical procedures | Vaccinations, sterilization and more, recorded once, visible everywhere | [`recipes/procedures`](recipes/procedures.md) |
| Global history | See what **other** clinics recorded for this pet | [`recipes/history`](recipes/history.md) |
| Owner's animals | Every pet linked to an owner — including ones you've never seen | [`recipes/by-owner`](recipes/by-owner.md) |
| Photos | The pet's real photo on its registry profile | [`recipes/photos`](recipes/photos.md) |
| Access + webhooks | Consent-based access to pets you don't own | [`recipes/access`](recipes/access.md) |

---

## Is this hard to build? No.

This cookbook came out of **one real integration** into a working veterinary site — public pages, booking funnel, client portal and staff CRM. It took a few days, and most of the work was done by an **AI agent**: reading the docs, writing a signed client, mapping the data model, building the UI, deploying and verifying against the live API.

The human supplied two things the AI could not: **API credentials** and a handful of product decisions.

That's the second point of this repo — if an AI agent can integrate this API end to end, so can your team.

See [`case-studies/green-pines`](case-studies/green-pines/README.md) for what was built, screenshots, and how long each part took.

---

## Start here

1. **Create an organization page in Animal-ID.** This is the only manual prerequisite — it issues your **App ID**, **public/private key** and **webhook secret**. Without an organization there are no credentials and no API access.
2. Read [`docs/authentication.md`](docs/authentication.md) — request signing in ~20 lines.
3. Copy [`examples/python/animalid_client.py`](examples/python/animalid_client.py) — a complete signed client, standard library only, no dependencies. Run it directly to verify your credentials.
4. Pick a recipe above and copy it.

Full docs:

| | |
|---|---|
| [`docs/authentication.md`](docs/authentication.md) | Signing, idempotency, webhooks, and a 401 checklist |
| [`docs/endpoints.md`](docs/endpoints.md) | Every endpoint, and what it's actually good for in a clinic |
| [`docs/gotchas.md`](docs/gotchas.md) | 14 undocumented things that cost us hours |
| [`docs/ai-agent-guide.md`](docs/ai-agent-guide.md) | Handing this integration to an AI agent — what works, what doesn't |

---

## Gotchas the docs don't cover

Hard-won from a real integration — these cost hours to discover and are documented in [`docs/gotchas.md`](docs/gotchas.md):

- the HMAC key is the private key **as a string**, not hex-decoded bytes
- the success envelope wraps every resource in a **list**, even single ones
- owners attach to animals by **`user_gid`**, not `public_id`
- search takes **`email_or_phone`**, not `email` / `phone`
- `expand` is a **header**, not a query parameter
- photo upload is multipart and signs with an **empty-body** hash

---

## Repo layout

```
docs/          authentication, endpoint reference, gotchas, AI-agent guide
recipes/       copy-paste recipes, one file per capability
examples/      a minimal signed client (Python, standard library only)
case-studies/  real integrations — what was built and what it took
```

---

## Status

Early and growing. Recipes land as they're proven against the live API.
Issues and pull requests welcome — especially from clinics integrating their own systems.

## License

MIT — see [LICENSE](LICENSE). Not an official Animal-ID project; built by an integrator.
