# Recipe: show the global medical history

This is the payoff. `GET /animals/{id}/procedures` returns what **every** partner clinic recorded for this animal — not just yours. A new patient arrives with a real history instead of "I think she had her shots last spring."

## Fetch and normalize

```python
from animalid_client import call, first, AnimalIDError

LABELS = {10: 'Vaccination', 20: 'Rabies vaccination', 30: 'Microchip',
          40: 'QR tag', 50: 'Deworming', 60: 'Sterilization', 70: 'Deceased'}


def fetch_history(animal_id):
    """The global card + full procedure history. Read-only."""
    try:
        card = first(call('GET', f'/animals/{animal_id}'))
    except AnimalIDError:
        card = {}                       # 403 = no consent; still show procedures

    procedures = []
    for p in call('GET', f'/animals/{animal_id}/procedures') or []:
        tsp = p.get('type_specific_payload') or {}
        procedures.append({
            'type':         p.get('type'),
            'label':        LABELS.get(p.get('type'), 'Procedure'),
            'occurred_at':  (p.get('occurred_at') or '')[:10],
            'summary':      p.get('summary') or '',
            'vaccine_name': tsp.get('vaccine_name'),
            'batch_number': tsp.get('batch_number'),
            'revaccination_date': p.get('revaccination_date'),
        })
    procedures.sort(key=lambda x: x['occurred_at'], reverse=True)
    return {'animal': card, 'procedures': procedures}
```

Filters are available: `?type=`, `?since=`, `?until=`.

## Presenting it

Three rules that came out of real use:

**Label it as external.** Staff must be able to tell at a glance which lines came from your records and which came from the registry. A heading — "Global record (Animal-ID)" — and a distinct visual block is enough.

**Make it read-only.** These entries belong to other clinics. Editing them isn't possible and offering an edit button that fails is worse than no button.

**Show the reason for gaps.** If `GET /animals/{id}` returned `403`, say "the owner hasn't granted access to the full record" and offer [request access](access.md). Don't render an empty panel.

## Where it belongs

- **Staff CRM** — on the pet's clinical page, under your own notes.
- **Client portal** — on the pet's page, so owners see their pet's full history in one place regardless of which clinic did what.

Both surfaces call the same function. Cache it briefly if the page polls; there's no reason to hit the registry on every render.

## Gotchas

- `payload` is a list — the single-animal fetch needs `first()` ([why](../docs/gotchas.md#3-payload-is-always-a-list))
- `403` is normal for animals you don't own ([access](access.md))
- `expand` for related data is the `X-Eternity-Expand` **header** ([why](../docs/gotchas.md#6-expand-is-a-header-not-a-query-parameter))
