# Recipe: look up a pet by microchip or QR

**Ship this first.** It's read-only, needs no owner consent, and it's the feature that makes the registry obviously worth having — someone finds a stray, types a chip number into *your* site, and gets an answer.

## The call

```python
from animalid_client import call, AnimalIDError

def lookup(identifier):
    """Search across identifier types (microchip, QR token, ...)."""
    try:
        return call('GET', f'/animals/by-identifier/{identifier}')
    except AnimalIDError as exc:
        if exc.status == 404:
            return []
        raise
```

Narrower, when you know the type:

```python
call('GET', f'/animals/by-identifier/microchip/{chip}')
```

Both return a **list** — a chip can match more than one record.

## What you get back

Only the fields you're allowed to see. Enough to confirm identity — name, species, photo, whether it's registered — without exposing the owner's contact details to whoever typed the number.

For the full record you need [access](access.md), or the animal has to be one of yours.

## Wire it into a public page

```python
# Django view — a thin, unauthenticated proxy.
def api_lookup(request):
    q = (request.GET.get('q') or '').strip()
    if len(q) < 6:
        return JsonResponse({'error': 'Enter a valid identifier'}, status=400)
    try:
        animals = lookup(q)
    except AnimalIDError:
        return JsonResponse({'error': 'Registry unavailable'}, status=503)
    return JsonResponse({'results': [
        {'id': a.get('id'), 'name': a.get('nickname'),
         'species': a.get('species'), 'photo': a.get('avatar_url'),
         'profile': f"https://animal-id.net/en/pets/{a.get('id')}"}
        for a in animals
    ]})
```

Two things worth doing:

- **Rate-limit it.** It's a public endpoint hitting a third-party API on your credentials.
- **Link to the public profile** — `https://animal-id.net/en/pets/{id}` — so the finder can go further without you proxying everything.

## Also use it at intake

Same call, different moment: a new patient arrives, staff scan the chip, and the pet's registry record appears before anyone opens a paper file. If it resolves, you can offer to link it to the local record instead of retyping the animal's details.

## Gotchas

- Response `payload` is a **list**, always — [why](../docs/gotchas.md#3-payload-is-always-a-list)
- Chip-less pets exist in the registry but won't be found this way — [why](../docs/gotchas.md#10-a-microchip-is-optional--but-its-what-makes-a-pet-findable)
- `403` on a record you can see in results means consent is required, not that you broke something — [access](access.md)
