# Recipe: register an owner and a pet

Two writes, in order: the person, then the animal. The animal links to the person by `user_gid`.

## Step 1 — the owner

```python
from animalid_client import call, first, idempotency_key

def ensure_owner(client):
    """Register/resolve a clinic client as an Animal-ID owner. Returns user_gid."""
    if client.animalid_owner_gid:
        return client.animalid_owner_gid          # already linked

    body = {'consent': {'account_creation': True}}
    if client.email:      body['email'] = client.email
    if client.phone:      body['phone'] = to_e164(client.phone)   # +13055551234
    if client.first_name: body['first_name'] = client.first_name
    if client.last_name:  body['last_name'] = client.last_name
    if not (body.get('email') or body.get('phone')):
        return None                                # nothing to identify them by

    res = first(call('POST', '/owners', body=body,
                     idem=idempotency_key('owner', client.id)))
    gid = res.get('user_gid')
    if gid:
        client.animalid_owner_gid = str(gid)
        client.save()
    return client.animalid_owner_gid
```

`consent.account_creation: true` is you asserting the person agreed. **Get that consent for real** — you're creating someone's identity in a global registry, not a CRM row. In practice that means a checkbox they ticked, not a policy you assume.

The response has both `user_gid` and `public_id`. **Store `user_gid`** — `public_id` is rejected when linking animals ([why](../docs/gotchas.md#4-owners-attach-to-animals-by-user_gid-not-public_id)).

## Step 2 — the animal

```python
SPECIES = {'dog': 3, 'cat': 1}
SEX     = {'f': 0, 'm': 1, 'u': 2}

def ensure_animal(pet):
    """Register a pet (and its owner). Returns the Animal-ID animal id."""
    if pet.animalid_id:
        return pet.animalid_id

    species = SPECIES.get(pet.species)
    if not species:
        return None                        # exotics have no species code

    gid = ensure_owner(pet.client)
    if not gid:
        return None

    body = {
        'species': species,
        'is_microchip': bool(pet.microchip),
        'nickname': pet.name,
        'owners': [{'user_gid': int(gid)}],     # a number, not a string
    }
    if pet.microchip:          body['microchip'] = pet.microchip
    if pet.sex in SEX:         body['gender_id'] = SEX[pet.sex]
    if pet.breed:              body['breed'] = pet.breed        # free text
    if pet.color:              body['color'] = pet.color
    if pet.dob:                body['dob'] = pet.dob.isoformat()
    if pet.neutered is not None: body['sterilization'] = bool(pet.neutered)

    res = first(call('POST', '/animals', body=body,
                     idem=idempotency_key('animal', pet.id)))
    pet.animalid_id = res.get('id')            # NanoID — persist it
    pet.save()
    return pet.animalid_id
```

## Idempotency is the point

Both writes use a **stable** key derived from your own primary key. A retry, a double-submit, a redeploy mid-request — none of them can create a duplicate person or a duplicate animal upstream. Get this right before you run it against anything real.

Use a fresh `uuid4()` for `PATCH`, not a stable key ([why](../docs/authentication.md#idempotency)).

## When to call it

Pick a moment your staff already treat as "this pet is now ours": chip implantation, first vaccination, or portal signup. Registering at booking time works too — just make it explicit to the client that they're getting a registry profile, and let them decline.

Best-effort it. Wrap the call in `try/except` at the call site so a registry hiccup never blocks a staff action or a booking.

## Gotchas

- `payload` is a list — unwrap with `first()` ([why](../docs/gotchas.md#3-payload-is-always-a-list))
- No breed dictionary; `breed` is free text ([why](../docs/gotchas.md#8-there-is-no-breeds-dictionary))
- Chip is optional but makes the pet findable ([why](../docs/gotchas.md#10-a-microchip-is-optional--but-its-what-makes-a-pet-findable))
