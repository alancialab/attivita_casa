"""Service handlers for Attività Casa."""

from __future__ import annotations

import logging
from datetime import date, timedelta

import voluptuous as vol

from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .const import (
    ATTR_CALENDAR_ENTITY,
    ATTR_DATE,
    ATTR_DAYS,
    ATTR_ENTITY_ID,
    CONF_CALENDAR_ENTITY,
    CONF_COMPLETION_HISTORY,
    CONF_FREQUENCY,
    CONF_LAST_COMPLETION,
    CONF_LAST_COMPLETION_BEFORE_SNOOZE,
    CONF_NAME,
    DOMAIN,
    MAX_HISTORY,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_RESET = "reset"
SERVICE_SNOOZE = "snooze"
SERVICE_UNDO_SNOOZE = "undo_snooze"
SERVICE_SET_DATE = "set_date"

SERVICE_RESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Optional(ATTR_CALENDAR_ENTITY): cv.entity_id,
        # Data di completamento opzionale: se assente, usa oggi.
        vol.Optional(ATTR_DATE): cv.date,
    }
)

SERVICE_SNOOZE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DAYS): vol.All(int, vol.Range(min=1, max=365)),
    }
)

SERVICE_SET_DATE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
        vol.Required(ATTR_DATE): cv.date,
    }
)

SERVICE_UNDO_SNOOZE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_ENTITY_ID): cv.entity_id,
    }
)


def _find_entry_for_entity(
    hass: HomeAssistant, entity_id: str
) -> object | None:
    """Find the config entry matching the given entity_id."""
    from homeassistant.helpers import entity_registry as er
    from homeassistant.util import slugify

    # First try direct match by expected entity_id pattern
    for entry in hass.config_entries.async_entries(DOMAIN):
        expected_unique_id = f"attivita_casa_{slugify(entry.data.get(CONF_NAME, ''))}"
        expected_entity_id = f"sensor.{expected_unique_id}"
        if entity_id == expected_entity_id:
            return entry

    # Fallback: check entity registry for matching unique_id
    try:
        registry = er.async_get(hass)
        entity_entry = registry.async_get(entity_id)
        if entity_entry and entity_entry.unique_id:
            for entry in hass.config_entries.async_entries(DOMAIN):
                expected_uid = f"attivita_casa_{slugify(entry.data.get(CONF_NAME, ''))}"
                if entity_entry.unique_id == expected_uid:
                    return entry
    except Exception:  # noqa: BLE001
        pass

    return None


def _signal_sensor_update(hass: HomeAssistant, entry) -> None:
    """Signal the sensor to recalculate."""
    from homeassistant.helpers.dispatcher import async_dispatcher_send

    async_dispatcher_send(hass, f"{DOMAIN}_reset_{entry.entry_id}")


async def async_handle_reset(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the reset service call."""
    entity_id = call.data[ATTR_ENTITY_ID]

    entry = _find_entry_for_entity(hass, entity_id)
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity",
            translation_placeholders={"entity_id": entity_id},
        )

    # Data di completamento: quella passata dal servizio, oppure oggi.
    completion_date = call.data.get(ATTR_DATE) or date.today()

    # Update completion history (usa la data scelta, non forzatamente oggi).
    history = list(entry.data.get(CONF_COMPLETION_HISTORY, []))
    history.append(completion_date.isoformat())
    # Mantiene lo storico ordinato per data e limita alle ultime MAX_HISTORY.
    history = sorted(history)[-MAX_HISTORY:]

    # Update last completion date and save history
    new_data = {
        **entry.data,
        CONF_LAST_COMPLETION: completion_date.isoformat(),
        CONF_COMPLETION_HISTORY: history,
    }
    hass.config_entries.async_update_entry(entry, data=new_data)

    _signal_sensor_update(hass, entry)

    # Determine calendar entity: from service call or from config
    calendar_entity = call.data.get(ATTR_CALENDAR_ENTITY)
    if not calendar_entity:
        calendar_entity = entry.data.get(CONF_CALENDAR_ENTITY, "")

    # Create calendar event if calendar is configured
    if calendar_entity:
        frequency = entry.data.get(CONF_FREQUENCY, 30)
        next_due = completion_date + timedelta(days=frequency)
        try:
            await hass.services.async_call(
                "calendar",
                "create_event",
                {
                    "summary": entry.data[CONF_NAME],
                    "start_date": next_due.isoformat(),
                    "end_date": (next_due + timedelta(days=1)).isoformat(),
                    "description": "Prossima scadenza attività",
                },
                target={"entity_id": calendar_entity},
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.error(
                "Failed to create calendar event for activity '%s'",
                entry.data.get(CONF_NAME),
            )


async def async_handle_snooze(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the snooze service call — postpone deadline by N days."""
    entity_id = call.data[ATTR_ENTITY_ID]
    snooze_days = call.data[ATTR_DAYS]

    entry = _find_entry_for_entity(hass, entity_id)
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity",
            translation_placeholders={"entity_id": entity_id},
        )

    # Save current last_completion before snooze for undo
    last_completion_str = entry.data.get(CONF_LAST_COMPLETION)
    try:
        last_completion = date.fromisoformat(last_completion_str)
    except (TypeError, ValueError):
        last_completion = date.today()

    new_last_completion = last_completion + timedelta(days=snooze_days)

    new_data = {
        **entry.data,
        CONF_LAST_COMPLETION_BEFORE_SNOOZE: last_completion.isoformat(),
        CONF_LAST_COMPLETION: new_last_completion.isoformat(),
    }
    hass.config_entries.async_update_entry(entry, data=new_data)

    _signal_sensor_update(hass, entry)

    _LOGGER.info(
        "Activity '%s' snoozed by %d days (previous: %s)",
        entry.data.get(CONF_NAME),
        snooze_days,
        last_completion.isoformat(),
    )


async def async_handle_undo_snooze(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the undo_snooze service call — revert last snooze."""
    entity_id = call.data[ATTR_ENTITY_ID]

    entry = _find_entry_for_entity(hass, entity_id)
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity",
            translation_placeholders={"entity_id": entity_id},
        )

    previous_date_str = entry.data.get(CONF_LAST_COMPLETION_BEFORE_SNOOZE)
    if not previous_date_str:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="no_snooze_to_undo",
            translation_placeholders={"entity_id": entity_id},
        )

    new_data = {
        **entry.data,
        CONF_LAST_COMPLETION: previous_date_str,
        CONF_LAST_COMPLETION_BEFORE_SNOOZE: "",
    }
    hass.config_entries.async_update_entry(entry, data=new_data)

    _signal_sensor_update(hass, entry)

    _LOGGER.info(
        "Activity '%s' snooze undone, reverted to %s",
        entry.data.get(CONF_NAME),
        previous_date_str,
    )


async def async_handle_set_date(hass: HomeAssistant, call: ServiceCall) -> None:
    """Handle the set_date service call — manually set last completion date."""
    entity_id = call.data[ATTR_ENTITY_ID]
    new_date = call.data[ATTR_DATE]

    entry = _find_entry_for_entity(hass, entity_id)
    if entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_entity",
            translation_placeholders={"entity_id": entity_id},
        )

    new_data = {
        **entry.data,
        CONF_LAST_COMPLETION: new_date.isoformat(),
    }
    hass.config_entries.async_update_entry(entry, data=new_data)

    _signal_sensor_update(hass, entry)

    _LOGGER.info(
        "Activity '%s' last completion manually set to %s",
        entry.data.get(CONF_NAME),
        new_date.isoformat(),
    )


def async_register_services(hass: HomeAssistant) -> None:
    """Register the attivita_casa services."""
    if hass.services.has_service(DOMAIN, SERVICE_RESET):
        return

    async def handle_reset(call: ServiceCall) -> None:
        await async_handle_reset(hass, call)

    async def handle_snooze(call: ServiceCall) -> None:
        await async_handle_snooze(hass, call)

    async def handle_undo_snooze(call: ServiceCall) -> None:
        await async_handle_undo_snooze(hass, call)

    async def handle_set_date(call: ServiceCall) -> None:
        await async_handle_set_date(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_RESET,
        handle_reset,
        schema=SERVICE_RESET_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SNOOZE,
        handle_snooze,
        schema=SERVICE_SNOOZE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_UNDO_SNOOZE,
        handle_undo_snooze,
        schema=SERVICE_UNDO_SNOOZE_SCHEMA,
    )

    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_DATE,
        handle_set_date,
        schema=SERVICE_SET_DATE_SCHEMA,
    )
