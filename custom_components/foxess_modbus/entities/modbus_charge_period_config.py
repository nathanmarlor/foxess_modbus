"""Time period config"""
import logging

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from .modbus_binary_sensor import ModbusBinarySensorDescription
from .modbus_charge_period_sensors import ModbusChargePeriodStartEndSensorDescription
from .modbus_charge_period_sensors import ModbusEnableForceChargeSensorDescription

_LOGGER = logging.getLogger(__name__)


class ModbusChargePeriodConfig:
    """Holds information on the various sensors required to represent a time period"""

    def __init__(
        self,
        period_start_key: str,
        period_start_name: str,
        period_start_address: int,
        period_end_key: str,
        period_end_name: str,
        period_end_address: int,
        enable_force_charge_key: str,
        enable_force_charge_name: str,
        enable_charge_from_grid_key: str,
        enable_charge_from_grid_name: str,
        enable_charge_from_grid_address: int,
    ) -> None:
        self.period_start = ModbusChargePeriodStartEndSensorDescription(
            key=period_start_key,
            name=period_start_name,
            address=period_start_address,
            other_address=period_end_address,
        )
        self.period_end = ModbusChargePeriodStartEndSensorDescription(
            key=period_end_key,
            name=period_end_name,
            address=period_end_address,
            other_address=period_start_address,
        )
        self.enable_force_charge = ModbusEnableForceChargeSensorDescription(
            key=enable_force_charge_key,
            name=enable_force_charge_name,
            period_start_address=period_start_address,
            period_end_address=period_end_address,
        )
        self.enable_charge_from_grid = ModbusBinarySensorDescription(
            key=enable_charge_from_grid_key,
            name=enable_charge_from_grid_name,
            address=enable_charge_from_grid_address,
            device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        )

        self.entity_descriptions = [
            self.period_start,
            self.period_end,
            self.enable_force_charge,
            self.enable_charge_from_grid,
        ]
