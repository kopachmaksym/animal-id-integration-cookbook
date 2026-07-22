# Recipe: upload a pet photo

A found-stray lookup that returns a photo shows a recognisable animal. One that returns a chip number shows a database row. Worth the twenty lines.

## The catch

`POST /animals/{id}/photos` is `multipart/form-data`, and **the multipart body is not part of the signature** — you sign an *empty* body hash. Hashing the real bytes returns `401`. This is the only endpoint that behaves this way ([why](../docs/gotchas.md#7-photo-upload-is-multipart-and-signs-an-empty-body)).

The client in [`examples/python/animalid_client.py`](../examples/python/animalid_client.py) already handles it:

```python
from animalid_client import upload_photo, idempotency_key

def push_photo(pet):
    if not pet.animalid_id or not pet.photo:
        return None

    pet.photo.open('rb')
    try:
        data = pet.photo.read()
    finally:
        pet.photo.close()

    filename = os.path.basename(pet.photo.name) or 'pet.jpg'
    content_type = 'image/png' if filename.lower().endswith('.png') else 'image/jpeg'

    return upload_photo(pet.animalid_id, data,
                        filename=filename, content_type=content_type,
                        kind='avatar',
                        # Key off the FILE PATH, not the pet id: re-runs don't
                        # duplicate, but a genuinely new photo uploads fresh.
                        idem=idempotency_key('photo', pet.id, pet.photo.name))
```

## Fields

| Field | Value |
|---|---|
| `file` | image bytes, with filename and content type |
| `kind` | `avatar`, `gallery`, or `nose` |

`avatar` is the profile picture. `nose` is for nose-print identification.

## When to call it

Right after registration, if the pet already has a photo:

```python
animal_id = ensure_animal(pet)
if animal_id and pet.photo:
    try:
        push_photo(pet)
    except Exception:
        log.warning('photo sync failed for pet %s', pet.id, exc_info=True)
```

Never let a failed photo upload fail the registration — the profile is useful without a picture.

Re-call it whenever the local photo changes. Because the idempotency key includes the file path, a new upload gets a new key automatically.

## Removing one

```python
call('DELETE', f'/animals/{animal_id}/photos/{photo_id}')
```

Soft delete.

## Gotchas

- Sign an **empty** body hash, not the multipart bytes
- Set a real `User-Agent` — Cloudflare rejects the default `python-urllib` one ([why](../docs/authentication.md#headers))
- `payload` is a list ([why](../docs/gotchas.md#3-payload-is-always-a-list))
