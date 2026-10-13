"""Config flow and options flow for Attività Casa."""

from __future__ import annotations

from datetime import date
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import (
    CONF_CALENDAR_ENTITY,
    CONF_CATEGORY,
    CONF_FREQUENCY,
    CONF_ICON,
    CONF_LAST_COMPLETION,
    CONF_MODE,
    CONF_NAME,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_SERVICE,
    CONF_PRIORITY,
    DEFAULT_CATEGORY,
    DEFAULT_FREQUENCY,
    DEFAULT_ICON,
    DEFAULT_MODE,
    DEFAULT_PRIORITY,
    DOMAIN,
    MODE_SCHEDULED,
    MODE_TRACKER,
    MODES,
    PRIORITIES,
)


def _build_user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
    """Build the schema for the user config step."""
    defaults = defaults or {}
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME, default=defaults.get(CONF_NAME, "")
            ): str,
            vol.Required(
                CONF_MODE, default=defaults.get(CONF_MODE, DEFAULT_MODE)
            ): vol.In(MODES),
            vol.Required(
                CONF_ICON, default=defaults.get(CONF_ICON, DEFAULT_ICON)
            ): str,
            vol.Optional(
                CONF_FREQUENCY,
                default=defaults.get(CONF_FREQUENCY, DEFAULT_FREQUENCY),
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                CONF_LAST_COMPLETION,
                default=defaults.get(CONF_LAST_COMPLETION, date.today().isoformat()),
            ): str,
            vol.Optional(
                CONF_CATEGORY,
                default=defaults.get(CONF_CATEGORY, DEFAULT_CATEGORY),
            ): str,
            vol.Optional(
                CONF_PRIORITY,
                default=defaults.get(CONF_PRIORITY, DEFAULT_PRIORITY),
            ): vol.In(PRIORITIES),
            vol.Optional(
                CONF_CALENDAR_ENTITY,
                default=defaults.get(CONF_CALENDAR_ENTITY, ""),
            ): str,
            vol.Required(
                CONF_NOTIFY_ENABLED,
                default=defaults.get(CONF_NOTIFY_ENABLED, False),
            ): bool,
            vol.Optional(
                CONF_NOTIFY_SERVICE,
                default=defaults.get(CONF_NOTIFY_SERVICE, ""),
            ): str,
        }
    )


def _build_options_schema(entry: ConfigEntry) -> vol.Schema:
    """Build the schema for the options flow step."""
    return vol.Schema(
        {
            vol.Required(
                CONF_NAME,
                default=entry.data.get(CONF_NAME, ""),
            ): str,
            vol.Required(
                CONF_MODE,
                default=entry.data.get(CONF_MODE, DEFAULT_MODE),
            ): vol.In(MODES),
            vol.Required(
                CONF_ICON,
                default=entry.data.get(CONF_ICON, DEFAULT_ICON),
            ): str,
            vol.Optional(
                CONF_FREQUENCY,
                default=entry.data.get(CONF_FREQUENCY, DEFAULT_FREQUENCY),
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                CONF_LAST_COMPLETION,
                default=entry.data.get(CONF_LAST_COMPLETION, date.today().isoformat()),
            ): str,
            vol.Optional(
                CONF_CATEGORY,
                default=entry.data.get(CONF_CATEGORY, DEFAULT_CATEGORY),
            ): str,
            vol.Optional(
                CONF_PRIORITY,
                default=entry.data.get(CONF_PRIORITY, DEFAULT_PRIORITY),
            ): vol.In(PRIORITIES),
            vol.Optional(
                CONF_CALENDAR_ENTITY,
                default=entry.data.get(CONF_CALENDAR_ENTITY, ""),
            ): str,
            vol.Required(
                CONF_NOTIFY_ENABLED,
                default=entry.data.get(CONF_NOTIFY_ENABLED, False),
            ): bool,
            vol.Optional(
                CONF_NOTIFY_SERVICE,
                default=entry.data.get(CONF_NOTIFY_SERVICE, ""),
            ): str,
        }
    )


class AttivitaCasaConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Attività Casa."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step — add a new activity."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate name uniqueness
            for entry in self._async_current_entries():
                if entry.data.get(CONF_NAME) == user_input[CONF_NAME]:
                    errors["base"] = "name_exists"
                    break

            # Validate frequency only for scheduled mode
            mode = user_input.get(CONF_MODE, DEFAULT_MODE)
            if mode == MODE_SCHEDULED:
                if user_input.get(CONF_FREQUENCY, 0) < 1:
                    errors[CONF_FREQUENCY] = "invalid_frequency"

            if not errors:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=_build_user_schema(user_input),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AttivitaCasaOptionsFlow:
        """Get the options flow handler."""
        return AttivitaCasaOptionsFlow(config_entry)


class AttivitaCasaOptionsFlow(OptionsFlow):
    """Handle options flow for Attività Casa."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self._entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the options step."""
        if user_input is not None:
            new_data = {**self._entry.data, **user_input}
            new_title = user_input.get(CONF_NAME, self._entry.title)
            self.hass.config_entries.async_update_entry(
                self._entry, data=new_data, title=new_title
            )
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=_build_options_schema(self._entry),
        )
