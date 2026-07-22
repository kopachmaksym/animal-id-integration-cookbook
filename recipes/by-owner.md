# Recipe: find every pet an owner has

`GET /animals/by-owner` returns all animals linked to a contact — **including pets registered by other clinics**. It turns intake from a form into a confirmation.

## The call

```python
from animalid_client import call, AnimalIDError

def animals_for(email_or_phone):
    try:
        return call('GET', '/animals/by-owner',
                    query={'email_or_phone': email_or_phone})
    except AnimalIDError as exc:
        if exc.status == 404:
            return []
        raise
```

One combined parameter — not `email` / `phone` ([why](../docs/gotchas.md#5-search-takes-email_or_phone-not-email-or-phone)). Normalize phones to E.164 (`+13055551234`) first.

## Use it in the booking flow

A client picks a pet for their appointment. Show their **local** pets and their **registry** pets in one list — and dedupe, or the same animal appears twice and the client picks at random.

Three-step match, most reliable first:

```js
const norm = s => (s || '').toString().trim().toLowerCase();

const merged = localPets.map(p => {
  const match = registryPets.find(a =>
    (p.animalid_id && a.id === p.animalid_id) ||                      // 1. linked id
    (p.microchip && a.microchip && norm(a.microchip) === norm(p.microchip)) ||  // 2. chip
    (norm(a.nickname) && norm(a.nickname) === norm(p.name))           // 3. name
  ) || null;
  return { ...p, registry: match };
});

// Registry pets with no local counterpart, appended once.
const matched = new Set(merged.map(p => p.registry?.id).filter(Boolean));
const extras = registryPets.filter(a => !matched.has(a.id));
```

Badge the registry-sourced entries so the client understands where they came from. When one is selected for a booking, create the local pet record and carry the `animalid_id` and microchip across — otherwise the link is lost and you'll re-register the same animal next time.

## Use it at intake

Staff type the client's phone number and see three pets, one of which your clinic has never treated. That's the moment to [request access](access.md) rather than asking the owner to recite a vaccination history from memory.

## Gotchas

- Carry `animalid_id` **and** `microchip` onto any local record you create from a registry pet — dropping them silently breaks every subsequent sync
- The dedupe order matters: id, then chip, then name. Name-only matching is the fallback, not the rule
- `403` on a returned animal's full record is consent, not failure ([access](access.md))
