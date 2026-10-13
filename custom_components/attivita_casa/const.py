"""Constants for the Attività Casa integration."""

DOMAIN = "attivita_casa"

CONF_NAME = "name"
CONF_ICON = "icon"
CONF_FREQUENCY = "frequency"
CONF_LAST_COMPLETION = "last_completion"
CONF_NOTIFY_ENABLED = "notify_enabled"
CONF_NOTIFY_SERVICE = "notify_service"
CONF_CALENDAR_ENTITY = "calendar_entity"
CONF_COMPLETION_HISTORY = "completion_history"
CONF_CATEGORY = "category"
CONF_PRIORITY = "priority"
CONF_MODE = "mode"

DEFAULT_ICON = "mdi:checkbox-marked-circle"
DEFAULT_FREQUENCY = 30
DEFAULT_CATEGORY = ""
DEFAULT_PRIORITY = "medium"
DEFAULT_MODE = "scheduled"
MAX_HISTORY = 10

ATTR_ENTITY_ID = "entity_id"
ATTR_CALENDAR_ENTITY = "calendar_entity"
ATTR_DAYS = "days"
ATTR_DATE = "date"

CONF_LAST_COMPLETION_BEFORE_SNOOZE = "last_completion_before_snooze"

MODE_SCHEDULED = "scheduled"
MODE_TRACKER = "tracker"
MODES = [MODE_SCHEDULED, MODE_TRACKER]

PRIORITY_HIGH = "high"
PRIORITY_MEDIUM = "medium"
PRIORITY_LOW = "low"
PRIORITIES = [PRIORITY_HIGH, PRIORITY_MEDIUM, PRIORITY_LOW]

STATE_OK = "ok"
STATE_WARNING = "warning"
STATE_EXPIRED = "expired"
