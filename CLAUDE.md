# Skippo — Home Assistant Custom Integration

Tracks vessels from [Skippo](https://www.skippo.se) and exposes them as HA entities.

---

## Architecture overview

```
custom_components/skippo/
├── const.py          — All configurable constants (URLs, keys, field names)
├── auth.py           — Firebase auth + Basic auth scraping
├── coordinator.py    — DataUpdateCoordinator: one poll per 60 s, shared by all entities
├── config_flow.py    — Config flow (login + vessel picker) + Options flow (add/remove)
├── __init__.py       — Entry setup, teardown, reload-on-change listener
├── device_tracker.py — GPS position entity per vessel
├── sensor.py         — Speed (knots) sensor per vessel
├── binary_sensor.py  — Online/offline connectivity sensor per vessel
├── manifest.json
├── strings.json      — UI strings + translations source
└── translations/     — Per-locale copies of strings.json
```

---

## API authentication — two layers

Every request to `boat-data-service.skippo.io` requires **both** headers simultaneously:

| Header | Value | Notes |
|---|---|---|
| `Authorization` | `Basic <b64>` | App-level credential. Scraped from Skippo's JS bundle at startup. Fallback hardcoded in `const.py:BASIC_AUTH_FALLBACK`. |
| `id-token` | Firebase JWT | User-level credential. Rotated every 60 min via refresh token. |
| `target` | `SE` / `NO` / `DK` / `FI` | Region filter, set at config time. |

### How Basic auth is obtained (auth.py)

1. Fetch `https://www.skippo.se/plan` (the Skippo Next.js app).
2. Extract all `/_next/static/chunks/*.js` URLs from the HTML.
3. Fetch all chunks in parallel and regex-search for:
   - `concat("webClient",":").concat("<secret>")` — minified btoa form
   - `btoa("webClient:<secret>")` — non-minified form
4. Base64-encode `webClient:<secret>` → `Authorization: Basic <result>`.
5. Cache result for the HA session lifetime.
6. On a `401` from the API, invalidate cache and retry once (self-healing if Skippo redeploys).

### Firebase auth flow (auth.py — SkippoAuth)

- **Login**: `POST identitytoolkit.googleapis.com/v1/accounts:signInWithPassword` with email + password.
- **Refresh**: `POST securetoken.googleapis.com/v1/token` with the refresh token.
- The **refresh token** (not the password) is stored in `entry.data`. Tokens are rotated automatically before expiry (`FIREBASE_TOKEN_EXPIRY_MARGIN = 300 s`).
- Firebase project: `nautical-app-se`. API key: `const.py:FIREBASE_API_KEY`.

---

## API endpoints

Base URL: `https://boat-data-service.skippo.io`

| Endpoint | Method | Purpose |
|---|---|---|
| `/data/mapAll` | GET | All vessels in the target region. Polled once per interval. |
| `/data/2412/{vessel_id}` | GET | Detail for a single vessel (name, SOG, dimensions, callsign). |

### mapAll response schema (per vessel)
```json
{ "id": "...", "lat": 0.0, "lon": 0.0, "c": 270.0, "t": 1,
  "s": 1,        // 0 = stopped, 1 = moving (NOT speed in knots)
  "a": false,    // anchored
  "ts": 1720000000000 }
```

### Detail response schema (relevant fields)
```json
{
  "name": "My Boat",
  "location": { "lat": 0.0, "lon": 0.0, "course": 270.0, "speed": 5.2, "aisAnchored": false, "timestamp": 1720000000000 },
  "aisData": { "callSign": "SABCD" },
  "length": 10.5, "width": 3.2, "draught": 1.1,
  "countryCode": "SE"
}
```

> `location.speed` is SOG in **knots**. The `s` field in mapAll is binary (0/1), not speed.

---

## DataUpdateCoordinator (coordinator.py)

- Polls `mapAll` once per `SCAN_INTERVAL` (60 s).
- Filters the response to only tracked vessel IDs (`coordinator.vessel_ids`).
- For each **online** vessel, fetches the detail endpoint to get SOG and metadata.
- Stores `vessel["online"] = True/False` on every entry.
- **Offline persistence**: if a vessel disappears from mapAll, the last known position is returned with `online=False` so entities don't go unavailable. Last known state is kept in `coordinator._last_known`.

---

## Config entry data schema

Stored in `entry.data` (never `entry.options`):

```python
{
    "email": "user@example.com",       # shown in UI only
    "refresh_token": "...",            # Firebase refresh token (rotated)
    "target": "SE",                    # region
    "vessels": {                       # dict of vessel_id → friendly_name
        "265023580": "My Sailboat",
        "123456789": "Other Boat",
    }
}
```

The raw password is **never** stored.

---

## Entities per vessel

All entities share the same HA device (keyed by `vessel_id`):

| Platform | unique_id | Class | Notes |
|---|---|---|---|
| `device_tracker` | `{vessel_id}_tracker` | `TrackerEntity` | GPS lat/lon + extra attributes |
| `sensor` | `{vessel_id}_speed` | `SensorEntity` | SOG in knots. `None` when no detail available. |
| `binary_sensor` | `{vessel_id}_online` | `BinarySensorEntity` | `True` = vessel visible in mapAll |

Device model: `"AIS"` if `vessel_id` is all digits (MMSI), otherwise `"Skippo User"`.

---

## Adding / removing vessels (Options flow)

The options flow menu (`init` → `add_vessel` / `remove_vessel`) writes changes directly to `entry.data` via `hass.config_entries.async_update_entry`. The `_async_update_listener` in `__init__.py` triggers `async_reload` on any data change, which restarts the coordinator with the updated vessel list.

---

## All configurable constants (const.py)

| Constant | Purpose |
|---|---|
| `API_BASE_URL` | Skippo boat-data API base URL |
| `FIREBASE_API_KEY` | Firebase project API key (nautical-app-se) |
| `FIREBASE_SIGNIN_URL` | Firebase sign-in endpoint |
| `FIREBASE_REFRESH_URL` | Firebase token refresh endpoint |
| `FIREBASE_TOKEN_EXPIRY_MARGIN` | Seconds before expiry to refresh token (300) |
| `SKIPPO_WEB_PLAN_URL` | Page URL used to find JS chunk URLs for Basic auth scraping |
| `BASIC_AUTH_FALLBACK` | Hardcoded fallback Basic auth credential (base64) |
| `SCAN_INTERVAL` | Poll interval (60 s) |
| `MANUFACTURER` | Device manufacturer string (`"Skippo"`) |
| `MODEL_AIS` / `MODEL_USER` | Device model strings |
| `TARGET_REGIONS` / `DEFAULT_TARGET` | Supported regions |
| `CONF_*` | Config entry key strings |

---

## Test script (test_skippo.py)

Standalone script — no HA dependency. Tests API connectivity end-to-end:

```bash
python3 test_skippo.py --email you@example.com --target SE --limit 5
```

On startup it scrapes the Basic auth credential from the JS bundle (same logic as the integration). Prints a table of vessels and fetches detail for moving ones. Useful for verifying credentials and checking what data the API returns for a specific vessel (`--vessel <id>`).

---

## Common development tasks

**Change poll interval**: edit `SCAN_INTERVAL` in `const.py`.

**Add a new entity type**: create `my_platform.py` mirroring the pattern in `sensor.py`, add `Platform.MY_PLATFORM` to `PLATFORMS` in `__init__.py`, add translation keys to `strings.json` and `translations/en.json`.

**API field changed**: update `_parse_detail()` in `coordinator.py` and the relevant entity property.

**Skippo changes its Basic auth credential**: the integration self-heals on the next 401 by re-scraping the JS bundle. The `BASIC_AUTH_FALLBACK` in `const.py` is only used if the web app is unreachable at startup.

**Firebase project changed** (Skippo migrates): update `FIREBASE_API_KEY`, `FIREBASE_SIGNIN_URL`, `FIREBASE_REFRESH_URL` in `const.py`.
