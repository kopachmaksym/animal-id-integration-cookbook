# Recipe: push vaccinations and procedures

Your clinic already records vaccinations. This mirrors them into the registry so the pet's history survives the client moving, your software changing, or your clinic closing.

## Types

Each procedure is typed by an integer, and each type wants different fields in `type_specific_payload`:

| Code | Procedure | `type_specific_payload` |
|---|---|---|
| `10` | Vaccination | `vaccine_name`, `batch_number` |
| `20` | Rabies vaccination | `vaccine_name`, `batch_number` |
| `30` | Transponder / microchip | identifier fields |
| `40` | QR token | token fields |
| `50` | Deworming | `drug` |
| `60` | Sterilization | `method`, `anesthesia_type` |
| `70` | Death | — |

**Rabies is its own type.** File it as `20`, not `10`, or it won't appear where another clinic or a border official expects it.

Unsure about a type you haven't used? Send it with an empty `type_specific_payload` and read the `422` — it names the required fields ([the 422 probe](../docs/ai-agent-guide.md#the-422-probe)).

## Pushing a vaccination

```python
from datetime import datetime, time, timezone
from animalid_client import call, first, idempotency_key

def push_vaccination(vacc):
    animal_id = ensure_animal(vacc.pet)          # see recipes/register.md
    if not animal_id:
        return None

    # occurred_at is a full ISO-8601 timestamp, not a date. If you only
    # store a date, pick a time — midday UTC is a fine convention.
    occurred = datetime.combine(vacc.given_at, time(12, 0),
                                tzinfo=timezone.utc).isoformat()

    is_rabies = 'rabies' in (vacc.name or '').lower()
    body = {
        'type': 20 if is_rabies else 10,
        'occurred_at': occurred,
        'type_specific_payload': {
            'vaccine_name': vacc.name or 'Vaccination',
            'batch_number': vacc.batch_no or 'unspecified',
        },
    }
    if vacc.notes:  body['summary'] = vacc.notes[:250]
    if vacc.due_at: body['revaccination_date'] = vacc.due_at.isoformat()

    return first(call('POST', f'/animals/{animal_id}/procedures', body=body,
                      idem=idempotency_key('vacc', vacc.id)))
```

## Sterilization

```python
def push_sterilization(pet):
    if not pet.animalid_id or not pet.neutered:
        return None
    body = {
        'type': 60,
        'occurred_at': datetime.now(timezone.utc).isoformat(),
        'type_specific_payload': {'method': '...', 'anesthesia_type': '...'},
    }
    return first(call('POST', f'/animals/{pet.animalid_id}/procedures', body=body,
                      idem=idempotency_key('sterilization', pet.id)))
```

## Where to hook it

On save, in whatever already writes the vaccination locally:

```python
vacc.save()
try:
    push_vaccination(vacc)
except Exception:
    log.warning('Animal-ID sync failed for vaccination %s', vacc.id, exc_info=True)
```

Best-effort, always. A registry outage must never stop a vet from recording a shot. The stable idempotency key means you can safely re-run a backfill later to catch anything that failed.

## Backfilling history

Same function, run over existing rows. Because the key is derived from your own primary key, running it twice is harmless:

```python
for vacc in Vaccination.objects.filter(pet__animalid_id__isnull=False):
    try:
        push_vaccination(vacc)
    except Exception as exc:
        log.warning('skip %s: %s', vacc.id, exc)
```

## Gotchas

- `occurred_at` is a timestamp, not a date
- Stable idempotency keys for creates; fresh keys for updates ([why](../docs/authentication.md#idempotency))
- `payload` is a list ([why](../docs/gotchas.md#3-payload-is-always-a-list))
