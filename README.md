# Skippo — Home Assistant Integration

Track vessels from [Skippo](https://www.skippo.se) directly in Home Assistant. Each tracked vessel becomes a device with GPS position, speed, online status, and movement state.

No Skippo account is required.

---

## What it does

For every vessel you add, the integration creates four entities grouped under one HA device:

| Entity | Type | Description |
|---|---|---|
| Position | `device_tracker` | GPS latitude and longitude |
| Speed | `sensor` | Speed over ground in knots |
| Online | `binary_sensor` | Vessel is visible in the AIS/Skippo network |
| Moving | `binary_sensor` | Vessel is currently underway (≥ 1.0 kn) |

If a vessel temporarily disappears from the network the last known position is kept, with the **Online** sensor showing `off`, so your dashboards and automations stay intact.

---

## Supported regions

Sweden (`SE`), Norway (`NO`), Denmark (`DK`), Finland (`FI`).

---

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → ⋮ → **Custom repositories**
2. Add `https://github.com/robinostlund/homeassistant-skippo` — category **Integration**
3. Install **Skippo** and restart Home Assistant

### Manual

1. Copy the `custom_components/skippo` folder into your HA `config/custom_components/` directory
2. Restart Home Assistant

---

## Configuration

Go to **Settings → Devices & Services → Add integration → Skippo**.

1. **Select region** — choose the AIS region where your vessel operates
2. **Add vessel** — enter the vessel ID (see below) and an optional friendly name
3. Check **Add another vessel** to track multiple boats

### Adding a vessel that is currently offline

If the vessel is not broadcasting AIS right now (e.g. it is in a marina), enter its ID and tick **Add anyway — vessel may currently be offline**. It will start showing data as soon as it comes online.

### Managing vessels later

Open the integration and click **Configure** to:

- **Add a vessel** — add another boat to track
- **Remove vessel(s)** — stop tracking selected vessels. You can also delete a vessel device directly from the device page in HA.
- **Settings** — adjust the polling interval (30–3600 seconds, default 60 s)

### Changing the region

Use **⋮ → Reconfigure** on the integration card to switch to a different AIS region.

---

## Finding your vessel ID

There are two types of vessel IDs:

### MMSI — AIS-equipped vessels

An MMSI (Maritime Mobile Service Identity) is a 9-digit number assigned to every vessel with an AIS transponder. You can find yours in several ways:

- **On the transponder itself** — the MMSI is printed on the device or shown in its settings menu
- **Ship documents or radio licence** — the MMSI is issued together with the vessel's radio licence
- **Online AIS sites** — search your boat name on [MarineTraffic](https://www.marinetraffic.com), [VesselFinder](https://www.vesselfinder.com), or [AISHub](https://www.aishub.net). The 9-digit number in the vessel detail page is your MMSI.
- **The included test script** (see below)

### Skippo user vessel ID

If your boat is registered in the Skippo app but does not have an AIS transponder, it is assigned a non-numeric Skippo ID. You can find it using the test script below.

---

## Finding vessels with the test script

The repository includes `test_skippo.py`, a standalone script that queries the live API and prints a list of vessels with their IDs — no dependencies beyond `aiohttp`.

```bash
pip install aiohttp
python3 test_skippo.py --target SE          # list vessels in Sweden
python3 test_skippo.py --target SE --limit 0  # include name and speed for all moving vessels
```

Example output:

```
ID                             Lat          Lon   Course  Moving  Anchored
--------------------------------------------------------------------------------
265023580                  57.70234     11.96538   270.0°     yes        no
265034812                  59.33458     18.07621     —         no        no
…
```

To look up a specific vessel by ID:

```bash
python3 test_skippo.py --vessel 265023580
```

This prints the full detail response for that vessel, including name, speed, call sign, and dimensions.

---

## Entities reference

### `device_tracker` — Position

State reflects HA zone membership. Extra attributes:

| Attribute | Description |
|---|---|
| `course` | Heading in degrees |
| `vessel_name` | Name from AIS data |
| `call_sign` | Radio call sign |
| `length` / `width` / `draught` | Vessel dimensions in metres |
| `country_code` | Flag state |
| `last_seen` | ISO timestamp of last AIS contact |

### `sensor` — Speed

Speed over ground in **knots**. `unknown` when the vessel has no recent AIS fix.

### `binary_sensor` — Online

`on` when the vessel is visible in the AIS/Skippo network. Remains `on` as long as the vessel is broadcasting; switches to `off` when it disappears, while still showing the last known position.

### `binary_sensor` — Moving

`on` when speed over ground is ≥ 1.0 knots. Falls back to Skippo's own moving flag when no speed data is available.

---

## Development

See [CLAUDE.md](CLAUDE.md) for architecture details, API documentation, and a guide to adding new entity types.

```bash
# Run standalone API and structure tests (no Home Assistant required)
pip install aiohttp pytest pytest-asyncio
pytest tests/test_structure.py tests/test_api.py -v

# Run full HA integration tests (clones HA core automatically via CI)
# See .github/workflows/validate-pr.yml
```
