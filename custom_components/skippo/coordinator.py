import logging

import aiohttp
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import async_fetch_basic_auth, invalidate_basic_auth_cache
from .const import API_BASE_URL, API_HEADERS, DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


def _parse_detail(raw: dict) -> dict:
    """Flatten the detail endpoint response into a simple vessel dict."""
    loc = raw.get("location", {})
    result: dict = {
        "lat": loc.get("lat"),
        "lon": loc.get("lon"),
        "course": loc.get("course"),
        "speed_knots": loc.get("speed"),  # SOG in knots
        "anchored": loc.get("aisAnchored", False),
        "active": loc.get("active", True),
        "ts": loc.get("timestamp"),
        "vessel_name": raw.get("name"),
        "length": raw.get("length"),
        "width": raw.get("width"),
        "draught": raw.get("draught"),
        "call_sign": raw.get("aisData", {}).get("callSign"),
        "country_code": raw.get("countryCode"),
    }
    if result["vessel_name"] is None:
        profiles = raw.get("user", {}).get("boatProfiles", [])
        if profiles:
            result["vessel_name"] = profiles[0].get("boatName")
    return result


class SkippoCoordinator(DataUpdateCoordinator[dict[str, dict]]):
    """Single coordinator that polls mapAll once and serves all tracked vessels.

    When a vessel disappears from the API response, the last known position is
    preserved in the returned data with ``online=False`` so entities can continue
    to display the last seen location.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        vessel_ids: set[str],
        target: str,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.vessel_ids = vessel_ids
        self._base_headers = {**API_HEADERS, "target": target}
        self._last_known: dict[str, dict] = {}

    @property
    def _session(self) -> aiohttp.ClientSession:
        return async_get_clientsession(self.hass)

    async def _build_headers(self) -> dict:
        basic = await async_fetch_basic_auth(self._session)
        return {**self._base_headers, "authorization": f"Basic {basic}"}

    async def _fetch_map_all(self, headers: dict) -> list[dict] | None:
        async with self._session.get(
            f"{API_BASE_URL}/data/mapAll",
            headers=headers,
        ) as resp:
            if resp.status == 401:
                return None
            resp.raise_for_status()
            return await resp.json(content_type=None)

    async def _async_update_data(self) -> dict[str, dict]:
        try:
            headers = await self._build_headers()
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Failed to build API headers: {err}") from err

        try:
            all_vessels = await self._fetch_map_all(headers)
            if all_vessels is None:
                # Basic auth credential may have changed — invalidate and retry once
                _LOGGER.warning("Skippo API returned 401 — re-fetching Basic auth credential")
                invalidate_basic_auth_cache()
                headers = await self._build_headers()
                all_vessels = await self._fetch_map_all(headers)
                if all_vessels is None:
                    raise UpdateFailed(
                        "Skippo API returned 401 after re-scraping — check network or Skippo service"
                    )
        except aiohttp.ClientError as err:
            raise UpdateFailed(f"Error communicating with Skippo API: {err}") from err

        online_ids: set[str] = set()
        result: dict[str, dict] = {}

        for v in all_vessels:
            vid = v.get("id")
            if vid not in self.vessel_ids:
                continue
            online_ids.add(vid)
            vessel = dict(v)
            vessel["online"] = True
            result[vid] = vessel

        # Fetch detail for online vessels to get SOG, name, dimensions
        for vessel_id in online_ids:
            try:
                detail_headers = {k: v for k, v in headers.items() if k != "target"}
                async with self._session.get(
                    f"{API_BASE_URL}/data/2412/{vessel_id}",
                    headers=detail_headers,
                ) as resp:
                    if resp.status == 200:
                        detail = await resp.json(content_type=None)
                        parsed = _parse_detail(detail)
                        result[vessel_id].update(
                            {k: v for k, v in parsed.items() if v is not None}
                        )
            except aiohttp.ClientError as err:
                _LOGGER.debug("Could not fetch detail for %s: %s", vessel_id, err)

            self._last_known[vessel_id] = result[vessel_id]

        # Inject stale data for offline vessels
        for vessel_id in self.vessel_ids - online_ids:
            if vessel_id in self._last_known:
                stale = dict(self._last_known[vessel_id])
                stale["online"] = False
                result[vessel_id] = stale
                _LOGGER.debug("Vessel %s offline — using last known position", vessel_id)

        return result
