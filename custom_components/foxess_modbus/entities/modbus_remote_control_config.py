from dataclasses import dataclass
from typing import Any
from typing import Callable

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number import NumberMode
from homeassistant.core import HomeAssistant

from ..common.entity_controller import EntityRemoteControlManager
from ..common.register_type import RegisterType
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import InverterModelSpec
from .inverter_model_spec import ModbusAddressSpecBase
from .modbus_remote_control_number import ModbusRemoteControlNumberDescription
from .modbus_remote_control_select import ModbusRemoteControlSelectDescription


@dataclass(frozen=True)
class ModbusRemoteControlAddressConfig:
    """Defines the set of registers used for remote control"""

    remote_enable: int
    """Remote Enable, turns remote control off/on"""
    timeout_set: int
    """Remote Timeout_Set, sets the watchdog reload value"""
    active_power: int
    """Remote control-Active power command, sets the output power (+ve) or input power (-ve) of the inverter"""
    work_mode: int | None
    """Work mode control"""

    battery_soc: int
    """Current battery SoC"""
    max_soc: int | None
    """Configured Max SoC"""
    inverter_power: list[int]
    """Current output power of the inverter (+ve) or input power (-ve)"""
    ac_power_limit_down: int
    """
    Pwr_limit Ac_P_Dn, maximum active power provided by the inverter. NOTE this is negative!

    It seems that Pwr_lmit_Ac_P_Up takes the export limit into account, whereas this doesn't.

    TODO: Read only once, when we have this ability"""
    pv_power_limit: int
    """Pwr_limit PV, related to the spare input PV capacity"""
    pv_voltages: list[int]
    """Array of pvx_voltage addresses for PV strings"""
    pv_powers: list[int]
    """Array of the pvx_power addresses for PV strings"""


class RemoteControlAddressSpec:
    """
    Specifies the addresses involved in remote control, for a given list of inverter models

    For example:
    addresses=[
        RemoteControlAddressSpec([H1, AC1], input=ModbusRemoteControlAddressConfig(...))
        RemoteControlAddressSpec([H3], holding=ModbusRemoteControlAddressConfig(period_start_address=...))
    ]
    """

    def __init__(
        self,
        models: list[str],
        input: ModbusRemoteControlAddressConfig | None = None,  # noqa: A002
        holding: ModbusRemoteControlAddressConfig | None = None,
    ) -> None:
        self.models = models
        self.register_types: dict[RegisterType, ModbusRemoteControlAddressConfig] = {}
        if input is not None:
            self.register_types[RegisterType.INPUT] = input
        if holding is not None:
            self.register_types[RegisterType.HOLDING] = holding

    def get_models_without_work_mode(self) -> EntitySpec:
        """Gets a InverterModelSpec instance to describe the Work Mode address"""
        return EntitySpec(self.models, [k for k, v in self.register_types.items() if v.work_mode is None])

    def get_ac_power_limit_down_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe Ac power limit down address"""

        return self._get_address(lambda x: x.ac_power_limit_down)

    def _get_address(self, accessor: Callable[[ModbusRemoteControlAddressConfig], int]) -> InverterModelSpec:
        addresses = {}
        for register_type, address_config in self.register_types.items():
            addresses[register_type] = [accessor(address_config)]
        return ModbusAddressSpecBase(self.models, addresses)


@dataclass
class ModbusRemoteControlFactory:
    """
    Factory which creates various things required to define and specify the remote control functionality

    This is used to create the entities which visualise the various bits of the remote control
    (enable, etc), and also the ModbusRemoteControlAddressConfig which is used internally when
    interacting with the remote control
    """

    def __init__(self, addresses: list[RemoteControlAddressSpec]) -> None:
        self.address_specs = addresses

        def _set_charge_power(manager: EntityRemoteControlManager, value: int) -> None:
            manager.charge_power = -value

        charge_power = ModbusRemoteControlNumberDescription(  # type: ignore
            key="force_charge_power",
            name="Force Charge Power",
            max_value_address=[x.get_ac_power_limit_down_address() for x in addresses],
            mode=NumberMode.BOX,
            device_class=NumberDeviceClass.POWER,
            native_min_value=0.0,
            # Max value is read from the inverter
            native_step=0.001,
            native_unit_of_measurement="kW",
            # The register is negative
            scale=-0.001,
            signed=True,
            value_setter=_set_charge_power,
        )

        def _set_discharge_power(manager: EntityRemoteControlManager, value: int) -> None:
            manager.discharge_power = -value

        # hass type hints are messed up, and mypy doesn't see inherited dataclass properties on the EntityDescriptions
        discharge_power = ModbusRemoteControlNumberDescription(  # type: ignore
            key="force_discharge_power",
            name="Force Discharge Power",
            max_value_address=[x.get_ac_power_limit_down_address() for x in addresses],
            mode=NumberMode.BOX,
            device_class=NumberDeviceClass.POWER,
            native_min_value=0.0,
            # Max value is read from the inverter
            native_step=0.001,
            native_unit_of_measurement="kW",
            scale=-0.001,
            signed=True,
            value_setter=_set_discharge_power,
        )

        # Models without a work_mode address get one of these
        remote_control_select = ModbusRemoteControlSelectDescription(  # type: ignore
            key="force_charge_mode",
            name="Force Charge Mode",
            models=[x.get_models_without_work_mode() for x in self.address_specs],
        )

        self.entity_descriptions: list[EntityFactory] = [charge_power, discharge_power, remote_control_select]

    def create_if_supported(
        self, _hass: HomeAssistant, inverter_model: str, register_type: RegisterType, _inv_details: dict[str, Any]
    ) -> ModbusRemoteControlAddressConfig | None:
        """
        If the inverter model / connection type supports a charge period, fetches a ModbusChargePeriodAddressConfig
        containing the register addresses involved. If not supported, returns None.
        """

        result: ModbusRemoteControlAddressConfig | None = None
        for address_spec in self.address_specs:
            if inverter_model in address_spec.models:
                address_config = address_spec.register_types.get(register_type)
                if address_config is not None:
                    assert (
                        result is None
                    ), f"{self}: multiple remote control addresses defined for ({inverter_model}, {register_type})"

                    result = address_config
        return result
