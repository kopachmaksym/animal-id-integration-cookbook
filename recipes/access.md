# Recipe: request access to another clinic's pet

You can *find* an animal registered by another clinic. You cannot read its full record until the owner approves. This is a feature — it's someone's pet's medical history — and the API gives you a clean way to ask.

## The flow

```python
from animalid_client import call, first, idempotency_key

def request_access(pet):
    """Ask the owner to grant this clinic access."""
    return first(call('POST', f'/animals/{pet.animalid_id}/access-request',
                      idem=idempotency_key('access', pet.id)))


def access_status(animal_id):
    """pending / approved / denied."""
    return first(call('GET', f'/animals/{animal_id}/access-request'))
```

Store the request locally so staff can see it's pending rather than clicking "request" three more times:

```python
class AnimalIDAccessRequest(models.Model):
    animal_id    = models.CharField(max_length=64, unique=True)
    status       = models.CharField(max_length=16, default='pending')  # pending/approved/denied/expired
    requested_by = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    note         = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
```

## `403` is not a bug

Reading a record you don't have access to returns **`403`, not `404`**. The animal exists and you can see it in search results — you just can't read the details.

Build the UI around that:

```python
try:
    card = first(call('GET', f'/animals/{animal_id}'))
except AnimalIDError as exc:
    if exc.status == 403:
        return {'locked': True, 'can_request': True}
    raise
```

Show what you have (name, species, that it's registered), state plainly that the owner hasn't granted access, and offer one button. A dead end here is the difference between staff using the integration and ignoring it.

## Reacting via webhook

Rather than polling, let the registry tell you when the owner answers.

```python
from animalid_client import verify_webhook

@csrf_exempt
def animalid_webhook(request):
    raw = request.body
    ok = verify_webhook(
        settings.ANIMALID_WEBHOOK_SECRET,
        request.method, request.path, raw,
        request.headers.get('X-Eternity-Webhook-Timestamp'),
        request.headers.get('X-Eternity-Webhook-Signature'),
    )
    if not ok:
        return HttpResponse(status=401)

    # Reject stale deliveries so a captured request can't be replayed.
    ts = int(request.headers.get('X-Eternity-Webhook-Timestamp') or 0)
    if abs(time.time() - ts) > 300:
        return HttpResponse(status=401)

    event = request.headers.get('X-Eternity-Webhook-Event') or ''
    delivery_id = request.headers.get('X-Eternity-Webhook-Id') or ''
    # Dedupe on delivery_id — retries are expected.
    handle(event, json.loads(raw or b'{}'))
    return HttpResponse(status=200)
```

Same signing scheme as the API, keyed with the **webhook secret** ([details](../docs/authentication.md#webhooks)).

> The secret starts with `whsec_`, which is the Svix convention — but this is **not** Svix. Don't install a Svix SDK; verify it with the HMAC you already wrote.

**Code the handler defensively.** Verify the payload shape against your own deliveries before depending on specific field names — read the event from the header, treat the body as a hint, and re-fetch `GET /animals/{id}/access-request` to get authoritative status rather than trusting a field you haven't seen arrive.

## Gotchas

- `403` means consent, not error
- Always verify the signature **before** parsing the body
- Dedupe on `X-Eternity-Webhook-Id`; deliveries can repeat
- Don't reach for a Svix library because of the `whsec_` prefix
