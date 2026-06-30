import logging

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import async_fetch_basic_auth
from .const import (
    API_BASE_URL,
    API_HEADERS,
    CONF_ADD_ANOTHER,
    CONF_TARGET,
    CONF_VESSEL_ID,
    CONF_VESSEL_NAME,
    CONF_VESSELS,
    DEFAULT_TARGET,
    DOMAIN,
    TARGET_REGIONS,
)

_LOGGER = logging.getLogger(__name__)


async def _vessel_exists(hass, vessel_id: str, target: str) -> tuple[bool, str | None]:
    """Check if vessel ID exists in mapAll. Returns (found, error_key)."""
    session = async_get_clientsession(hass)
    try:
        basic = await async_fetch_basic_auth(session)
        async with session.get(
            f"{API_BASE_URL}/data/mapAll",
            headers={**API_HEADERS, "authorization": f"Basic {basic}", "target": target},
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            if resp.status != 200:
                return False, "cannot_connect"
            vessels: list[dict] = await resp.json(content_type=None)
            return any(v.get("id") == vessel_id for v in vessels), None
    except aiohttp.ClientError:
        return False, "cannot_connect"


class SkippoConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Two-step flow: select region → add first vessel."""

    VERSION = 1
    _data: dict

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 1: choose target region."""
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        if user_input is not None:
            self._data = {
                CONF_TARGET: user_input.get(CONF_TARGET, DEFAULT_TARGET),
                CONF_VESSELS: {},
            }
            return await self.async_step_vessel()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_TARGET, default=DEFAULT_TARGET): vol.In(TARGET_REGIONS),
            }),
        )

    async def async_step_vessel(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        """Step 2 (repeatable): add a vessel to track."""
        errors: dict[str, str] = {}

        if user_input is not None:
            vessel_id = user_input[CONF_VESSEL_ID].strip()
            vessel_name = user_input.get(CONF_VESSEL_NAME, "").strip() or vessel_id

            if vessel_id in self._data[CONF_VESSELS]:
                errors[CONF_VESSEL_ID] = "vessel_already_added"
            else:
                found, error = await _vessel_exists(
                    self.hass, vessel_id, self._data[CONF_TARGET]
                )
                if error:
                    errors["base"] = error
                elif not found:
                    errors[CONF_VESSEL_ID] = "vessel_not_found"
                else:
                    self._data[CONF_VESSELS][vessel_id] = vessel_name

                    if user_input.get(CONF_ADD_ANOTHER):
                        return await self.async_step_vessel()

                    return self.async_create_entry(title="Skippo", data=self._data)

        added = len(self._data.get(CONF_VESSELS, {}))
        return self.async_show_form(
            step_id="vessel",
            data_schema=vol.Schema({
                vol.Required(CONF_VESSEL_ID): str,
                vol.Optional(CONF_VESSEL_NAME): str,
                vol.Optional(CONF_ADD_ANOTHER, default=False): bool,
            }),
            errors=errors,
            description_placeholders={"added": str(added)},
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "SkippoOptionsFlow":
        return SkippoOptionsFlow(config_entry)


class SkippoOptionsFlow(config_entries.OptionsFlow):
    """Options flow: add or remove tracked vessels."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self._entry = entry
        self._vessels: dict[str, str] = dict(entry.data.get(CONF_VESSELS, {}))

    async def async_step_init(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options=["add_vessel", "remove_vessel"],
        )

    async def async_step_add_vessel(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            vessel_id = user_input[CONF_VESSEL_ID].strip()
            vessel_name = user_input.get(CONF_VESSEL_NAME, "").strip() or vessel_id

            if vessel_id in self._vessels:
                errors[CONF_VESSEL_ID] = "vessel_already_added"
            else:
                found, error = await _vessel_exists(
                    self.hass,
                    vessel_id,
                    self._entry.data.get(CONF_TARGET, DEFAULT_TARGET),
                )
                if error:
                    errors["base"] = error
                elif not found:
                    errors[CONF_VESSEL_ID] = "vessel_not_found"
                else:
                    self._vessels[vessel_id] = vessel_name
                    return self._save()

        return self.async_show_form(
            step_id="add_vessel",
            data_schema=vol.Schema({
                vol.Required(CONF_VESSEL_ID): str,
                vol.Optional(CONF_VESSEL_NAME): str,
            }),
            errors=errors,
        )

    async def async_step_remove_vessel(
        self, user_input: dict | None = None
    ) -> config_entries.FlowResult:
        if not self._vessels:
            return self.async_abort(reason="no_vessels")

        if user_input is not None:
            for vid in user_input.get("vessel_ids", []):
                self._vessels.pop(vid, None)
            return self._save()

        options = [
            selector.SelectOptionDict(value=vid, label=f"{name} ({vid})")
            for vid, name in self._vessels.items()
        ]
        return self.async_show_form(
            step_id="remove_vessel",
            data_schema=vol.Schema({
                vol.Required("vessel_ids"): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=options, multiple=True)
                ),
            }),
        )

    def _save(self) -> config_entries.FlowResult:
        self.hass.config_entries.async_update_entry(
            self._entry,
            data={**self._entry.data, CONF_VESSELS: self._vessels},
        )
        return self.async_create_entry(title="", data={})
