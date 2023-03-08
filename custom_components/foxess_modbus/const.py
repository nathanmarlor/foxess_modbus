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
PLATFORMS = [SENSOR]
ATTR_ENTRY_TYPE = "entry_type"

# Fox Options
MODBUS_HOST = "modbus_host"
MODBUS_PORT = "modbus_port"

INVERTER_TYPE = "modbus_type"
INVERTER_CONN = "modbus_conn"

# Inverter Types
H1 = "H1"
H3 = "H3"
LAN = "LAN"
AUX = "AUX"

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
