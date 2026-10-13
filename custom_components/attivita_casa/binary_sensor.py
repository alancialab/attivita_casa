"""Binary sensor platform for Attività Casa.

Espone un binary_sensor "Scaduta" per ogni attività pianificata (mode scheduled):
ON quando l'attività è scaduta (stato EXPIRED), OFF altrimenti. device_class
"problem" così si integra con badge/automazioni standard di Home Assistant.

Riusa le funzioni pure di sensor.py (calculate_days_remaining/classify_state)
per avere ESATTAMENTE la stessa logica del sensore principale. È puramente
additivo: non tocca gli unique_id né le entità sensor esistenti.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .const import (
    CONF_FREQUENCY,
    CONF_ICON,
    CONF_LAST_COMPLETION,
    CONF_MODE,
    CONF_NAME,
    DEFAULT_FREQUENCY,
    DEFAULT_MODE,
    DOMAIN,
    MODE_TRACKER,
    STATE_EXPIRED,
)
from .sensor import (
    UPDATE_INTERVAL,
    calculate_days_remaining,
    classify_state,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the overdue binary sensor from a config entry.

    Solo per attività in modalità scheduled: le tracker non hanno scadenza,
    quindi un binary_sensor "scaduta" non avrebbe senso.
    """
    if entry.data.get(CONF_MODE, DEFAULT_MODE) == MODE_TRACKER:
        return
    async_add_entities([ActivityOverdueBinarySensor(hass, entry)], update_before_add=True)


class ActivityOverdueBinarySensor(BinarySensorEntity):
    """Binary sensor: ON quando l'attività è scaduta."""

    _attr_has_entity_name = True
    _attr_device_class = BinarySensorDeviceClass.PROBLEM

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the overdue binary sensor."""
        self.hass = hass
        self._entry = entry
        # unique_id DISTINTO dal sensore principale (suffisso _scaduta):
        # non collide con attivita_casa_<slug> del sensor esistente.
        self._attr_unique_id = f"attivita_casa_{slugify(entry.data[CONF_NAME])}_scaduta"
        self._attr_name = f"{entry.data[CONF_NAME]} scaduta"
        self._is_on: bool = False
        self._unsub_timer: Any = None

    @property
    def is_on(self) -> bool:
        """Return True se l'attività è scaduta."""
        return self._is_on

    @property
    def icon(self) -> str:
        """Icona: allerta quando scaduta, altrimenti check."""
        return "mdi:alert-circle" if self._is_on else "mdi:check-circle-outline"

    async def async_added_to_hass(self) -> None:
        """Calcola lo stato e pianifica gli aggiornamenti (timer + dispatcher)."""
        self._calculate()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_scheduled_update, UPDATE_INTERVAL
        )
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{DOMAIN}_reset_{self._entry.entry_id}",
                self._async_scheduled_update,
            )
        )

    async def async_will_remove_from_hass(self) -> None:
        """Pulisce il timer alla rimozione."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_scheduled_update(self, now: datetime | None = None) -> None:
        """Aggiornamento orario / su reset."""
        self._calculate()
        self.async_write_ha_state()

    def _calculate(self) -> None:
        """Ricalcola on/off usando la stessa logica del sensore principale."""
        last_completion_str = self._entry.data.get(CONF_LAST_COMPLETION)
        try:
            last_completion = date.fromisoformat(last_completion_str)
        except (TypeError, ValueError):
            _LOGGER.warning(
                "Invalid last_completion date '%s' for activity '%s', using today",
                last_completion_str,
                self._entry.data.get(CONF_NAME),
            )
            last_completion = date.today()

        frequency = self._entry.data.get(CONF_FREQUENCY, DEFAULT_FREQUENCY)
        days_remaining = calculate_days_remaining(last_completion, frequency)
        self._is_on = classify_state(days_remaining) == STATE_EXPIRED
