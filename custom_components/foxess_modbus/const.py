"""Constants for foxess_modbus."""
# Base component constants
NAME = "foxess_modbus"
DOMAIN = "foxess_modbus"
DOMAIN_DATA = f"{DOMAIN}_data"
VERSION = "1.0.0b2"

ISSUE_URL = "https://github.com/nathanmarlor/foxess_modbus/issues"

# Icons
ICON = "mdi:format-quote-close"

# Platforms
SENSOR = "sensor"
BINARY_SENSOR = "binary_sensor"
SELECT = "select"
NUMBER = "number"
PLATFORMS = [SENSOR, BINARY_SENSOR, SELECT, NUMBER]
ATTR_ENTRY_TYPE = "entry_type"

# Modbus Options
FRIENDLY_NAME = "friendly_name"
MODBUS_HOST = "modbus_host"
MODBUS_PORT = "modbus_port"
MODBUS_SLAVE = "modbus_slave"
MODBUS_DEVICE = "modbus_device"
MODBUS_TYPE = "modbus_type"
MODBUS_SERIAL_HOST = "modbus_serial_host"
MODBUS_SERIAL_BAUD = "modbus_serial_baud"

INVERTER_TYPE = "inverter_type"
INVERTER_MODEL = "inverter_model"
INVERTER_BASE = "inverter_base"
INVERTER_CONN = "inverter_conn"
INVERTERS = "inverters"

ADD_ANOTHER = "add_another"
CONFIG_SAVE_TIME = "save_time"

# Inverter Types
H1 = "H1"
AC1 = "AC1"
H3 = "H3"
LAN = "LAN"
AUX = "AUX"
TCP = "TCP"
SERIAL = "SERIAL"

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
Version: {VERSION}
This is a custom integration!
If you have any issues with this you need to open an issue here:
{ISSUE_URL}
-------------------------------------------------------------------
"""
