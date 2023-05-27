"""
Sensor which shows Unknown if the battery / BMS is offline, as indicated by the BatStatus / BMS connect state
register
"""
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from .inverter_model_spec import ModbusAddressSpec
from .modbus_sensor import ModbusSensor
from .modbus_sensor import ModbusSensorDescription


@dataclass(kw_only=True)
class ModbusBatterySensorDescription(ModbusSensorDescription):
    """Description for ModbusBatterySensor"""

    bms_connect_state_address: list[ModbusAddressSpec]

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        _entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        bms_connect_address = (
            self._address_for_inverter_model(self.bms_connect_state_address, inverter_model, register_type)
            if self.bms_connect_state_address is not None
            else None
        )
        return (
            ModbusBatterySensor(
                controller,
                self,
                addresses,
                bms_connect_address,
                inv_details,
            )
            if addresses is not None
            else None
        )


class ModbusBatterySensor(ModbusSensor):
    """A sensor which returns Unknown if the battery is not connected"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSensorDescription,
        # Array of registers which this value is split over, from lower-order bits to higher-order bits
        addresses: list[int],
        bms_connect_state_address: int | None,
        inv_details: dict[str, Any],
    ) -> None:
        super().__init__(
            controller=controller,
            entity_description=entity_description,
            addresses=addresses,
            round_to=None,
            inv_details=inv_details,
        )

        self._interested_addresses = addresses.copy()
        if bms_connect_state_address is not None:
            self._interested_addresses.append(bms_connect_state_address)

        self._bms_connect_state_address = bms_connect_state_address

    @property
    def native_value(self) -> Any:
        if self._bms_connect_state_address is not None:
            bms_connect_state = self._controller.read(self._bms_connect_state_address)
            # 0: Initial state, 1: OK, 2: NG
            if bms_connect_state != 1:
                return None

        return super().native_value

    @property
    def addresses(self) -> list[int]:
        return self._interested_addresses
