# Technical license flow (for engineers / LS reviewers)

## Endpoints used by GrabbyVault

Base: `https://api.lemonsqueezy.com`

### 1. Activate

```http
POST /v1/licenses/activate
Accept: application/json
Content-Type: application/x-www-form-urlencoded

license_key=...&instance_name=GrabbyVault-PCNAME-abc123def456
```

**Success:** `activated: true`, `instance.id` (UUID), `license_key.status`  
**Limit reached:** `activated: false`, `error` e.g. “reached the activation limit”

App stores: `license_key`, `instance.id`, machine fingerprint, `meta.product_id`.

### 2. Validate (heartbeat + startup)

```http
POST /v1/licenses/validate
Accept: application/json
Content-Type: application/x-www-form-urlencoded

license_key=...&instance_id=<uuid from activate>
```

**Success:** `valid: true`  
App rejects: `expired` / `disabled` status, missing instance, product_id mismatch (if configured).

### 3. Deactivate (release seat / take-over step 1)

```http
POST /v1/licenses/deactivate
Accept: application/json
Content-Type: application/x-www-form-urlencoded

license_key=...&instance_id=<uuid>
```

**Success:** `deactivated: true`

## Client module

`src/core/license_manager.py` → class `LemonSqueezyClient` + `LicenseManager`

## Rate limits

LS: **60 requests/minute**. Client spaces requests ~1s apart and heartbeats every 180s by default.

## What we do **not** put in the desktop app

- Lemon Squeezy **merchant API key** (not required for license activate/validate/deactivate)
- Webhook secrets

## Optional production config

```json
"lemonsqueezy_product_ids": [12345],
"lemonsqueezy_variant_ids": [67890],
"allow_dev_keys": false,
"license_single_seat": true,
"license_heartbeat_seconds": 180
```

When product/variant IDs are set, keys for other products are rejected after activate (and the accidental activation is deactivated when possible).

## Reference docs

- https://docs.lemonsqueezy.com/api/license-api  
- https://docs.lemonsqueezy.com/api/license-api/activate-license-key  
- https://docs.lemonsqueezy.com/api/license-api/validate-license-key  
- https://docs.lemonsqueezy.com/api/license-api/deactivate-license-key  
