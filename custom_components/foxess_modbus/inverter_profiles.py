"""Defines the different inverter models and connection types"""

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from .common.entity_controller import EntityController
from .common.types import ConnectionType
from .common.types import Inv
from .common.types import InverterModel
from .common.types import RegisterType
from .const import AC1
from .const import AC3
from .const import AIO_H1
from .const import AIO_H3
from .const import H3
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import KH
from .const import KUARA_H3
from .const import SK_HWR
from .const import SOLAVITA_SP
from .const import STAR_H3
from .entities.charge_period_descriptions import CHARGE_PERIODS
from .entities.entity_descriptions import ENTITIES
from .entities.modbus_charge_period_config import ModbusChargePeriodInfo
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig
from .entities.remote_control_description import REMOTE_CONTROL_DESCRIPTION

_LOGGER = logging.getLogger(__package__)


class SpecialRegisterConfig:
    def __init__(
        self,
        *,
        invalid_register_ranges: list[tuple[int, int]] | None = None,
        individual_read_register_ranges: list[tuple[int, int]] | None = None,
    ) -> None:
        if invalid_register_ranges is None:
            invalid_register_ranges = []
        self.invalid_register_ranges = invalid_register_ranges

        if individual_read_register_ranges is None:
            individual_read_register_ranges = []
        self.individual_read_register_ranges = individual_read_register_ranges


H1_AC1_REGISTERS = SpecialRegisterConfig(invalid_register_ranges=[(11096, 39999)])
# See https://github.com/nathanmarlor/foxess_modbus/discussions/503
H3_REGISTERS = SpecialRegisterConfig(
    invalid_register_ranges=[(41001, 41006), (41012, 41013), (41015, 41015)],
    individual_read_register_ranges=[(41000, 41999)],
)
# See https://github.com/nathanmarlor/foxess_modbus/pull/512
KH_REGISTERS = SpecialRegisterConfig(
    invalid_register_ranges=[(41001, 41006), (41012, 41012), (41019, 43999)],
    individual_read_register_ranges=[(41000, 41999)],
)


class InverterModelConnectionTypeProfile:
    """Describes the capabilities of an inverter when connected to over a particular interface"""

    def __init__(
        self,
        inverter_model_profile: "InverterModelProfile",
        inv: Inv,
        connection_type: ConnectionType,
        register_type: RegisterType,
        special_registers: SpecialRegisterConfig,
    ) -> None:
        self.inverter_model_profile = inverter_model_profile
        self.connection_type = connection_type
        self.register_type = register_type
        self.special_registers = special_registers

    def overlaps_invalid_range(self, start_address: int, end_address: int) -> bool:
        """Determines whether the given inclusive address range overlaps any invalid address ranges"""
        return any(
            r[0] <= end_address and start_address <= r[1] for r in self.special_registers.invalid_register_ranges
        )

    def is_individual_read(self, address: int) -> bool:
        return any(r[0] <= address <= r[1] for r in self.special_registers.individual_read_register_ranges)

    def create_entities(
        self,
        entity_type: type[Entity],
        hass: HomeAssistant,
        controller: EntityController,
        entry: ConfigEntry,
        inverter_details: dict[str, Any],
    ) -> list[Entity]:
        """Create all of the entities of the given type which support this inverter/connection combination"""

        result = []

        for entity_factory in ENTITIES:
            if entity_factory.entity_type == entity_type:
                entity = entity_factory.create_entity_if_supported(
                    hass,
                    controller,
                    self.inverter_model_profile.model,
                    self.register_type,
                    entry,
                    inverter_details,
                )
                if entity is not None:
                    result.append(entity)

        return result

    def create_charge_periods(
        self, hass: HomeAssistant, inverter_details: dict[str, Any]
    ) -> list[ModbusChargePeriodInfo]:
        """Create all of the charge periods which support this inverter/connection combination"""

        result = []

        for charge_period_factory in CHARGE_PERIODS:
            charge_period = charge_period_factory.create_charge_period_config_if_supported(
                hass, self.inverter_model_profile.model, self.register_type, inverter_details
            )
            if charge_period is not None:
                result.append(charge_period)

        return result

    def create_remote_control_config(
        self, hass: HomeAssistant, inverter_detials: dict[str, Any]
    ) -> ModbusRemoteControlAddressConfig | None:
        return REMOTE_CONTROL_DESCRIPTION.create_if_supported(
            hass, self.inverter_model_profile.model, self.register_type, inverter_detials
        )


class InverterModelProfile:
    """Describes the capabilities of an inverter model"""

    def __init__(self, model: InverterModel, model_pattern: str, capacity_map: dict[str, int] | None = None) -> None:
        self.model = model
        self.model_pattern = model_pattern
        self._capacity_map = capacity_map
        self.connection_types: dict[ConnectionType, InverterModelConnectionTypeProfile] = {}

    def add_connection_type(
        self,
        inv: Inv,
        connection_type: ConnectionType,
        register_type: RegisterType,
        special_registers: SpecialRegisterConfig | None = None,
    ) -> "InverterModelProfile":
        """Add the given connection type to the profile"""

        assert connection_type not in self.connection_types
        if special_registers is None:
            special_registers = SpecialRegisterConfig()

        self.connection_types[connection_type] = InverterModelConnectionTypeProfile(
            self,
            inv,
            connection_type,
            register_type,
            special_registers,
        )
        return self

    def inverter_capacity(self, inverter_model: str) -> int:
        match = re.match(self.model_pattern, inverter_model)
        if match is None:
            raise Exception(f"Unable to determine capacity of inverter '{inverter_model}'")

        # Some inverters don't put their power into their model, so we have to have a separate map
        if self._capacity_map is not None:
            capacity = self._capacity_map.get(match.group(1))
            if capacity is None:
                raise Exception(f"Unknown capacity '{match.group(1)}' for inverter model '{inverter_model}'")
            return capacity

        try:
            capacity = int(float(match.group(1)) * 1000)
            return capacity
        except ValueError as ex:
            raise Exception(f"Unable parse capacity '{match.group(1)}' of inverter '{inverter_model}'") from ex


INVERTER_PROFILES = {
    x.model: x
    for x in [
        # Can be both e.g. H1-5.0 and H1-5.0-E
        InverterModelProfile(InverterModel.H1, r"^H1-([\d\.]+)")
        .add_connection_type(
            Inv.H1_G1,
            ConnectionType.AUX,
            RegisterType.INPUT,
            special_registers=H1_AC1_REGISTERS,
        )
        .add_connection_type(
            Inv.H1_LAN,
            ConnectionType.LAN,
            RegisterType.HOLDING,
        ),
        InverterModelProfile(AC1, r"^AC1-([\d\.]+)")
        .add_connection_type(
            ConnectionType.AUX,
            RegisterType.INPUT,
            special_registers=H1_AC1_REGISTERS,
        )
        .add_connection_type(
            ConnectionType.LAN,
            RegisterType.HOLDING,
        ),
        InverterModelProfile(AIO_H1, r"^AIO-H1-([\d\.]+)")
        .add_connection_type(
            ConnectionType.AUX,
            RegisterType.INPUT,
            special_registers=H1_AC1_REGISTERS,
        )
        .add_connection_type(
            ConnectionType.LAN,
            RegisterType.HOLDING,
        ),
        # The KH doesn't have a LAN port. It supports both input and holding over RS485
        # Some models start with KH-, but some are just e.g. KH10.5
        InverterModelProfile(KH, r"^KH([\d\.]+)").add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=KH_REGISTERS,
        ),
        # The H3 seems to use holding registers for everything
        InverterModelProfile(H3, r"^H3-([\d\.]+)")
        .add_connection_type(
            ConnectionType.LAN,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        )
        .add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
        InverterModelProfile(AC3, r"^AC3-([\d\.]+)")
        .add_connection_type(
            ConnectionType.LAN,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        )
        .add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
        InverterModelProfile(AIO_H3, r"^AIO-H3-([\d\.]+)")
        .add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        )
        .add_connection_type(
            ConnectionType.LAN,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
        # Kuara 6.0-3-H: H3-6.0-E
        # Kuara 8.0-3-H: H3-8.0-E
        # Kuara 10.0-3-H: H3-10.0-E
        # Kuara 12.0-3-H: H3-12.0-E
        # I haven't seen any indication that these support a direct LAN connection
        InverterModelProfile(KUARA_H3, r"^Kuara ([\d\.]+)-3-H$").add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
        # Sonnenkraft:
        # SK-HWR-8: H3-8.0-E
        # (presumably there are other sizes also)
        InverterModelProfile(SK_HWR, r"^SK-HWR-([\d\.]+)").add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
        # STAR
        # STAR-H3-12.0-E: H3-12.0-E
        # (presumably there are other sizes also)
        InverterModelProfile(STAR_H3, r"^STAR-H3-([\d\.]+)").add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
        # Solavita SP
        # These have the form 'SP R8KH3', 'R10KH3', 'R12KH3', but the number doesn't map to a power
        # https://www.svcenergy.com/product/three-phase-solar-power-hybrid-inverter-sih
        InverterModelProfile(
            SOLAVITA_SP,
            r"^SP R(\d+)KH3",
            capacity_map={
                "8": 10400,
                "10": 13000,
                "12": 15600,
            },
        ).add_connection_type(
            ConnectionType.AUX,
            RegisterType.HOLDING,
            special_registers=H3_REGISTERS,
        ),
    ]
}


def create_entities(
    entity_type: type[Entity],
    hass: HomeAssistant,
    controller: EntityController,
    entry: ConfigEntry,
    inverter_config: dict[str, Any],
) -> list[Entity]:
    """Create all of the entities which support the inverter described by the given configuration object"""

    return inverter_connection_type_profile_from_config(inverter_config).create_entities(
        entity_type, hass, controller, entry, inverter_config
    )


def inverter_connection_type_profile_from_config(inverter_config: dict[str, Any]) -> InverterModelConnectionTypeProfile:
    """Fetches a InverterConnectionTypeProfile for a given configuration object"""

    return INVERTER_PROFILES[inverter_config[INVERTER_BASE]].connection_types[inverter_config[INVERTER_CONN]]
