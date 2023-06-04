"""Time period config"""
import logging
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

from ..common.register_type import RegisterType
from .inverter_model_spec import InverterModelSpec
from .inverter_model_spec import ModbusAddressSpecBase
from .modbus_binary_sensor import ModbusBinarySensorDescription
from .modbus_charge_period_sensors import ModbusChargePeriodStartEndSensorDescription
from .modbus_charge_period_sensors import ModbusEnableForceChargeSensorDescription
from .validation import Time

_LOGGER = logging.getLogger(__name__)

# hass type hints are messed up, and mypy doesn't see inherited dataclass properties on the EntityDescriptions
# mypy: disable-error-code="call-arg"


@dataclass
class ModbusChargePeriodConfig:
    """Defines the set of registers which are used to define a charge period"""

    period_start_address: int
    period_end_address: int
    enable_charge_from_grid_address: int


class ChargePeriodAddressSpec:
    """
    Specifies the addresses involved in a charge period, for a given list of inverter models

    For example:
    addrseses=[
        ChargePeriodAddressSpec([H1, AC1], aux=ModbusChargePeriodConfig(period_start_address=...))
        ChargePeriodAddressSpec([H3], aux=ModbusChargePeriodConfig(period_start_address=...))
    ]
    """

    def __init__(
        self,
        models: list[str],
        input: ModbusChargePeriodConfig | None = None,  # noqa: A002
        holding: ModbusChargePeriodConfig | None = None,
    ) -> None:
        self.models = models
        self.register_types: dict[RegisterType, ModbusChargePeriodConfig] = {}
        if input is not None:
            self.register_types[RegisterType.INPUT] = input
        if holding is not None:
            self.register_types[RegisterType.HOLDING] = holding

    def get_start_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe the start address"""

        addresses = {}
        for register_type, period_addresses in self.register_types.items():
            addresses[register_type] = [period_addresses.period_start_address]
        return ModbusAddressSpecBase(self.models, addresses)

    def get_end_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe the end address"""

        addresses = {}
        for register_type, period_addresses in self.register_types.items():
            addresses[register_type] = [period_addresses.period_end_address]
        return ModbusAddressSpecBase(self.models, addresses)

    def get_enable_charge_from_grid_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe 'enable charge from grid' address"""

        addresses = {}
        for register_type, period_addresses in self.register_types.items():
            addresses[register_type] = [period_addresses.enable_charge_from_grid_address]
        return ModbusAddressSpecBase(self.models, addresses)


@dataclass
class ModbusChargePeriodFactory:
    """
    Factory which creates various things required to define and specify a charge period

    This is used to create the entities which visualise the various bits of charge period start
    (start time, etc), and also the ModbusChargePeriodConfig which is used internally when
    interacting with charge periods
    """

    def __init__(
        self,
        addresses: list[ChargePeriodAddressSpec],
        period_start_key: str,
        period_start_name: str,
        period_end_key: str,
        period_end_name: str,
        enable_force_charge_key: str,
        enable_force_charge_name: str,
        enable_charge_from_grid_key: str,
        enable_charge_from_grid_name: str,
    ) -> None:
        self.address_specs = addresses

        period_start_address = [x.get_start_address() for x in addresses]
        period_end_address = [x.get_end_address() for x in addresses]
        enable_charge_from_grid_address = [x.get_enable_charge_from_grid_address() for x in addresses]

        self.period_start = ModbusChargePeriodStartEndSensorDescription(
            key=period_start_key,
            name=period_start_name,
            address=period_start_address,
            other_address=period_end_address,
            icon="mdi:timer-play-outline",
            validate=[Time()],
        )
        self.period_end = ModbusChargePeriodStartEndSensorDescription(
            key=period_end_key,
            name=period_end_name,
            address=period_end_address,
            other_address=period_start_address,
            icon="mdi:timer-stop-outline",
            validate=[Time()],
        )
        self.enable_force_charge = ModbusEnableForceChargeSensorDescription(
            key=enable_force_charge_key,
            name=enable_force_charge_name,
            period_start_address=period_start_address,
            period_end_address=period_end_address,
            validate=[Time()],
        )
        self.enable_charge_from_grid = ModbusBinarySensorDescription(
            key=enable_charge_from_grid_key,
            name=enable_charge_from_grid_name,
            address=enable_charge_from_grid_address,
            # The 'Update Charge Period' service only accepts devices with this device_class,
            # so ensure that only inverters which support this provide a sensor with this device_class
            device_class=BinarySensorDeviceClass.POWER,
            # mdi:power-plug-battery is perfect, but not yet in HA
            icon_func=lambda x: "mdi:battery-charging" if x else "mdi:battery",
        )

        self.entity_descriptions = [
            self.period_start,
            self.period_end,
            self.enable_force_charge,
            self.enable_charge_from_grid,
        ]

    def create_charge_period_config_if_supported(
        self, inverter_model: str, register_type: RegisterType
    ) -> ModbusChargePeriodConfig | None:
        """
        If the inverter model / connection type supports a charge period, fetches a ModbusChargePeriodConfig containing
        the register addresses involved. If not supported, returns None.
        """

        result: ModbusChargePeriodConfig | None = None
        for address_spec in self.address_specs:
            if inverter_model in address_spec.models:
                config = address_spec.register_types.get(register_type)
                if config is not None:
                    assert (
                        result is None
                    ), f"{self}: multiple charge periods defined for ({inverter_model}, {register_type})"
                    result = config
        return result
