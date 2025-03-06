"""Defines the different inverter models and connection types"""

import functools
import logging
import re
from dataclasses import dataclass
from typing import Any
from typing import ClassVar

from homeassistant.helpers.entity import Entity

from .common.entity_controller import EntityController
from .common.types import ConnectionType
from .common.types import Inv
from .common.types import InverterModel
from .common.types import RegisterType
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import INVERTER_VERSION
from .entities.charge_period_descriptions import CHARGE_PERIODS
from .entities.entity_descriptions import ENTITIES
from .entities.modbus_charge_period_config import ModbusChargePeriodInfo
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig
from .entities.remote_control_description import REMOTE_CONTROL_DESCRIPTION

_LOGGER = logging.getLogger(__package__)


@functools.total_ordering
class Version:
    def __init__(self, major: int, minor: int) -> None:
        self.major = major
        self.minor = minor

    @staticmethod
    def parse(version: str) -> "Version":
        match = re.fullmatch(r"(\d+)\.(\d+)", version)
        if match is None:
            raise ValueError(f"Version {version} is not a valid version")
        return Version(int(match[1]), int(match[2]))

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Version) and self.major == other.major and self.minor == other.minor

    def __hash__(self) -> int:
        return hash((self.major, self.minor))

    def __lt__(self, other: Any) -> bool:
        # None means "the latest", and so sorts higher than anything (except None)
        if other is None:
            return True
        if self.major != other.major:
            return self.major < other.major
        return self.minor < other.minor

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}"

    def __repr__(self) -> str:
        return f"Version({self.major}, {self.minor})"


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
    invalid_register_ranges=[(41001, 41006), (41012, 41012), (41019, 43999), (31055, 31999)],
    individual_read_register_ranges=[(41000, 41999)],
)
# See https://github.com/nathanmarlor/foxess_modbus/discussions/553
H1_G2_REGISTERS = SpecialRegisterConfig(
    individual_read_register_ranges=[(41000, 41999)],
)

# See https://github.com/nathanmarlor/foxess_modbus/discussions/792
#
# Additional information to the individual read:
# - 37609 allows only to read 28 instead of 92 registers.
# - 37632 allows only to read  5 instead of 69 registers.
#
# All the 410xx register are not specified within the document version V1.05.03.00
H3_SMART_REGISTERS = SpecialRegisterConfig(
    invalid_register_ranges=[(41001, 41006), (41012, 41013), (41015, 41015)],
    individual_read_register_ranges=[(37609, 37620), (37632, 37636)]
)

@dataclass(kw_only=True)
class CapacityParser:
    capacity_map: dict[str, int] | None
    fallback_to_kw: bool

    DEFAULT: ClassVar["CapacityParser"]
    H1: ClassVar["CapacityParser"]

    def parse(self, capacity_str: str, inverter_model: str) -> int:
        if self.capacity_map is not None:
            capacity = self.capacity_map.get(capacity_str)
            if capacity is not None:
                return capacity
            if not self.fallback_to_kw:
                raise Exception(f"Unknown capacity '{capacity_str}' for inverter model '{inverter_model}'")

        try:
            capacity = int(float(capacity_str) * 1000)
            return capacity
        except ValueError as ex:
            raise Exception(f"Unable parse capacity '{capacity_str}' of inverter '{inverter_model}'") from ex


CapacityParser.DEFAULT = CapacityParser(capacity_map=None, fallback_to_kw=True)
CapacityParser.H1 = CapacityParser(capacity_map={"3.7": 3680}, fallback_to_kw=True)


class InverterModelConnectionTypeProfile:
    """Describes the capabilities of an inverter when connected to over a particular interface"""

    def __init__(
        self,
        inverter_model_profile: "InverterModelProfile",
        connection_type: ConnectionType,
        register_type: RegisterType,
        versions: dict[Version | None, Inv],
        special_registers: SpecialRegisterConfig,
    ) -> None:
        self.inverter_model_profile = inverter_model_profile
        self.connection_type = connection_type
        self.register_type = register_type
        self.versions = versions
        self.special_registers = special_registers

        assert None in versions

    def _get_inv(self, controller: EntityController) -> Inv:
        version_from_config = controller.inverter_details.get(INVERTER_VERSION)
        # Remember that self._versions is a map of maximum supported manager version (or None to support the max
        # firmware version) -> Inv for that version
        if version_from_config is None:
            return self.versions[None]

        inverter_version = Version.parse(version_from_config)
        versions = sorted(self.versions.items(), reverse=True)
        matched_version = next((x for x in versions if x[0] <= inverter_version), versions[0])
        return matched_version[1]

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
        controller: EntityController,
    ) -> list[Entity]:
        """Create all of the entities of the given type which support this inverter/connection combination"""

        result = []

        for entity_factory in ENTITIES:
            if entity_factory.entity_type == entity_type:
                entity = entity_factory.create_entity_if_supported(
                    controller, self._get_inv(controller), self.register_type
                )
                if entity is not None:
                    result.append(entity)

        return result

    def create_charge_periods(self, controller: EntityController) -> list[ModbusChargePeriodInfo]:
        """Create all of the charge periods which support this inverter/connection combination"""

        result = []

        for charge_period_factory in CHARGE_PERIODS:
            charge_period = charge_period_factory.create_charge_period_config_if_supported(
                controller, self._get_inv(controller), self.register_type
            )
            if charge_period is not None:
                result.append(charge_period)

        return result

    def create_remote_control_config(self, controller: EntityController) -> ModbusRemoteControlAddressConfig | None:
        return REMOTE_CONTROL_DESCRIPTION.create_if_supported(controller, self._get_inv(controller), self.register_type)


class InverterModelProfile:
    """Describes the capabilities of an inverter model"""

    def __init__(self, model: InverterModel, model_pattern: str, capacity_parser: CapacityParser | None = None) -> None:
        self.model = model
        self.model_pattern = model_pattern
        self._capacity_parser = capacity_parser if capacity_parser is not None else CapacityParser.DEFAULT
        self.connection_types: dict[ConnectionType, InverterModelConnectionTypeProfile] = {}

    def add_connection_type(
        self,
        connection_type: ConnectionType,
        register_type: RegisterType,
        versions: dict[Version | None, Inv],  # Map of maximum supported manager versions -> Inv for that
        special_registers: SpecialRegisterConfig | None = None,
    ) -> "InverterModelProfile":
        """Add the given connection type to the profile"""

        assert connection_type not in self.connection_types
        if special_registers is None:
            special_registers = SpecialRegisterConfig()

        self.connection_types[connection_type] = InverterModelConnectionTypeProfile(
            self,
            connection_type,
            register_type,
            versions,
            special_registers,
        )
        return self

    def inverter_capacity(self, inverter_model: str) -> int:
        match = re.match(self.model_pattern, inverter_model)
        if match is None:
            raise Exception(f"Unable to determine capacity of inverter '{inverter_model}'")

        capacity = self._capacity_parser.parse(match.group(1), inverter_model)
        return capacity


_INVERTER_PROFILES_LIST = [
    # E.g. H1-5.0-E-G2. Has to appear before H1_G1.
    InverterModelProfile(
        InverterModel.H1_G2, r"^H1-([\d\.]+)-E-G2", capacity_parser=CapacityParser.H1
    ).add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 44): Inv.H1_G2_PRE144, None: Inv.H1_G2_144},
        special_registers=H1_G2_REGISTERS,
    ),
    # Can be both e.g. H1-5.0 and H1-5.0-E, but not H1-5.0-E-G2
    InverterModelProfile(InverterModel.H1_G1, r"^H1-([\d\.]+)", capacity_parser=CapacityParser.H1)
    .add_connection_type(
        ConnectionType.AUX,
        RegisterType.INPUT,
        versions={None: Inv.H1_G1},
        special_registers=H1_AC1_REGISTERS,
    )
    .add_connection_type(
        ConnectionType.LAN,
        RegisterType.HOLDING,
        versions={None: Inv.H1_LAN},
    ),
    # AC1-5.0-E-G2. Has to appear before AC1 G1 see https://github.com/nathanmarlor/foxess_modbus/discussions/715
    InverterModelProfile(
        InverterModel.AC1_G2, r"^AC1-([\d\.]+)-E-G2", capacity_parser=CapacityParser.H1
    ).add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 44): Inv.H1_G2_PRE144, None: Inv.H1_G2_144},
        special_registers=H1_G2_REGISTERS,
    ),
    InverterModelProfile(InverterModel.AC1, r"^AC1-([\d\.]+)", capacity_parser=CapacityParser.H1)
    .add_connection_type(
        ConnectionType.AUX,
        RegisterType.INPUT,
        versions={None: Inv.H1_G1},
        special_registers=H1_AC1_REGISTERS,
    )
    .add_connection_type(
        ConnectionType.LAN,
        RegisterType.HOLDING,
        versions={None: Inv.H1_LAN},
    ),
    InverterModelProfile(InverterModel.AIO_H1, r"^AIO-H1-([\d\.]+)", capacity_parser=CapacityParser.H1)
    .add_connection_type(
        ConnectionType.AUX,
        RegisterType.INPUT,
        versions={None: Inv.H1_G1},
        special_registers=H1_AC1_REGISTERS,
    )
    .add_connection_type(
        ConnectionType.LAN,
        RegisterType.HOLDING,
        versions={None: Inv.H1_LAN},
    ),
    InverterModelProfile(
        InverterModel.AIO_AC1, r"^AIO-AC1-([\d\.]+)", capacity_parser=CapacityParser.H1
    ).add_connection_type(
        ConnectionType.AUX,
        RegisterType.INPUT,
        versions={None: Inv.H1_G1},
        special_registers=H1_AC1_REGISTERS,
    ),
    # The KH doesn't have a LAN port. It supports both input and holding over RS485
    # Some models start with KH-, but some are just e.g. KH10.5
    InverterModelProfile(InverterModel.KH, r"^KH([\d\.]+)").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 19): Inv.KH_PRE119, Version(1, 33): Inv.KH_PRE133, None: Inv.KH_133},
        special_registers=KH_REGISTERS,
    ),
    # The H3 seems to use holding registers for everything
    InverterModelProfile(InverterModel.H3, r"^H3-([\d\.]+)")
    .add_connection_type(
        ConnectionType.LAN,
        RegisterType.HOLDING,
        versions={Version(1, 80): Inv.H3_PRE180, None: Inv.H3_180},
        special_registers=H3_REGISTERS,
    )
    .add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 80): Inv.H3_PRE180, None: Inv.H3_180},
        special_registers=H3_REGISTERS,
    ),
    InverterModelProfile(InverterModel.AC3, r"^AC3-([\d\.]+)")
    .add_connection_type(
        ConnectionType.LAN,
        RegisterType.HOLDING,
        versions={Version(1, 80): Inv.H3_PRE180, None: Inv.H3_180},
        special_registers=H3_REGISTERS,
    )
    .add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 80): Inv.H3_PRE180, None: Inv.H3_180},
        special_registers=H3_REGISTERS,
    ),
    InverterModelProfile(InverterModel.AIO_H3, r"^AIO-H3-([\d\.]+)")
    .add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 1): Inv.AIO_H3_PRE101, None: Inv.AIO_H3_101},
        special_registers=H3_REGISTERS,
    )
    .add_connection_type(
        ConnectionType.LAN,
        RegisterType.HOLDING,
        versions={Version(1, 1): Inv.AIO_H3_PRE101, None: Inv.AIO_H3_101},
        special_registers=H3_REGISTERS,
    ),
    # Kuara 6.0-3-H: H3-6.0-E
    # Kuara 8.0-3-H: H3-8.0-E
    # Kuara 10.0-3-H: H3-10.0-E
    # Kuara 12.0-3-H: H3-12.0-E
    # I haven't seen any indication that these support a direct LAN connection
    InverterModelProfile(InverterModel.KUARA_H3, r"^Kuara ([\d\.]+)-3-H$").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={None: Inv.KUARA_H3},
        special_registers=H3_REGISTERS,
    ),
    # Sonnenkraft:
    # SK-HWR-8: H3-8.0-E
    # (presumably there are other sizes also)
    InverterModelProfile(InverterModel.SK_HWR, r"^SK-HWR-([\d\.]+)").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={None: Inv.H3_PRE180},
        special_registers=H3_REGISTERS,
    ),
    # STAR
    # STAR-H3-12.0-E: H3-12.0-E
    # (presumably there are other sizes also)
    InverterModelProfile(InverterModel.STAR_H3, r"^STAR-H3-([\d\.]+)").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={None: Inv.H3_PRE180},
        special_registers=H3_REGISTERS,
    ),
    # Solavita SP
    # These have the form 'SP R8KH3', 'R10KH3', 'R12KH3', but the number doesn't map to a power
    # https://www.svcenergy.com/product/three-phase-solar-power-hybrid-inverter-sih
    InverterModelProfile(
        InverterModel.SOLAVITA_SP,
        r"^SP R(\d+)KH3",
        capacity_parser=CapacityParser(
            capacity_map={
                "8": 10400,
                "10": 13000,
                "12": 15600,
            },
            fallback_to_kw=False,
        ),
    ).add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={None: Inv.H3_PRE180},
        special_registers=H3_REGISTERS,
    ),
    # a-TroniX AX
    # These have the form 'AX 12.0kW-3ph' (the 3ph standing for '3 phase'). Presumably there are other powers, too
    # See https://github.com/nathanmarlor/foxess_modbus/discussions/783
    InverterModelProfile(InverterModel.ATRONIX_AX, r"^AX ([\d\.]+)kW-3ph").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={None: Inv.H3_PRE180},
        special_registers=H3_REGISTERS,
    ),
    # Enpal I-X range
    # These have the form 'I-X5', with powers 5, 6, 8, 9.9, 10, 12, 15kW
    # See https://github.com/nathanmarlor/foxess_modbus/issues/785
    InverterModelProfile(InverterModel.ENPAL_IX, r"^I-X([\d\.]+)").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={None: Inv.H3_SMART},
        special_registers=H3_SMART_REGISTERS,
    ),
    # E.g. H3-Pro-20.0
    InverterModelProfile(InverterModel.H3_PRO, r"^H3-Pro-([\d\.]+)").add_connection_type(
        ConnectionType.AUX,
        RegisterType.HOLDING,
        versions={Version(1, 22): Inv.H3_PRO_PRE122, None: Inv.H3_PRO_122},
        special_registers=H3_REGISTERS,
    ),
]

INVERTER_PROFILES = {x.model: x for x in _INVERTER_PROFILES_LIST}
assert len(INVERTER_PROFILES) == len(_INVERTER_PROFILES_LIST)


def create_entities(entity_type: type[Entity], controller: EntityController) -> list[Entity]:
    """Create all of the entities which support the inverter described by the given configuration object"""

    return inverter_connection_type_profile_from_config(controller.inverter_details).create_entities(
        entity_type, controller
    )


def inverter_connection_type_profile_from_config(inverter_config: dict[str, Any]) -> InverterModelConnectionTypeProfile:
    """Fetches a InverterConnectionTypeProfile for a given configuration object"""

    return INVERTER_PROFILES[inverter_config[INVERTER_BASE]].connection_types[inverter_config[INVERTER_CONN]]
