from dataclasses import dataclass
from typing import Any
from typing import Callable

from homeassistant.core import HomeAssistant

from ..common.register_type import RegisterType
from .inverter_model_spec import InverterModelSpec
from .inverter_model_spec import ModbusAddressSpecBase


@dataclass(frozen=True)
class ModbusRemoteControlAddressConfig:
    """Defines the set of registers used for remote control"""

    remote_enable_address: int
    timeout_set_address: int
    active_power_address: int

    @property
    def addresses(self) -> list[int]:
        return [self.remote_enable_address, self.timeout_set_address, self.active_power_address]


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

    def get_remote_enable_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe the remote enable address"""

        return self._get_address(lambda x: x.remote_enable_address)

    def get_timeout_set_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe the timeout set address"""

        return self._get_address(lambda x: x.timeout_set_address)

    def get_active_power_address(self) -> InverterModelSpec:
        """Gets a InverterModelSpec instance to describe the active power address"""

        return self._get_address(lambda x: x.active_power_address)

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
