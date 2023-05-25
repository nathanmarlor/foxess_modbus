"""Defines the different inverter models and connection types"""
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from .common.entity_controller import EntityController
from .common.register_type import RegisterType
from .const import AC1
from .const import AIO_H1
from .const import AIO_H3
from .const import AUX
from .const import H1
from .const import H3
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import KH
from .const import LAN
from .entities import invalid_ranges
from .entities.charge_periods import CHARGE_PERIODS
from .entities.entity_descriptions import ENTITIES
from .entities.modbus_charge_period_config import ModbusChargePeriodConfig

_LOGGER = logging.getLogger(__package__)


class InverterModelConnectionTypeProfile:
    """Describes the capabilities of an inverter when connected to over a particular interface"""

    def __init__(
        self,
        inverter_model: str,
        connection_type: str,
        register_type: RegisterType,
        invalid_register_ranges: list[tuple[int, int]],
    ) -> None:
        self.inverter_model = inverter_model
        self.connection_type = connection_type
        self.register_type = register_type
        self.invalid_register_ranges = invalid_register_ranges

    def overlaps_invalid_range(self, start_address: int, end_address: int) -> bool:
        """Determines whether the given inclusive address range overlaps any invalid address ranges"""
        return any(r[0] <= end_address and start_address <= r[1] for r in self.invalid_register_ranges)

    def create_entities(
        self,
        entity_type: type[Entity],
        controller: EntityController,
        entry: ConfigEntry,
        inverter_details: dict[str, Any],
    ) -> list[Entity]:
        """Create all of the entities of the given type which support this inverter/connection combination"""

        result = []

        for entity_factory in ENTITIES:
            if entity_factory.entity_type == entity_type:
                entity = entity_factory.create_entity_if_supported(
                    controller,
                    self.inverter_model,
                    self.register_type,
                    entry,
                    inverter_details,
                )
                if entity is not None:
                    result.append(entity)

        return result

    def create_charge_periods(self) -> list[ModbusChargePeriodConfig]:
        """Create all of the charge periods which support this inverter/connection combination"""

        result = []

        for charge_period_factory in CHARGE_PERIODS:
            charge_period = charge_period_factory.create_charge_period_config_if_supported(
                self.inverter_model, self.register_type
            )
            if charge_period is not None:
                result.append(charge_period)

        return result


class InverterModelProfile:
    """Describes the capabilities of an inverter model"""

    def __init__(self, model: str) -> None:
        self.model = model
        self.connection_types: dict[str, InverterModelConnectionTypeProfile] = {}

    def add_connection_type(
        self,
        connection_type: str,
        register_type: RegisterType,
        invalid_register_ranges: list[tuple[int, int]] | None = None,
    ) -> "InverterModelProfile":
        """Add the given connection type to the profile"""

        assert connection_type not in self.connection_types
        if invalid_register_ranges is None:
            invalid_register_ranges = []

        self.connection_types[connection_type] = InverterModelConnectionTypeProfile(
            self.model,
            connection_type,
            register_type,
            invalid_register_ranges,
        )
        return self


INVERTER_PROFILES = {
    x.model: x
    for x in [
        InverterModelProfile(H1)
        .add_connection_type(
            AUX,
            RegisterType.INPUT,
            invalid_register_ranges=invalid_ranges.H1_AC1,
        )
        .add_connection_type(
            LAN,
            RegisterType.HOLDING,
        ),
        InverterModelProfile(AC1)
        .add_connection_type(
            AUX,
            RegisterType.INPUT,
            invalid_register_ranges=invalid_ranges.H1_AC1,
        )
        .add_connection_type(
            LAN,
            RegisterType.HOLDING,
        ),
        InverterModelProfile(AIO_H1)
        .add_connection_type(
            AUX,
            RegisterType.INPUT,
            invalid_register_ranges=invalid_ranges.H1_AC1,
        )
        .add_connection_type(
            LAN,
            RegisterType.HOLDING,
        ),
        # The KH doesn't have a LAN port. It supports both input and holding over RS485
        InverterModelProfile(KH).add_connection_type(AUX, RegisterType.INPUT),
        # The H3 seems to use holding registers for everything
        InverterModelProfile(H3)
        .add_connection_type(
            LAN,
            RegisterType.HOLDING,
        )
        .add_connection_type(
            AUX,
            RegisterType.HOLDING,
        ),
        InverterModelProfile(AIO_H3)
        .add_connection_type(
            AUX,
            RegisterType.HOLDING,
        )
        .add_connection_type(
            LAN,
            RegisterType.HOLDING,
        ),
    ]
}


def create_entities(
    entity_type: type[Entity],
    controller: EntityController,
    entry: ConfigEntry,
    inverter_config: dict[str, Any],
) -> list[Entity]:
    """Create all of the entities which support the inverter described by the given configuration object"""

    return inverter_connection_type_profile_from_config(inverter_config).create_entities(
        entity_type, controller, entry, inverter_config
    )


def inverter_connection_type_profile_from_config(inverter_config: dict[str, Any]) -> InverterModelConnectionTypeProfile:
    """Fetches a InverterConnectionTypeProfile for a given configuration object"""

    return INVERTER_PROFILES[inverter_config[INVERTER_BASE]].connection_types[inverter_config[INVERTER_CONN]]
