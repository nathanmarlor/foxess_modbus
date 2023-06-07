"""Constants for foxess_modbus."""
# Base component constants
NAME = "foxess_modbus"
DOMAIN = "foxess_modbus"
DOMAIN_DATA = f"{DOMAIN}_data"

ISSUE_URL = "https://github.com/nathanmarlor/foxess_modbus/issues"

# Icons
ICON = "mdi:format-quote-close"

# Inverter connection types
AUX = "AUX"
LAN = "LAN"

# Inverter models. These need to match the string returned from the inverter
# Also matches config[INVERTER_BASE]
H1 = "H1"
AC1 = "AC1"
AIO_H1 = "AIO-H1"
KH = "KH"
H3 = "H3"
AIO_H3 = "AIO-H3"

# Platforms
SENSOR = "sensor"
BINARY_SENSOR = "binary_sensor"
SELECT = "select"
NUMBER = "number"
PLATFORMS = [SENSOR, BINARY_SENSOR, SELECT, NUMBER]
ATTR_ENTRY_TYPE = "entry_type"

# Modbus Options
ENTITY_ID_PREFIX = "entity_id_prefix"
FRIENDLY_NAME = "friendly_name"
MODBUS_SLAVE = "modbus_slave"
MODBUS_DEVICE = "modbus_device"
MODBUS_TYPE = "modbus_type"
MODBUS_SERIAL_BAUD = "modbus_serial_baud"
POLL_RATE = "poll_rate"
MAX_READ = "max_read"
ADAPTER_ID = "adapter_id"
ROUND_SENSOR_VALUES = "round_sensor_values"
# Used as a key in the inverter config to indicate that the adapter was migrated from config version 1
ADAPTER_WAS_MIGRATED = "adapter_was_migrated"

INVERTER_MODEL = "inverter_model"
INVERTER_BASE = "inverter_base"
INVERTER_CONN = "inverter_conn"
INVERTERS = "inverters"
MODBUS_CLIENTS = "modbus_clients"

CONFIG_SAVE_TIME = "save_time"

HOST = "host"
TCP = "tcp"
UDP = "udp"
SERIAL = "serial"
RTU_OVER_TCP = "rtu_over_tcp"

CONTROLLER = "controllers"
CONFIG = "config"
INVERTER = "inverter"
CONNECTION = "connection"
MODBUS = "modbus"

# Defaults
DEFAULT_NAME = DOMAIN

STARTUP_MESSAGE = f"""
-------------------------------------------------------------------
{NAME}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
