"""Inverter sensor"""
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass

from ..const import MODBUS
from .modbus_sensor import ModbusSensor
from .sensor_desc import SensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SENSORS: dict[str, SensorDescription] = {
    "pv1-voltage": SensorDescription(
        key="pv1-voltage",
        address=31000,
        name="PV1 Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
    ),
    "pv1-current": SensorDescription(
        key="pv1-current",
        address=31001,
        name="PV1 Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
    ),
    "pv1-power": SensorDescription(
        key="pv1-power",
        address=31002,
        name="PV1 Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
    ),
    "pv2-voltage": SensorDescription(
        key="pv2-voltage",
        address=31003,
        name="PV2 Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
    ),
    "pv2-current": SensorDescription(
        key="pv2-current",
        address=31004,
        name="PV2 Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
    ),
    "pv2-power": SensorDescription(
        key="pv2-power",
        address=31005,
        name="PV2 Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
    ),
    "battery-soc": SensorDescription(
        key="battery-soc",
        address=31024,
        name="Battery SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
    ),
    "battery-discharge": SensorDescription(
        key="battery-discharge",
        address=31022,
        name="Battery Discharge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
    ),
    "battery-charge": SensorDescription(
        key="battery-charge",
        address=31022,
        name="Battery Charge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
    ),
    "feed-in": SensorDescription(
        key="feed-in",
        address=31014,
        name="Feed In",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
    ),
    "grid-consumption": SensorDescription(
        key="grid-consumption",
        address=31014,
        name="Grid Consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
    ),
    "grid-voltage": SensorDescription(
        key="grid-voltage",
        address=31006,
        name="Grid Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
    ),
    "grid-current": SensorDescription(
        key="grid-current",
        address=31007,
        name="Grid Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
    ),
    "grid-frequency": SensorDescription(
        key="grid-frequency",
        address=31009,
        name="Grid Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
    ),
    "battery-temp": SensorDescription(
        key="battery-temp",
        address=31023,
        name="Battery Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
    ),
    "inv-temp": SensorDescription(
        key="inv-temp",
        address=31019,
        name="Inverter Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
    ),
    "amb-temp": SensorDescription(
        key="amb-temp",
        address=31018,
        name="Ambient Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
    ),
    "load-power": SensorDescription(
        key="load-power",
        address=31016,
        name="Load Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
    ),
    "grid-ct": SensorDescription(
        key="grid-ct",
        address=31014,
        name="Grid CT",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
    ),
    "bat-voltage": SensorDescription(
        key="bat-voltage",
        address=31020,
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
    ),
    "bat-current": SensorDescription(
        key="bat-current",
        address=31021,
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
    ),
}


def sensors(controllers, entry) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = ModbusSensor(controllers[MODBUS], SENSORS[sensor], entry)
        entities.append(sen)

    return entities
