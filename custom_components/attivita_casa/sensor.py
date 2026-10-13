"""Sensor platform for Attività Casa."""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import slugify

from .const import (
    CONF_CATEGORY,
    CONF_FREQUENCY,
    CONF_ICON,
    CONF_LAST_COMPLETION,
    CONF_LAST_COMPLETION_BEFORE_SNOOZE,
    CONF_MODE,
    CONF_NAME,
    CONF_NOTIFY_ENABLED,
    CONF_NOTIFY_SERVICE,
    CONF_PRIORITY,
    DEFAULT_CATEGORY,
    DEFAULT_MODE,
    DEFAULT_PRIORITY,
    DOMAIN,
    MODE_TRACKER,
    STATE_EXPIRED,
    STATE_OK,
    STATE_WARNING,
)

_LOGGER = logging.getLogger(__name__)

UPDATE_INTERVAL = timedelta(hours=1)

WEEKDAYS_IT = {
    0: "Lun",
    1: "Mar",
    2: "Mer",
    3: "Gio",
    4: "Ven",
    5: "Sab",
    6: "Dom",
}

MONTHS_IT = {
    1: "Gennaio",
    2: "Febbraio",
    3: "Marzo",
    4: "Aprile",
    5: "Maggio",
    6: "Giugno",
    7: "Luglio",
    8: "Agosto",
    9: "Settembre",
    10: "Ottobre",
    11: "Novembre",
    12: "Dicembre",
}


def calculate_days_remaining(last_completion: date, frequency: int) -> int:
    """Calculate days remaining until activity is due."""
    next_due = last_completion + timedelta(days=frequency)
    return (next_due - date.today()).days


def calculate_days_elapsed(last_completion: date) -> int:
    """Calculate days elapsed since last completion."""
    return (date.today() - last_completion).days


def calculate_average_frequency(history: list[str]) -> int | None:
    """Calculate average days between completions from history."""
    if len(history) < 2:
        return None
    dates = []
    for d in history:
        try:
            dates.append(date.fromisoformat(d))
        except (TypeError, ValueError):
            continue
    if len(dates) < 2:
        return None
    dates.sort()
    intervals = [(dates[i + 1] - dates[i]).days for i in range(len(dates) - 1)]
    # Filter out 0-day intervals (same day completions)
    intervals = [i for i in intervals if i > 0]
    if not intervals:
        return None
    return round(sum(intervals) / len(intervals))


def classify_state(days_remaining: int) -> str:
    """Classify activity state from days remaining."""
    if days_remaining > 5:
        return STATE_OK
    if days_remaining >= 1:
        return STATE_WARNING
    return STATE_EXPIRED


def format_date_friendly(d: date) -> str:
    """Format a date in Italian friendly format (e.g. '1 Giugno')."""
    month = MONTHS_IT[d.month]
    return f"{d.day} {month}"


def should_notify(current_state: str, last_notified_state: str | None) -> bool:
    """Determine if a notification should fire on state transition."""
    if last_notified_state is None:
        return current_state in (STATE_WARNING, STATE_EXPIRED)

    if current_state == last_notified_state:
        return False

    valid_transitions = {
        (STATE_OK, STATE_WARNING),
        (STATE_OK, STATE_EXPIRED),
        (STATE_WARNING, STATE_EXPIRED),
    }
    return (last_notified_state, current_state) in valid_transitions


def format_notification_message(name: str, days_remaining: int) -> str:
    """Format the notification message for an activity."""
    if days_remaining <= 0:
        return f"⚠️ L'attività '{name}' è scaduta da {abs(days_remaining)} giorni!"
    return f"⏰ L'attività '{name}' scade tra {days_remaining} giorni."


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the activity sensor from a config entry."""
    async_add_entities([ActivitySensor(hass, entry)], update_before_add=True)


class ActivitySensor(SensorEntity):
    """Sensor representing a recurring household activity."""

    _attr_has_entity_name = True
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the activity sensor."""
        self.hass = hass
        self._entry = entry
        self._attr_unique_id = f"attivita_casa_{slugify(entry.data[CONF_NAME])}"
        self._attr_name = entry.data[CONF_NAME]
        self._days_remaining: int = 0
        self._days_elapsed: int = 0
        self._activity_state: str = STATE_OK
        self._next_due: date = date.today()
        self._overdue_days: int = 0
        self._progress_pct: int = 0
        self._next_due_friendly: str = ""
        self._last_completion_friendly: str = ""
        self._average_frequency: int | None = None
        self._last_notified_state: str | None = None
        self._unsub_timer: Any = None

    @property
    def _mode(self) -> str:
        """Return the activity mode."""
        return self._entry.data.get(CONF_MODE, DEFAULT_MODE)

    @property
    def native_value(self) -> int:
        """Return sensor value based on mode."""
        if self._mode == MODE_TRACKER:
            return self._days_elapsed
        return self._days_remaining

    @property
    def icon(self) -> str:
        """Return the icon for this activity."""
        return self._entry.data.get(CONF_ICON, "mdi:checkbox-marked-circle")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        frequency = self._entry.data.get(CONF_FREQUENCY, 30)
        mode = self._mode
        history = self._entry.data.get("completion_history", [])

        attrs = {
            "activity_name": self._entry.data[CONF_NAME],
            "icon": self._entry.data.get(CONF_ICON, "mdi:checkbox-marked-circle"),
            "mode": mode,
            "last_completion": self._entry.data.get(CONF_LAST_COMPLETION, ""),
            "last_completion_friendly": self._last_completion_friendly,
            "days_elapsed": self._days_elapsed,
            "category": self._entry.data.get(CONF_CATEGORY, DEFAULT_CATEGORY),
            "priority": self._entry.data.get(CONF_PRIORITY, DEFAULT_PRIORITY),
            "completion_history": history,
            "average_frequency": self._average_frequency,
        }

        if mode == MODE_TRACKER:
            # Tracker mode: no frequency, no due date, no state colors
            attrs["state"] = "tracker"
        else:
            # Scheduled mode: full attributes
            attrs.update({
                "frequency": frequency,
                "next_due": self._next_due.isoformat(),
                "next_due_friendly": self._next_due_friendly,
                "state": self._activity_state,
                "days_remaining": self._days_remaining,
                "overdue_days": self._overdue_days,
                "progress_pct": self._progress_pct,
                "calendar_entity": self._entry.data.get("calendar_entity", ""),
                "last_completion_before_snooze": self._entry.data.get(
                    CONF_LAST_COMPLETION_BEFORE_SNOOZE, ""
                ),
            })

        return attrs

    async def async_added_to_hass(self) -> None:
        """Run when entity is added to hass — calculate state and schedule updates."""
        self._calculate_state()
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
        """Clean up timer when entity is removed."""
        if self._unsub_timer:
            self._unsub_timer()
            self._unsub_timer = None

    @callback
    def _async_scheduled_update(self, now: datetime | None = None) -> None:
        """Handle scheduled hourly update."""
        self._calculate_state()
        self.async_write_ha_state()

    def _calculate_state(self) -> None:
        """Recalculate state based on mode."""
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

        # Common calculations
        self._days_elapsed = calculate_days_elapsed(last_completion)
        self._last_completion_friendly = format_date_friendly(last_completion)

        # Calculate average frequency from history
        history = self._entry.data.get("completion_history", [])
        self._average_frequency = calculate_average_frequency(history)

        if self._mode == MODE_TRACKER:
            # Tracker mode: no deadline, just track elapsed days
            self._activity_state = "tracker"
            return

        # Scheduled mode: full calculation
        frequency = self._entry.data.get(CONF_FREQUENCY, 30)

        self._days_remaining = calculate_days_remaining(last_completion, frequency)
        self._next_due = last_completion + timedelta(days=frequency)
        self._next_due_friendly = format_date_friendly(self._next_due)

        # Calculate overdue days (0 if not overdue)
        if self._days_remaining < 0:
            self._overdue_days = abs(self._days_remaining)
        else:
            self._overdue_days = 0

        # Calculate progress percentage (100% = just completed, 0% = due now)
        if frequency > 0:
            elapsed = (date.today() - last_completion).days
            remaining_pct = max(0, min(100, int(((frequency - elapsed) / frequency) * 100)))
            self._progress_pct = remaining_pct
        else:
            self._progress_pct = 0

        new_state = classify_state(self._days_remaining)

        # Check for notification
        if self._entry.data.get(CONF_NOTIFY_ENABLED, False):
            if should_notify(new_state, self._last_notified_state):
                self._send_notification(new_state)

        self._last_notified_state = new_state
        self._activity_state = new_state

    def _send_notification(self, new_state: str) -> None:
        """Send a notification about the activity state change."""
        notify_service = self._entry.data.get(CONF_NOTIFY_SERVICE, "")
        if not notify_service:
            return

        message = format_notification_message(
            self._entry.data[CONF_NAME], self._days_remaining
        )

        parts = notify_service.split(".", 1)
        if len(parts) != 2:
            _LOGGER.warning(
                "Invalid notify_service format '%s' for activity '%s'",
                notify_service,
                self._entry.data.get(CONF_NAME),
            )
            return

        domain, service = parts

        self.hass.async_create_task(
            self.hass.services.async_call(
                domain,
                service,
                {"message": message, "title": "Attività Casa"},
                blocking=False,
            )
        )

    def recalculate(self) -> None:
        """Force recalculation — called after reset service."""
        self._calculate_state()
        self.async_write_ha_state()
