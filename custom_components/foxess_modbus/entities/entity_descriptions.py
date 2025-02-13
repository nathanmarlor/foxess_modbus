"""Holds all entity descriptions for all entities across all inverters"""

import itertools
from typing import Iterable

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTime

from ..common.types import Inv
from ..common.types import RegisterType
from .charge_period_descriptions import CHARGE_PERIODS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import ModbusAddressesSpec
from .inverter_model_spec import ModbusAddressSpec
from .modbus_battery_sensor import ModbusBatterySensorDescription
from .modbus_fault_sensor import H3_PRO_KH_133_FAULTS
from .modbus_fault_sensor import STANDARD_FAULTS
from .modbus_fault_sensor import FaultSet
from .modbus_fault_sensor import ModbusFaultSensorDescription
from .modbus_integration_sensor import ModbusIntegrationSensorDescription
from .modbus_inverter_state_sensor import H1_INVERTER_STATES
from .modbus_inverter_state_sensor import KH_INVERTER_STATES
from .modbus_inverter_state_sensor import ModbusG2InverterStateSensorDescription
from .modbus_inverter_state_sensor import ModbusInverterStateSensorDescription
from .modbus_lambda_sensor import ModbusLambdaSensorDescription
from .modbus_number import ModbusNumberDescription
from .modbus_sensor import ModbusSensorDescription
from .modbus_version_sensor import ModbusVersionSensorDescription
from .modbus_work_mode_select import ModbusWorkModeSelectDescription
from .remote_control_description import REMOTE_CONTROL_DESCRIPTION
from .validation import Min
from .validation import Range

# hass type hints are messed up, and mypy doesn't see inherited dataclass properties on the EntityDescriptions
# mypy: disable-error-code="call-arg"


BMS_CONNECT_STATE_ADDRESS = [
    ModbusAddressSpec(input=11058, models=Inv.H1_G1 | Inv.KH_PRE119),
    ModbusAddressSpec(holding=31029, models=Inv.H1_G1 | Inv.H1_LAN),
    ModbusAddressSpec(holding=31028, models=Inv.KH_PRE133 | Inv.H1_G2_SET),
    ModbusAddressSpec(holding=37002, models=Inv.KH_133),
    ModbusAddressSpec(holding=31042, models=Inv.H3_SET),
]


def _version_entities() -> Iterable[EntityFactory]:
    # Named so that they sort together
    def _master_version(address: list[ModbusAddressSpec], is_hex: bool) -> ModbusVersionSensorDescription:
        return ModbusVersionSensorDescription(
            key="master_version",
            address=address,
            is_hex=is_hex,
            name="Version: Master",
            icon="mdi:source-branch",
        )

    yield _master_version(
        address=[
            ModbusAddressSpec(input=10016, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=30016, models=Inv.H1_G1 | Inv.H1_LAN | Inv.H3_SET),
            ModbusAddressSpec(holding=36001, models=Inv.H3_PRO_PRE122),
        ],
        is_hex=False,
    )
    yield _master_version(
        address=[
            ModbusAddressSpec(holding=30016, models=Inv.KH_PRE133),
            ModbusAddressSpec(holding=36001, models=Inv.H1_G2_SET | Inv.KH_133 | Inv.H3_PRO_122),
        ],
        is_hex=True,
    )

    def _slave_version(address: list[ModbusAddressSpec], is_hex: bool) -> ModbusVersionSensorDescription:
        return ModbusVersionSensorDescription(
            key="slave_version",
            address=address,
            is_hex=is_hex,
            name="Version: Slave",
            icon="mdi:source-branch",
        )

    yield _slave_version(
        address=[
            ModbusAddressSpec(input=10017, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=30017, models=Inv.H1_G1 | Inv.H1_LAN | Inv.H3_SET),
            ModbusAddressSpec(holding=36002, models=Inv.H3_PRO_PRE122),
        ],
        is_hex=False,
    )
    yield _slave_version(
        address=[
            ModbusAddressSpec(holding=30017, models=Inv.KH_PRE133),
            ModbusAddressSpec(holding=36002, models=Inv.H1_G2_SET | Inv.KH_133 | Inv.H3_PRO_122),
        ],
        is_hex=True,
    )

    def _manager_version(address: list[ModbusAddressSpec], is_hex: bool) -> ModbusVersionSensorDescription:
        return ModbusVersionSensorDescription(
            key="manager_version",
            address=address,
            is_hex=is_hex,
            name="Version: Manager",
            icon="mdi:source-branch",
        )

    yield _manager_version(
        address=[
            ModbusAddressSpec(input=10018, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=30018, models=Inv.H1_G1 | Inv.H1_LAN),
        ],
        is_hex=False,
    )
    yield _manager_version(
        address=[
            ModbusAddressSpec(holding=30018, models=Inv.KH_PRE133 | Inv.H3_SET),
            ModbusAddressSpec(holding=36003, models=Inv.H1_G2_SET | Inv.H3_PRO_SET | Inv.KH_133),
        ],
        is_hex=True,
    )


def _pv_entities() -> Iterable[EntityFactory]:
    def _pv_voltage(key: str, addresses: list[ModbusAddressesSpec], name: str) -> EntityFactory:
        return ModbusSensorDescription(
            key=key,
            addresses=addresses,
            name=name,
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            scale=0.1,
            round_to=1,
            # This can go negative if no panels are attached
        )

    def _pv_current(key: str, addresses: list[ModbusAddressesSpec], name: str, scale: float) -> EntityFactory:
        return ModbusSensorDescription(
            key=key,
            addresses=addresses,
            name=name,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="A",
            scale=scale,
            round_to=1,
            # This can a small amount negative
            post_process=lambda x: max(x, 0),
            validate=[Range(0, 100)],
        )

    def _pv_power(key: str, addresses: list[ModbusAddressesSpec], name: str) -> EntityFactory:
        return ModbusSensorDescription(
            key=key,
            addresses=addresses,
            name=name,
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:solar-power-variant-outline",
            scale=0.001,
            round_to=0.01,
            # This can go negative if no panels are attached
            post_process=lambda x: max(x, 0),
        )

    def _pv_energy_total(key: str, models: list[EntitySpec], name: str, source_entity: str) -> EntityFactory:
        return ModbusIntegrationSensorDescription(
            key=key,
            models=models,
            device_class=SensorDeviceClass.ENERGY,
            native_unit_of_measurement="kWh",
            integration_method="left",
            name=name,
            source_entity=source_entity,
            unit_time=UnitOfTime.HOURS,
            icon="mdi:solar-power-variant-outline",
        )

    yield _pv_voltage(
        key="pv1_voltage",
        addresses=[
            ModbusAddressesSpec(input=[11000], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31000], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_PRE133 | Inv.H3_SET),
            ModbusAddressesSpec(holding=[39070], models=Inv.H1_G2_SET | Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV1 Voltage",
    )
    yield _pv_current(
        key="pv1_current",
        addresses=[
            ModbusAddressesSpec(input=[11001], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31001], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_PRE133 | Inv.H3_SET),
        ],
        name="PV1 Current",
        scale=0.1,
    )
    yield _pv_current(
        key="pv1_current",
        addresses=[
            ModbusAddressesSpec(holding=[39071], models=Inv.H1_G2_SET | Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV1 Current",
        scale=0.01,
    )
    yield _pv_power(
        key="pv1_power",
        addresses=[
            ModbusAddressesSpec(input=[11002], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31002], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_PRE133 | Inv.H3_SET),
            # This is techincally a 32-bit register on the G2, but it doesn't appear to actually write the upper word,
            # which means that negative values are represented incorrectly (as 0x0000FFFF etc)
            ModbusAddressesSpec(holding=[39280], models=Inv.H1_G2_SET),
            ModbusAddressesSpec(holding=[39280, 39279], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV1 Power",
    )
    yield _pv_energy_total(
        key="pv1_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.ALL,
            ),
        ],
        name="PV1 Power Total",
        source_entity="pv1_power",
    )
    yield _pv_voltage(
        key="pv2_voltage",
        addresses=[
            ModbusAddressesSpec(input=[11003], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31003], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_PRE133 | Inv.H3_SET),
            ModbusAddressesSpec(holding=[39072], models=Inv.H1_G2_SET | Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV2 Voltage",
    )
    yield _pv_current(
        key="pv2_current",
        addresses=[
            ModbusAddressesSpec(input=[11004], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31004], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_PRE133 | Inv.H3_SET),
        ],
        name="PV2 Current",
        scale=0.1,
    )
    yield _pv_current(
        key="pv2_current",
        addresses=[
            ModbusAddressesSpec(holding=[39073], models=Inv.H1_G2_SET | Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV2 Current",
        scale=0.01,
    )
    yield _pv_power(
        key="pv2_power",
        addresses=[
            ModbusAddressesSpec(input=[11005], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31005], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_PRE133 | Inv.H3_SET),
            # This is techincally a 32-bit register on the G2, but it doesn't appear to actually write the upper word,
            # which means that negative values are represented incorrectly (as 0x0000FFFF etc)
            ModbusAddressesSpec(holding=[39282], models=Inv.H1_G2_SET),
            ModbusAddressesSpec(holding=[39282, 39281], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV2 Power",
    )
    yield _pv_energy_total(
        key="pv2_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.ALL,
            ),
        ],
        name="PV2 Power Total",
        source_entity="pv2_power",
    )
    yield _pv_voltage(
        key="pv3_voltage",
        addresses=[
            ModbusAddressesSpec(input=[11096], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31039], models=Inv.KH_PRE133),
            ModbusAddressesSpec(holding=[39074], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV3 Voltage",
    )
    yield _pv_current(
        key="pv3_current",
        addresses=[
            ModbusAddressesSpec(input=[11097], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31040], models=Inv.KH_PRE133),
        ],
        name="PV3 Current",
        scale=0.1,
    )
    yield _pv_current(
        key="pv3_current",
        addresses=[
            ModbusAddressesSpec(holding=[39075], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV3 Current",
        scale=0.01,
    )
    yield _pv_power(
        key="pv3_power",
        addresses=[
            ModbusAddressesSpec(input=[11098], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31041], models=Inv.KH_PRE133),
            ModbusAddressesSpec(holding=[39284, 39283], models=Inv.KH_133),
            ModbusAddressesSpec(holding=[39284, 39283], models=Inv.H3_PRO_SET),
        ],
        name="PV3 Power",
    )
    yield _pv_energy_total(
        key="pv3_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.KH_SET | Inv.H3_PRO_SET,
            ),
        ],
        name="PV3 Power Total",
        source_entity="pv3_power",
    )
    yield _pv_voltage(
        key="pv4_voltage",
        addresses=[
            ModbusAddressesSpec(input=[11099], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31042], models=Inv.KH_PRE133),
            ModbusAddressesSpec(holding=[39076], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV4 Voltage",
    )
    yield _pv_current(
        key="pv4_current",
        addresses=[
            ModbusAddressesSpec(input=[11100], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31043], models=Inv.KH_PRE133),
        ],
        name="PV4 Current",
        scale=0.1,
    )
    yield _pv_current(
        key="pv4_current",
        addresses=[
            ModbusAddressesSpec(holding=[39077], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV4 Current",
        scale=0.01,
    )
    yield _pv_power(
        key="pv4_power",
        addresses=[
            ModbusAddressesSpec(input=[11101], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31044], models=Inv.KH_PRE133),
            ModbusAddressesSpec(holding=[39286, 39285], models=Inv.H3_PRO_SET | Inv.KH_133),
        ],
        name="PV4 Power",
    )
    yield _pv_energy_total(
        key="pv4_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.KH_SET | Inv.H3_PRO_SET,
            ),
        ],
        name="PV4 Power Total",
        source_entity="pv4_power",
    )
    yield _pv_voltage(
        key="pv5_voltage",
        addresses=[
            ModbusAddressesSpec(holding=[39078], models=Inv.H3_PRO_SET),
        ],
        name="PV5 Voltage",
    )
    yield _pv_current(
        key="pv5_current",
        addresses=[
            ModbusAddressesSpec(holding=[39079], models=Inv.H3_PRO_SET),
        ],
        name="PV5 Current",
        scale=0.01,
    )
    yield _pv_power(
        key="pv5_power",
        addresses=[
            ModbusAddressesSpec(holding=[39288, 39287], models=Inv.H3_PRO_SET),
        ],
        name="PV5 Power",
    )
    yield _pv_energy_total(
        key="pv5_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.H3_PRO_SET,
            ),
        ],
        name="PV5 Power Total",
        source_entity="pv5_power",
    )
    yield _pv_voltage(
        key="pv6_voltage",
        addresses=[
            ModbusAddressesSpec(holding=[39080], models=Inv.H3_PRO_SET),
        ],
        name="PV6 Voltage",
    )
    yield _pv_current(
        key="pv6_current",
        addresses=[
            ModbusAddressesSpec(holding=[39081], models=Inv.H3_PRO_SET),
        ],
        name="PV6 Current",
        scale=0.01,
    )
    yield _pv_power(
        key="pv6_power",
        addresses=[
            ModbusAddressesSpec(holding=[39290, 39289], models=Inv.H3_PRO_SET),
        ],
        name="PV6 Power",
    )
    yield _pv_energy_total(
        key="pv6_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.H3_PRO_SET,
            ),
        ],
        name="PV6 Power Total",
        source_entity="pv6_power",
    )
    yield ModbusLambdaSensorDescription(
        key="pv_power_now",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.ALL & ~(Inv.KH_SET | Inv.H3_PRO_SET),
            ),
        ],
        sources=["pv1_power", "pv2_power"],
        method=sum,
        name="PV Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:solar-power-variant-outline",
    )
    yield ModbusLambdaSensorDescription(
        key="pv_power_now",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.KH_SET,
            ),
        ],
        sources=["pv1_power", "pv2_power", "pv3_power", "pv4_power"],
        method=sum,
        name="PV Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:solar-power-variant-outline",
    )
    yield ModbusLambdaSensorDescription(
        key="pv_power_now",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.H3_PRO_SET,
            ),
        ],
        sources=["pv1_power", "pv2_power", "pv3_power", "pv4_power", "pv5_power", "pv6_power"],
        method=sum,
        name="PV Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:solar-power-variant-outline",
    )


def _h1_current_voltage_power_entities() -> Iterable[EntityFactory]:
    yield ModbusSensorDescription(
        key="load_power",
        addresses=[
            ModbusAddressesSpec(input=[11023], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31016], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_133),
            ModbusAddressesSpec(holding=[31054, 31053], models=Inv.KH_PRE133),
        ],
        name="Load Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:home-lightning-bolt-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="rvolt",  # Ideally rename to grid_voltage?
        addresses=[
            ModbusAddressesSpec(input=[11009], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31006], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
        entity_registry_enabled_default=False,
        name="Grid Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        signed=False,
        validate=[Range(0, 300)],
    )
    yield ModbusSensorDescription(
        key="rcurrent",
        addresses=[
            ModbusAddressesSpec(input=[11010], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31007], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
        name="Inverter Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="rpower",
        addresses=[
            ModbusAddressesSpec(input=[11011], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31008], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_133),
            ModbusAddressesSpec(holding=[31046, 31045], models=Inv.KH_PRE133),
        ],
        name="Inverter Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:export",
        scale=0.001,
        round_to=0.01,
        # Negative = charging batteries
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="rpower_Q",
        addresses=[
            ModbusAddressesSpec(input=[11012], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        entity_registry_enabled_default=False,
        name="Inverter Power (Reactive)",
        # REACTIVE_POWER only supports var, not kvar
        # device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kvar",
        icon="mdi:export",
        scale=0.001,
        round_to=0.01,
        # Negative = charging batteries
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="rpower_S",
        addresses=[
            ModbusAddressesSpec(input=[11013], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        entity_registry_enabled_default=False,
        name="Inverter Power (Apparent)",
        # APPARENT_POWER only supports VA, not kVA
        # device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kVA",
        icon="mdi:export",
        scale=0.001,
        round_to=0.01,
        # Negative = charging batteries
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_rvolt",
        addresses=[
            ModbusAddressesSpec(input=[11015], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31010], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
        entity_registry_enabled_default=False,
        name="EPS Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        signed=False,
        validate=[Range(0, 300)],
    )
    yield ModbusSensorDescription(
        key="eps_rcurrent",
        addresses=[
            ModbusAddressesSpec(input=[11016], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31011], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
        entity_registry_enabled_default=False,
        name="EPS Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_rpower",
        addresses=[
            ModbusAddressesSpec(input=[11017], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31012], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_133),
            ModbusAddressesSpec(holding=[31048, 31047], models=Inv.KH_PRE133),
        ],
        entity_registry_enabled_default=False,
        name="EPS Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:power-socket",
        scale=0.001,
        round_to=0.01,
        post_process=lambda x: max(x, 0),
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_rpower_Q",
        addresses=[
            ModbusAddressesSpec(input=[11018], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        entity_registry_enabled_default=False,
        name="EPS Power (Reactive)",
        # REACTIVE_POWER only supports var, not kvar
        # device_class=SensorDeviceClass.REACTIVE_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kvar",
        icon="mdi:power-socket",
        scale=0.001,
        round_to=0.01,
        post_process=lambda x: max(x, 0),
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_rpower_S",
        addresses=[
            ModbusAddressesSpec(input=[11019], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        entity_registry_enabled_default=False,
        name="EPS Power (Apparent)",
        # APPARENT_POWER only supports VA, not kVA
        # device_class=SensorDeviceClass.APPARENT_POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kVA",
        icon="mdi:power-socket",
        scale=0.001,
        round_to=0.01,
        post_process=lambda x: max(x, 0),
        validate=[Range(0, 100)],
    )

    # The KH uses the opposite sign for Grid CT, for some bizarre reason

    def _grid_ct(addresses: list[ModbusAddressesSpec], scale: float) -> Iterable[ModbusSensorDescription]:
        yield ModbusSensorDescription(
            key="grid_ct",
            addresses=addresses,
            name="Grid CT",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:meter-electric-outline",
            scale=scale,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )
        yield ModbusSensorDescription(
            key="feed_in",
            addresses=addresses,
            name="Feed-in",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:transmission-tower-import",
            scale=scale,
            round_to=0.01,
            post_process=lambda v: v if v > 0 else 0,
            validate=[Range(0, 100)],
        )
        yield ModbusSensorDescription(
            key="grid_consumption",
            addresses=addresses,
            name="Grid Consumption",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:transmission-tower-export",
            scale=scale,
            round_to=0.01,
            post_process=lambda v: abs(v) if v < 0 else 0,
            validate=[Range(0, 100)],
        )

    yield from _grid_ct(
        addresses=[
            ModbusAddressesSpec(input=[11021], models=Inv.H1_G1),
            ModbusAddressesSpec(holding=[31014], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET),
            ModbusAddressesSpec(holding=[39169, 39168], models=Inv.KH_133),
        ],
        scale=0.001,
    )
    yield from _grid_ct(
        addresses=[
            ModbusAddressesSpec(input=[11021], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31050, 31049], models=Inv.KH_PRE133),
        ],
        scale=-0.001,
    )

    def _ct2_meter(addresses: list[ModbusAddressesSpec], scale: float) -> ModbusSensorDescription:
        return ModbusSensorDescription(
            key="ct2_meter",
            addresses=addresses,
            name="CT2 Meter",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:meter-electric-outline",
            scale=scale,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )

    yield _ct2_meter(
        addresses=[
            ModbusAddressesSpec(input=[11022], models=Inv.H1_G1),
            ModbusAddressesSpec(holding=[31015], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET),
        ],
        scale=0.001,
    )
    yield _ct2_meter(
        addresses=[
            ModbusAddressesSpec(input=[11022], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31052, 31051], models=Inv.KH_PRE133),
            ModbusAddressesSpec(holding=[31015], models=Inv.KH_133),
        ],
        scale=-0.001,
    )


def _h3_current_voltage_power_entities() -> Iterable[EntityFactory]:
    def _grid_voltage(phase: str, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key=f"grid_voltage_{phase}",
            addresses=addresses,
            entity_registry_enabled_default=False,
            name=f"Grid Voltage {phase}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            scale=0.1,
            round_to=1,
            signed=False,
            validate=[Range(0, 300)],
        )

    yield _grid_voltage(
        "R",
        addresses=[
            ModbusAddressesSpec(holding=[31006], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39123], models=Inv.H3_PRO_SET),
        ],
    )
    yield _grid_voltage(
        "S",
        addresses=[
            ModbusAddressesSpec(holding=[31007], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39124], models=Inv.H3_PRO_SET),
        ],
    )
    yield _grid_voltage(
        "T",
        addresses=[
            ModbusAddressesSpec(holding=[31008], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39125], models=Inv.H3_PRO_SET),
        ],
    )

    def _inv_current(phase: str, addresses: list[ModbusAddressesSpec], scale: float) -> EntityFactory:
        return ModbusSensorDescription(
            key=f"inv_current_{phase}",
            addresses=addresses,
            name=f"Inverter Current {phase}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="A",
            scale=scale,
            round_to=1,
            validate=[Range(0, 100)],
        )

    def _inv_current_set(
        r_addresses: list[ModbusAddressesSpec],
        s_addresses: list[ModbusAddressesSpec],
        t_addresses: list[ModbusAddressesSpec],
        scale: float,
    ) -> Iterable[EntityFactory]:
        yield _inv_current("R", addresses=r_addresses, scale=scale)
        yield _inv_current("S", addresses=s_addresses, scale=scale)
        yield _inv_current("T", addresses=t_addresses, scale=scale)

    yield from _inv_current_set(
        r_addresses=[ModbusAddressesSpec(holding=[31009], models=Inv.H3_SET)],
        s_addresses=[ModbusAddressesSpec(holding=[31010], models=Inv.H3_SET)],
        t_addresses=[ModbusAddressesSpec(holding=[31011], models=Inv.H3_SET)],
        scale=0.1,
    )

    yield from _inv_current_set(
        r_addresses=[ModbusAddressesSpec(holding=[39127, 39126], models=Inv.H3_PRO_SET)],
        s_addresses=[ModbusAddressesSpec(holding=[39129, 39128], models=Inv.H3_PRO_SET)],
        t_addresses=[ModbusAddressesSpec(holding=[39131, 39130], models=Inv.H3_PRO_SET)],
        scale=0.001,
    )

    def _inv_power(phase: str | None, addresses: list[ModbusAddressesSpec], scale: float) -> EntityFactory:
        key_suffix = f"_{phase}" if phase is not None else ""
        name_suffix = f" {phase}" if phase is not None else ""
        return ModbusSensorDescription(
            key=f"inv_power{key_suffix}",
            addresses=addresses,
            name=f"Inverter Power{name_suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            scale=scale,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )

    yield _inv_power(
        phase=None,
        addresses=[
            ModbusAddressesSpec(holding=[39135, 39134], models=Inv.H3_PRO_SET),
        ],
        # This one appears to be in mW, despite what the spec says
        scale=0.000001,
    )
    yield _inv_power(
        "R",
        addresses=[
            ModbusAddressesSpec(holding=[31012], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39249, 39248], models=Inv.H3_PRO_SET),
        ],
        scale=0.001,
    )
    yield _inv_power(
        "S",
        addresses=[
            ModbusAddressesSpec(holding=[31013], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39251, 39250], models=Inv.H3_PRO_SET),
        ],
        scale=0.001,
    )
    yield _inv_power(
        "T",
        addresses=[
            ModbusAddressesSpec(holding=[31014], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39253, 39252], models=Inv.H3_PRO_SET),
        ],
        scale=0.001,
    )

    def _inv_power_reactive(phase: str | None, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        key_suffix = f"_{phase}" if phase is not None else ""
        name_suffix = f" {phase}" if phase is not None else ""
        return ModbusSensorDescription(
            key=f"inv_power_Q{key_suffix}",
            addresses=addresses,
            entity_registry_enabled_default=False,
            name=f"Inverter Power (Reactive){name_suffix}",
            # REACTIVE_POWER only supports var, not kvar
            # device_class=SensorDeviceClass.REACTIVE_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kvar",
            icon="mdi:export",
            scale=0.001,
            round_to=0.01,
            # Negative = charging batteries
            validate=[Range(-100, 100)],
        )

    yield _inv_power_reactive(
        phase=None, addresses=[ModbusAddressesSpec(holding=[39137, 39136], models=Inv.H3_PRO_SET)]
    )
    yield _inv_power_reactive(phase="R", addresses=[ModbusAddressesSpec(holding=[39257, 39256], models=Inv.H3_PRO_SET)])
    yield _inv_power_reactive(phase="S", addresses=[ModbusAddressesSpec(holding=[39259, 39258], models=Inv.H3_PRO_SET)])
    yield _inv_power_reactive(phase="T", addresses=[ModbusAddressesSpec(holding=[39261, 39260], models=Inv.H3_PRO_SET)])

    def _inv_power_apparent(phase: str | None, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        key_suffix = f"_{phase}" if phase is not None else ""
        name_suffix = f" {phase}" if phase is not None else ""
        return ModbusSensorDescription(
            key=f"rpower_S{key_suffix}",
            addresses=addresses,
            entity_registry_enabled_default=False,
            name=f"Inverter Power (Apparent){name_suffix}",
            # APPARENT_POWER only supports VA, not kVA
            # device_class=SensorDeviceClass.APPARENT_POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kVA",
            icon="mdi:export",
            scale=0.001,
            round_to=0.01,
            # Negative = charging batteries
            validate=[Range(-100, 100)],
        )

    yield _inv_power_apparent(phase="R", addresses=[ModbusAddressesSpec(holding=[39265, 39264], models=Inv.H3_PRO_SET)])
    yield _inv_power_apparent(phase="S", addresses=[ModbusAddressesSpec(holding=[39267, 39266], models=Inv.H3_PRO_SET)])
    yield _inv_power_apparent(phase="T", addresses=[ModbusAddressesSpec(holding=[39269, 39268], models=Inv.H3_PRO_SET)])

    def _eps_rvolt(phase: str, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key=f"eps_rvolt_{phase}",
            addresses=addresses,
            entity_registry_enabled_default=False,
            name=f"EPS Voltage_{phase}",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            scale=0.1,
            round_to=1,
            signed=False,
            validate=[Range(0, 300)],
        )

    yield _eps_rvolt("R", addresses=[ModbusAddressesSpec(holding=[39201], models=Inv.H3_PRO_SET)])
    yield _eps_rvolt("S", addresses=[ModbusAddressesSpec(holding=[39202], models=Inv.H3_PRO_SET)])
    yield _eps_rvolt("T", addresses=[ModbusAddressesSpec(holding=[39203], models=Inv.H3_PRO_SET)])

    def _eps_rcurrent(phase: str, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key=f"eps_rcurrent_{phase}",
            addresses=addresses,
            entity_registry_enabled_default=False,
            name=f"EPS Current {phase}",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="A",
            scale=0.001,
            round_to=1,
            validate=[Range(0, 100)],
        )

    yield _eps_rcurrent("R", addresses=[ModbusAddressesSpec(holding=[39205, 39204], models=Inv.H3_PRO_SET)])
    yield _eps_rcurrent("S", addresses=[ModbusAddressesSpec(holding=[39207, 39206], models=Inv.H3_PRO_SET)])
    yield _eps_rcurrent("T", addresses=[ModbusAddressesSpec(holding=[39209, 39208], models=Inv.H3_PRO_SET)])

    def _eps_power(phase: str, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key=f"eps_power_{phase}",
            addresses=addresses,
            entity_registry_enabled_default=False,
            name=f"EPS Power {phase}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:power-socket",
            scale=0.001,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )

    yield _eps_power(
        "R",
        addresses=[
            ModbusAddressesSpec(holding=[31022], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39213, 39212], models=Inv.H3_PRO_SET),
        ],
    )
    yield _eps_power(
        "S",
        addresses=[
            ModbusAddressesSpec(holding=[31023], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39215, 39214], models=Inv.H3_PRO_SET),
        ],
    )
    yield _eps_power(
        "T",
        addresses=[
            ModbusAddressesSpec(holding=[31024], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39217, 39216], models=Inv.H3_PRO_SET),
        ],
    )

    def _grid_ct(phase: str | None, scale: float, addresses: list[ModbusAddressesSpec]) -> Iterable[EntityFactory]:
        key_suffix = f"_{phase}" if phase is not None else ""
        name_suffix = f" {phase}" if phase is not None else ""

        yield ModbusSensorDescription(
            key=f"grid_ct{key_suffix}",
            addresses=addresses,
            name=f"Grid CT{name_suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:meter-electric-outline",
            scale=scale,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )
        yield ModbusSensorDescription(
            key=f"feed_in{key_suffix}",
            addresses=addresses,
            name=f"Feed-in{name_suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:transmission-tower-import",
            scale=scale,
            round_to=0.01,
            post_process=lambda v: v if v > 0 else 0,
            validate=[Range(0, 100)],
        )
        yield ModbusSensorDescription(
            key=f"grid_consumption{key_suffix}",
            addresses=addresses,
            name=f"Grid Consumption{name_suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:transmission-tower-export",
            scale=scale,
            round_to=0.01,
            post_process=lambda v: abs(v) if v < 0 else 0,
            validate=[Range(0, 100)],
        )

    yield from _grid_ct(
        phase=None,
        scale=0.0001,  # 0.1W
        addresses=[
            ModbusAddressesSpec(holding=[38815, 38814], models=Inv.H3_PRO_SET),
        ],
    )
    yield from _grid_ct(
        "R",
        scale=0.001,
        addresses=[
            ModbusAddressesSpec(holding=[31026], models=Inv.H3_SET),
        ],
    )
    yield from _grid_ct(
        "R",
        scale=0.0001,
        addresses=[
            ModbusAddressesSpec(holding=[38817, 38816], models=Inv.H3_PRO_SET),
        ],
    )
    yield from _grid_ct(
        "S",
        scale=0.001,
        addresses=[
            ModbusAddressesSpec(holding=[31027], models=Inv.H3_SET),
        ],
    )
    yield from _grid_ct(
        "S",
        scale=0.0001,
        addresses=[
            ModbusAddressesSpec(holding=[38819, 38818], models=Inv.H3_PRO_SET),
        ],
    )
    yield from _grid_ct(
        "T",
        scale=0.001,
        addresses=[
            ModbusAddressesSpec(holding=[31028], models=Inv.H3_SET),
        ],
    )
    yield from _grid_ct(
        "T",
        scale=0.0001,
        addresses=[
            ModbusAddressesSpec(holding=[38821, 38820], models=Inv.H3_PRO_SET),
        ],
    )

    def _ct2_meter(phase: str | None, scale: float, addresses: list[ModbusAddressesSpec]) -> ModbusSensorDescription:
        key_suffix = f"_{phase}" if phase is not None else ""
        name_suffix = f" {phase}" if phase is not None else ""

        return ModbusSensorDescription(
            key=f"ct2_meter{key_suffix}",
            addresses=addresses,
            name=f"CT2 Meter{name_suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:meter-electric-outline",
            scale=scale,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )

    yield _ct2_meter(
        phase=None, scale=0.0001, addresses=[ModbusAddressesSpec(holding=[38915, 38914], models=Inv.H3_PRO_SET)]
    )
    yield _ct2_meter("R", scale=0.0001, addresses=[ModbusAddressesSpec(holding=[38917, 38916], models=Inv.H3_PRO_SET)])
    yield _ct2_meter("S", scale=0.0001, addresses=[ModbusAddressesSpec(holding=[38919, 38918], models=Inv.H3_PRO_SET)])
    yield _ct2_meter("T", scale=0.0001, addresses=[ModbusAddressesSpec(holding=[38921, 38920], models=Inv.H3_PRO_SET)])

    def _load_power(phase: str | None, *, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        key_suffix = f"_{phase}" if phase is not None else ""
        name_suffix = f" {phase}" if phase is not None else ""
        return ModbusSensorDescription(
            key=f"load_power{key_suffix}",
            addresses=addresses,
            name=f"Load Power{name_suffix}",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:home-lightning-bolt-outline",
            scale=0.001,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )

    yield _load_power(
        "R",
        addresses=[
            ModbusAddressesSpec(holding=[31029], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39220, 39219], models=Inv.H3_PRO_SET),
        ],
    )
    yield _load_power(
        "S",
        addresses=[
            ModbusAddressesSpec(holding=[31030], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39222, 39221], models=Inv.H3_PRO_SET),
        ],
    )
    yield _load_power(
        "T",
        addresses=[
            ModbusAddressesSpec(holding=[31031], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39224, 39223], models=Inv.H3_PRO_SET),
        ],
    )
    yield _load_power(
        phase=None,
        addresses=[
            ModbusAddressesSpec(holding=[39226, 39225], models=Inv.H3_PRO_SET),
        ],
    )


def _inverter_entities() -> Iterable[EntityFactory]:
    def _invbatvolt(index: int | None, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        key_suffix = f"_{index}" if index is not None else ""
        name_infix = f" {index}" if index is not None else ""
        return ModbusSensorDescription(
            key=f"invbatvolt{key_suffix}",
            addresses=addresses,
            name=f"Inverter Battery{name_infix} Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            scale=0.1,
            round_to=1,
            # This can go negative if no battery is attached
        )

    yield _invbatvolt(
        index=None,
        addresses=[
            ModbusAddressesSpec(input=[11006], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31020], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
    )
    yield _invbatvolt(index=1, addresses=[ModbusAddressesSpec(holding=[39227], models=Inv.H3_PRO_SET)])
    yield _invbatvolt(index=2, addresses=[ModbusAddressesSpec(holding=[39232], models=Inv.H3_PRO_SET)])

    def _invbatcurrent(index: int | None, scale: float, addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        key_suffix = f"_{index}" if index is not None else ""
        name_infix = f" {index}" if index is not None else ""
        return ModbusSensorDescription(
            key=f"invbatcurrent{key_suffix}",
            addresses=addresses,
            name=f"Inverter Battery{name_infix} Current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="A",
            scale=scale,
            round_to=1,
            validate=[Range(-100, 100)],
        )

    yield _invbatcurrent(
        index=None,
        scale=0.1,
        addresses=[
            ModbusAddressesSpec(input=[11007], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31021], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
    )
    yield _invbatcurrent(
        index=1, scale=0.001, addresses=[ModbusAddressesSpec(holding=[39229, 39228], models=Inv.H3_PRO_SET)]
    )
    yield _invbatcurrent(
        index=2, scale=0.001, addresses=[ModbusAddressesSpec(holding=[39234, 39233], models=Inv.H3_PRO_SET)]
    )

    def _invbatpower(index: int | None, addresses: list[ModbusAddressesSpec]) -> Iterable[ModbusSensorDescription]:
        key_suffix = f"_{index}" if index is not None else ""
        name_infix = f" {index}" if index is not None else ""
        yield ModbusSensorDescription(
            key=f"invbatpower{key_suffix}",
            addresses=addresses,
            name=f"Inverter Battery{name_infix} Power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            scale=0.001,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )
        yield ModbusSensorDescription(
            key=f"battery_discharge{key_suffix}",
            addresses=addresses,
            name=f"Battery{name_infix} Discharge",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:battery-arrow-down-outline",
            scale=0.001,
            round_to=0.01,
            post_process=lambda v: v if v > 0 else 0,
            validate=[Range(0, 100)],
        )
        yield ModbusSensorDescription(
            key=f"battery_charge{key_suffix}",
            addresses=addresses,
            name=f"Battery{name_infix} Charge",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            icon="mdi:battery-arrow-up-outline",
            scale=0.001,
            round_to=0.01,
            post_process=lambda v: abs(v) if v < 0 else 0,
            validate=[Range(0, 100)],
        )

    yield from _invbatpower(
        index=None,
        addresses=[
            ModbusAddressesSpec(input=[11008], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31022], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31036], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39238, 39237], models=Inv.H3_PRO_SET),
        ],
    )
    yield from _invbatpower(
        index=1,
        addresses=[
            ModbusAddressesSpec(holding=[39231, 39230], models=Inv.H3_PRO_SET),
        ],
    )
    yield from _invbatpower(
        index=2,
        addresses=[
            # It does genuinely look like these two are the wrong way around, see
            # https://github.com/nathanmarlor/foxess_modbus/discussions/516#discussioncomment-9569558
            # ^^^^ Following on from this previous comment,
            # the H3 Pro firmware from Master 1.53, Manager 1.22 has corrected the endian for this
            # batpower2 register; it now matches the Fox modbus definition V1.05.00.00
            # see https://github.com/nathanmarlor/foxess_modbus/discussions/685#discussioncomment-10811413
            ModbusAddressesSpec(holding=[39236, 39235], models=Inv.H3_PRO_SET),
        ],
    )

    yield ModbusSensorDescription(
        key="rfreq",
        addresses=[
            ModbusAddressesSpec(input=[11014], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31009], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31015], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[38847, 38846], models=Inv.H3_PRO_PRE122),
            ModbusAddressesSpec(holding=[39139], models=Inv.H3_PRO_122),
        ],
        entity_registry_enabled_default=False,
        name="Grid Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
        round_to=0.1,
        signed=False,
        validate=[Range(0, 60)],
    )
    yield ModbusSensorDescription(
        key="eps_frequency",
        addresses=[
            ModbusAddressesSpec(input=[11020], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31013], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31025], models=Inv.H3_SET),
        ],
        entity_registry_enabled_default=False,
        name="EPS Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
        round_to=0.1,
        signed=False,
        validate=[Range(0, 60)],
    )
    yield ModbusSensorDescription(
        key="invtemp",
        addresses=[
            ModbusAddressesSpec(input=[11024], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31018], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31032], models=Inv.H3_SET),
            ModbusAddressesSpec(holding=[39141], models=Inv.H3_PRO_SET),
        ],
        name="Inverter Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        round_to=0.5,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="ambtemp",
        addresses=[
            ModbusAddressesSpec(input=[11025], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31019], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31033], models=Inv.H3_SET),
        ],
        name="Ambient Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        round_to=0.5,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_charge_rate",
        addresses=[
            ModbusAddressesSpec(input=[11041], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31025], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
        entity_registry_enabled_default=False,
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Charge Rate",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        signed=False,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_discharge_rate",
        addresses=[
            ModbusAddressesSpec(input=[11042], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31026], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
        ],
        entity_registry_enabled_default=False,
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Discharge Rate",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        signed=False,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_cycle_count",
        addresses=[
            ModbusAddressesSpec(input=[11048], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Cycle Count",
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:counter",
        signed=False,
        validate=[Min(0)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_watthours_total",
        addresses=[
            ModbusAddressesSpec(input=[11049], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        entity_registry_enabled_default=False,
        name="BMS Energy Throughput",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.001,
        round_to=1,
        signed=False,
        validate=[Min(0)],
    )

    def _inverter_fault_code(addresses: list[ModbusAddressesSpec], fault_set: FaultSet) -> EntityFactory:
        return ModbusFaultSensorDescription(
            key="inverter_fault_code",
            addresses=addresses,
            fault_set=fault_set,
            name="Inverter Fault Code",
            icon="mdi:alert-circle-outline",
        )

    yield _inverter_fault_code(
        # We don't map Fault Code 3, as it's unused
        addresses=[
            # These addresses are correct for the KH, but the fault codes are not
            ModbusAddressesSpec(input=[11061, 11062, 11064, 11065, 11066, 11067, 11068], models=Inv.H1_G1),
            ModbusAddressesSpec(
                holding=[31031, 31032, 31034, 31035, 31036, 31037, 31038], models=Inv.H1_G1 | Inv.H1_LAN
            ),
            ModbusAddressesSpec(holding=[31044, 31045, 31047, 31048, 31049, 31050, 31051], models=Inv.H3_SET),
        ],
        fault_set=STANDARD_FAULTS,
    )

    yield _inverter_fault_code(
        addresses=[
            ModbusAddressesSpec(holding=[39067, 39068, 39069], models=Inv.H3_PRO_SET | Inv.H1_G2_144 | Inv.KH_133),
        ],
        fault_set=H3_PRO_KH_133_FAULTS,
    )

    yield ModbusInverterStateSensorDescription(
        key="inverter_state",
        address=[
            ModbusAddressSpec(input=11056, models=Inv.H1_G1),
            ModbusAddressSpec(holding=31027, models=Inv.H1_G1 | Inv.H1_LAN),
        ],
        name="Inverter State",
        states=H1_INVERTER_STATES,
    )
    yield ModbusInverterStateSensorDescription(
        key="inverter_state",
        address=[
            ModbusAddressSpec(input=11056, models=Inv.KH_PRE119),
            ModbusAddressSpec(holding=31027, models=Inv.KH_PRE133 | Inv.KH_133),
        ],
        name="Inverter State",
        states=KH_INVERTER_STATES,
    )
    yield ModbusG2InverterStateSensorDescription(
        key="inverter_state",
        addresses=[
            ModbusAddressesSpec(holding=[39063, 39065], models=Inv.H1_G2_SET | Inv.H3_PRO_SET),
        ],
        name="Inverter State",
    )
    yield ModbusSensorDescription(
        key="state_code",
        addresses=[
            ModbusAddressesSpec(holding=[31041], models=Inv.H3_SET),
        ],
        name="Inverter State Code",
        state_class=SensorStateClass.MEASUREMENT,
    )

    def _solar_energy_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        # There are 32xxx holding registers on the H1, but they're only accessible over RS485
        return ModbusSensorDescription(
            key="solar_energy_total",
            addresses=addresses,
            name="Solar Generation Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:solar-power",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _solar_energy_total(
        addresses=[
            ModbusAddressesSpec(input=[11070, 11069], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32001, 32000], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39602, 39601], models=Inv.H3_PRO_SET),
        ],
    )

    def _solar_energy_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="solar_energy_today",
            addresses=addresses,
            name="Solar Generation Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:solar-power",
            scale=0.1,
            signed=False,
            validate=[Range(0, 1000)],
        )

    yield _solar_energy_today(
        addresses=[
            ModbusAddressesSpec(input=[11071], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32002], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39604, 39603], models=Inv.H3_PRO_SET),
        ],
    )

    def _battery_charge_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="battery_charge_total",
            addresses=addresses,
            name="Battery Charge Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:battery-arrow-up-outline",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _battery_charge_total(
        addresses=[
            ModbusAddressesSpec(input=[11073, 11072], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32004, 32003], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39606, 39605], models=Inv.H3_PRO_SET),
        ],
    )

    yield ModbusIntegrationSensorDescription(
        key="battery_charge_total",
        models=[
            EntitySpec(register_types=[RegisterType.HOLDING], models=Inv.H1_LAN),
        ],
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-up-outline",
        integration_method="left",
        name="Battery Charge Total",
        source_entity="battery_charge",
        unit_time=UnitOfTime.HOURS,
    )

    def _battery_charge_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="battery_charge_today",
            addresses=addresses,
            name="Battery Charge Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:battery-arrow-up-outline",
            scale=0.1,
            validate=[Range(0, 100)],
        )

    yield _battery_charge_today(
        addresses=[
            ModbusAddressesSpec(input=[11074], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32005], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET),
            ModbusAddressesSpec(holding=[32005], models=Inv.KH_PRE133 | Inv.KH_133),
            ModbusAddressesSpec(holding=[39608, 39607], models=Inv.H3_PRO_SET),
        ],
    )

    def _battery_discharge_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="battery_discharge_total",
            addresses=addresses,
            name="Battery Discharge Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:battery-arrow-down-outline",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _battery_discharge_total(
        addresses=[
            ModbusAddressesSpec(input=[11076, 11075], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32007, 32006], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39610, 39609], models=Inv.H3_PRO_SET),
        ],
    )

    yield ModbusIntegrationSensorDescription(
        key="battery_discharge_total",
        models=[
            EntitySpec(register_types=[RegisterType.HOLDING], models=Inv.H1_LAN),
        ],
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-down-outline",
        integration_method="left",
        name="Battery Discharge Total",
        source_entity="battery_discharge",
        unit_time=UnitOfTime.HOURS,
    )

    def _battery_discharge_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="battery_discharge_today",
            addresses=addresses,
            name="Battery Discharge Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:battery-arrow-down-outline",
            scale=0.1,
            validate=[Range(0, 100)],
        )

    yield _battery_discharge_today(
        addresses=[
            ModbusAddressesSpec(input=[11077], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32008], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39612, 39611], models=Inv.H3_PRO_SET),
        ],
    )

    def _feed_in_energy_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="feed_in_energy_total",
            addresses=addresses,
            name="Feed-in Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:transmission-tower-import",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _feed_in_energy_total(
        addresses=[
            ModbusAddressesSpec(input=[11079, 11078], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32010, 32009], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39614, 39613], models=Inv.H3_PRO_SET),
        ],
    )

    yield ModbusIntegrationSensorDescription(
        key="feed_in_energy_total",
        models=[
            EntitySpec(register_types=[RegisterType.HOLDING], models=Inv.H1_LAN),
        ],
        name="Feed-in Total",
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        integration_method="left",
        source_entity="feed_in",
        unit_time=UnitOfTime.HOURS,
        icon="mdi:transmission-tower-import",
    )

    def _feed_in_energy_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="feed_in_energy_today",
            addresses=addresses,
            name="Feed-in Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:transmission-tower-import",
            scale=0.1,
            validate=[Range(0, 1000)],
        )

    yield _feed_in_energy_today(
        addresses=[
            ModbusAddressesSpec(input=[11080], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32011], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39616, 39615], models=Inv.H3_PRO_SET),
        ],
    )

    def _grid_consumption_energy_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="grid_consumption_energy_total",
            addresses=addresses,
            name="Grid Consumption Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:transmission-tower-export",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _grid_consumption_energy_total(
        addresses=[
            ModbusAddressesSpec(input=[11082, 11081], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32013, 32012], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39618, 39617], models=Inv.H3_PRO_SET),
        ],
    )

    yield ModbusIntegrationSensorDescription(
        key="grid_consumption_energy_total",
        models=[
            EntitySpec(register_types=[RegisterType.HOLDING], models=Inv.H1_LAN),
        ],
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Grid Consumption Total",
        source_entity="grid_consumption",
        unit_time=UnitOfTime.HOURS,
        icon="mdi:transmission-tower-export",
    )

    def _grid_consumption_energy_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="grid_consumption_energy_today",
            addresses=addresses,
            name="Grid Consumption Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:transmission-tower-export",
            scale=0.1,
            validate=[Range(0, 1000)],
        )

    yield _grid_consumption_energy_today(
        addresses=[
            ModbusAddressesSpec(input=[11083], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32014], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39620, 39619], models=Inv.H3_PRO_SET),
        ],
    )

    def _total_yield_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="total_yield_total",
            addresses=addresses,
            name="Yield Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:export",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _total_yield_total(
        addresses=[
            ModbusAddressesSpec(input=[11085, 11084], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32016, 32015], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39622, 39621], models=Inv.H3_PRO_SET),
        ],
    )

    def _total_yield_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="total_yield_today",
            addresses=addresses,
            name="Yield Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:export",
            scale=0.1,
            # unsure if this actually goes negative
            validate=[Range(-100, 100)],
        )

    yield _total_yield_today(
        addresses=[
            ModbusAddressesSpec(input=[11086], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32017], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39624, 39623], models=Inv.H3_PRO_SET),
        ],
    )

    def _input_energy_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="input_energy_total",
            addresses=addresses,
            name="Input Energy Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:import",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _input_energy_total(
        addresses=[
            ModbusAddressesSpec(input=[11088, 11087], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32019, 32018], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39626, 39625], models=Inv.H3_PRO_SET),
        ],
    )

    def _input_energy_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="input_energy_today",
            addresses=addresses,
            name="Input Energy Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:import",
            scale=0.1,
            # unsure if this actually goes negative
            validate=[Range(-1000, 1000)],
        )

    yield _input_energy_today(
        addresses=[
            ModbusAddressesSpec(input=[11089], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32020], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39628, 39627], models=Inv.H3_PRO_SET),
        ],
    )

    def _load_power_total(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="load_power_total",
            addresses=addresses,
            name="Load Energy Total",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            icon="mdi:home-lightning-bolt-outline",
            scale=0.1,
            signed=False,
            validate=[Min(0)],
        )

    yield _load_power_total(
        addresses=[
            # TODO: There are registers for H1, but we currently use an integration
            # ModbusAddressesSpec(
            #     models=H1_SET, input=[11091, 11090]
            # ),
            ModbusAddressesSpec(input=[11091, 11090], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32022, 32021], models=Inv.KH_PRE133 | Inv.KH_133 | Inv.H1_G2_SET | Inv.H3_SET),
            ModbusAddressesSpec(holding=[39630, 39629], models=Inv.H3_PRO_SET),
        ],
    )

    yield ModbusIntegrationSensorDescription(
        key="load_power_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.H1_G1 | Inv.H1_LAN,
            )
        ],
        device_class=SensorDeviceClass.ENERGY,
        native_unit_of_measurement="kWh",
        icon="mdi:home-lightning-bolt-outline",
        integration_method="left",
        name="Load Energy Total",
        source_entity="load_power",
        unit_time=UnitOfTime.HOURS,
    )

    def _load_energy_today(addresses: list[ModbusAddressesSpec]) -> EntityFactory:
        return ModbusSensorDescription(
            key="load_energy_today",
            addresses=addresses,
            name="Load Energy Today",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL_INCREASING,
            native_unit_of_measurement="kWh",
            icon="mdi:home-lightning-bolt-outline",
            scale=0.1,
            # unsure if this actually goes negative
            validate=[Range(-1000, 1000)],
        )

    yield _load_energy_today(
        addresses=[
            ModbusAddressesSpec(input=[11092], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[32023], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[39632, 39631], models=Inv.H3_PRO_SET),
        ],
    )


def _bms_entities() -> Iterable[EntityFactory]:
    def _inner(
        index: int | None,
        bms_connect_state_address: list[ModbusAddressSpec],
        batvolt: list[ModbusAddressesSpec],
        bat_current: list[ModbusAddressesSpec],
        battery_soc: list[ModbusAddressesSpec],
        battery_soh: list[ModbusAddressesSpec],
        battery_temp: list[ModbusAddressesSpec],
        bms_cell_temp_high: list[ModbusAddressesSpec],
        bms_cell_temp_low: list[ModbusAddressesSpec],
        bms_cell_mv_high: list[ModbusAddressesSpec],
        bms_cell_mv_low: list[ModbusAddressesSpec],
        bms_kwh_remaining: list[ModbusAddressesSpec],
    ) -> Iterable[EntityFactory]:
        key_suffix = f"_{index}" if index is not None else ""
        name_infix = f" {index}" if index is not None else ""

        yield ModbusSensorDescription(
            key=f"batvolt{key_suffix}",
            addresses=batvolt,
            name=f"Battery{name_infix} Voltage",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="V",
            scale=0.1,
            round_to=1,
            validate=[Min(0)],
        )
        yield ModbusSensorDescription(
            key=f"bat_current{key_suffix}",
            addresses=bat_current,
            name=f"Battery{name_infix} Current",
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="A",
            scale=0.1,
            round_to=1,
            validate=[Range(-100, 100)],
        )
        yield ModbusBatterySensorDescription(
            key=f"battery_soc{key_suffix}",
            addresses=battery_soc,
            bms_connect_state_address=bms_connect_state_address,
            name=f"Battery{name_infix} SoC",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            signed=False,
            validate=[Range(0, 100)],
        )
        yield ModbusBatterySensorDescription(
            key=f"battery_soh{key_suffix}",
            addresses=battery_soh,
            bms_connect_state_address=bms_connect_state_address,
            name=f"Battery{name_infix} SoH",
            device_class=SensorDeviceClass.BATTERY,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="%",
            signed=False,
            validate=[Range(0, 100)],
        )
        yield ModbusBatterySensorDescription(
            key=f"battery_temp{key_suffix}",
            addresses=battery_temp,
            bms_connect_state_address=bms_connect_state_address,
            name=f"Battery{name_infix} Temp",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="°C",
            scale=0.1,
            validate=[Range(0, 100)],
        )
        yield ModbusBatterySensorDescription(
            key=f"bms_cell_temp_high{key_suffix}",
            addresses=bms_cell_temp_high,
            bms_connect_state_address=bms_connect_state_address,
            name=f"BMS{name_infix} Cell Temp High",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="°C",
            scale=0.1,
            validate=[Range(0, 100)],
        )
        yield ModbusBatterySensorDescription(
            key=f"bms_cell_temp_low{key_suffix}",
            addresses=bms_cell_temp_low,
            bms_connect_state_address=bms_connect_state_address,
            name=f"BMS{name_infix} Cell Temp Low",
            device_class=SensorDeviceClass.TEMPERATURE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="°C",
            scale=0.1,
            validate=[Range(0, 100)],
        )
        yield ModbusBatterySensorDescription(
            key=f"bms_cell_mv_high{key_suffix}",
            addresses=bms_cell_mv_high,
            bms_connect_state_address=bms_connect_state_address,
            name=f"BMS{name_infix} Cell mV High",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="mV",
            signed=False,
            round_to=10,
            validate=[Min(0)],
        )
        yield ModbusBatterySensorDescription(
            key=f"bms_cell_mv_low{key_suffix}",
            addresses=bms_cell_mv_low,
            bms_connect_state_address=bms_connect_state_address,
            name=f"BMS{name_infix} Cell mV Low",
            device_class=SensorDeviceClass.VOLTAGE,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="mV",
            signed=False,
            round_to=10,
            validate=[Min(0)],
        )
        yield ModbusBatterySensorDescription(
            key=f"bms_kwh_remaining{key_suffix}",
            addresses=bms_kwh_remaining,
            bms_connect_state_address=bms_connect_state_address,
            name=f"BMS{name_infix} kWh Remaining",
            device_class=SensorDeviceClass.ENERGY,
            state_class=SensorStateClass.TOTAL,
            native_unit_of_measurement="kWh",
            scale=0.01,
            signed=False,
            validate=[Min(0)],
        )

    yield from _inner(
        index=None,
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        batvolt=[
            ModbusAddressesSpec(input=[11034], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37609], models=Inv.H1_G2_144),
            ModbusAddressesSpec(holding=[31034], models=Inv.H3_SET),
        ],
        bat_current=[
            ModbusAddressesSpec(input=[11035], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37610], models=Inv.H1_G2_144),
            ModbusAddressesSpec(holding=[31035], models=Inv.H3_SET),
        ],
        battery_soc=[
            ModbusAddressesSpec(input=[11036], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31024], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31038], models=Inv.H3_SET),
        ],
        battery_soh=[
            # Temporarily removed, see #756
            # ModbusAddressesSpec(input=[11104], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37624], models=Inv.H1_G2_144 | Inv.KH_133),
            ModbusAddressesSpec(holding=[31090], models=Inv.H3_180),
        ],
        battery_temp=[
            ModbusAddressesSpec(input=[11038], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[31023], models=Inv.H1_G1 | Inv.H1_LAN | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[31037], models=Inv.H3_SET),
        ],
        bms_cell_temp_high=[
            ModbusAddressesSpec(input=[11043], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37617], models=Inv.H1_G2_144 | Inv.KH_133),
            ModbusAddressesSpec(holding=[31102], models=Inv.H3_180),
        ],
        bms_cell_temp_low=[
            ModbusAddressesSpec(input=[11044], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37618], models=Inv.H1_G2_144 | Inv.KH_133),
            ModbusAddressesSpec(holding=[31103], models=Inv.H3_180),
        ],
        bms_cell_mv_high=[
            ModbusAddressesSpec(input=[11045], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37619], models=Inv.H1_G2_144 | Inv.KH_133),
            ModbusAddressesSpec(holding=[31100], models=Inv.H3_180),
        ],
        bms_cell_mv_low=[
            ModbusAddressesSpec(input=[11046], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37620], models=Inv.H1_G2_144 | Inv.KH_133),
            ModbusAddressesSpec(holding=[31101], models=Inv.H3_180),
        ],
        bms_kwh_remaining=[
            ModbusAddressesSpec(input=[11037], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[37632], models=Inv.H1_G2_SET | Inv.KH_133),
            ModbusAddressesSpec(holding=[31123], models=Inv.H3_180),
        ],
    )
    yield from _inner(
        index=1,
        bms_connect_state_address=[ModbusAddressSpec(holding=37002, models=Inv.H3_PRO_SET)],
        batvolt=[ModbusAddressesSpec(holding=[37609], models=Inv.H3_PRO_SET)],
        bat_current=[ModbusAddressesSpec(holding=[37610], models=Inv.H3_PRO_SET)],
        battery_soc=[ModbusAddressesSpec(holding=[37612], models=Inv.H3_PRO_SET)],
        # Added in H3_PRO v1.25, which hasn't been released yet.
        # See https://github.com/nathanmarlor/foxess_modbus/pull/775#issuecomment-2656447502
        battery_soh=[],
        # battery_soh=[ModbusAddressesSpec(holding=[37624], models=Inv.H3_PRO_122)],
        battery_temp=[ModbusAddressesSpec(holding=[37611], models=Inv.H3_PRO_SET)],
        bms_cell_temp_high=[ModbusAddressesSpec(holding=[37617], models=Inv.H3_PRO_SET)],
        bms_cell_temp_low=[ModbusAddressesSpec(holding=[37618], models=Inv.H3_PRO_SET)],
        bms_cell_mv_high=[ModbusAddressesSpec(holding=[37619], models=Inv.H3_PRO_SET)],
        bms_cell_mv_low=[ModbusAddressesSpec(holding=[37610], models=Inv.H3_PRO_SET)],
        bms_kwh_remaining=[ModbusAddressesSpec(holding=[37632], models=Inv.H3_PRO_SET)],
    )
    yield from _inner(
        index=2,
        bms_connect_state_address=[ModbusAddressSpec(holding=37700, models=Inv.H3_PRO_SET)],
        batvolt=[ModbusAddressesSpec(holding=[38307], models=Inv.H3_PRO_SET)],
        bat_current=[ModbusAddressesSpec(holding=[38308], models=Inv.H3_PRO_SET)],
        battery_soc=[ModbusAddressesSpec(holding=[38310], models=Inv.H3_PRO_SET)],
        # Added in H3_PRO v1.25, which hasn't been released yet.
        # See https://github.com/nathanmarlor/foxess_modbus/pull/775#issuecomment-2656447502
        battery_soh=[],
        # battery_soh=[ModbusAddressesSpec(holding=[38322], models=Inv.H3_PRO_122)],
        battery_temp=[ModbusAddressesSpec(holding=[38309], models=Inv.H3_PRO_SET)],
        bms_cell_temp_high=[ModbusAddressesSpec(holding=[38315], models=Inv.H3_PRO_SET)],
        bms_cell_temp_low=[ModbusAddressesSpec(holding=[38316], models=Inv.H3_PRO_SET)],
        bms_cell_mv_high=[ModbusAddressesSpec(holding=[38317], models=Inv.H3_PRO_SET)],
        bms_cell_mv_low=[ModbusAddressesSpec(holding=[38318], models=Inv.H3_PRO_SET)],
        bms_kwh_remaining=[ModbusAddressesSpec(holding=[38330], models=Inv.H3_PRO_SET)],
    )


def _configuration_entities() -> Iterable[EntityFactory]:
    yield ModbusWorkModeSelectDescription(
        key="work_mode",
        address=[
            ModbusAddressSpec(input=41000, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=41000, models=Inv.H1_G1 | Inv.KH_PRE133 | Inv.KH_133),
        ],
        name="Work Mode",
        options_map={0: "Self Use", 1: "Feed-in First", 2: "Back-up"},
    )

    yield ModbusWorkModeSelectDescription(
        key="work_mode",
        address=[
            ModbusAddressSpec(holding=49203, models=Inv.H3_PRO_SET),
        ],
        name="Work Mode",
        options_map={
            1: "Self Use",
            2: "Feed-in First",
            3: "Back-up",
            4: "Peak Shaving",
        },
    )

    yield ModbusWorkModeSelectDescription(
        key="work_mode",
        address=[
            ModbusAddressSpec(holding=41000, models=Inv.H1_G2_SET | Inv.H3_SET),
        ],
        name="Work Mode",
        options_map={0: "Self Use", 1: "Feed-in First", 2: "Back-up", 4: "Peak Shaving"},
    )

    # Sensors are a bit nicer to look at: keep for consistency with other numbers
    yield ModbusSensorDescription(
        key="max_charge_current",
        addresses=[
            ModbusAddressesSpec(input=[41007], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[41007], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[46607], models=Inv.H3_PRO_SET),
        ],
        name="Max Charge Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 50)],
    )
    yield ModbusNumberDescription(
        key="max_charge_current",
        address=[
            ModbusAddressSpec(input=41007, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(
                holding=41007, models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressSpec(holding=46607, models=Inv.H3_PRO_SET),
        ],
        name="Max Charge Current",
        mode=NumberMode.BOX,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 50)],
    )

    yield ModbusSensorDescription(
        key="max_discharge_current",
        addresses=[
            ModbusAddressesSpec(input=[41008], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[41008], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[46608], models=Inv.H3_PRO_SET),
        ],
        name="Max Discharge Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 50)],
    )
    yield ModbusNumberDescription(
        key="max_discharge_current",
        address=[
            ModbusAddressSpec(input=41008, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(
                holding=41008, models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.KH_PRE133 | Inv.KH_133 | Inv.H3_SET
            ),
            ModbusAddressSpec(holding=46608, models=Inv.H3_PRO_SET),
        ],
        name="Max Discharge Current",
        mode=NumberMode.BOX,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=50,
        native_step=0.1,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 50)],
    )

    # Sensor kept for back compat
    yield ModbusSensorDescription(
        key="min_soc",
        addresses=[
            ModbusAddressesSpec(input=[41009], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[41009], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[46609], models=Inv.H3_PRO_SET),
        ],
        name="Min SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:battery-arrow-down",
        native_unit_of_measurement="%",
        validate=[Range(0, 100)],
    )
    yield ModbusNumberDescription(
        key="min_soc",
        address=[
            ModbusAddressSpec(input=41009, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(
                holding=41009, models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressSpec(holding=46609, models=Inv.H3_PRO_SET),
        ],
        name="Min SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-down",
        validate=[Range(0, 100)],
    )

    # Sensor kept for back compat
    yield ModbusSensorDescription(
        key="max_soc",
        addresses=[
            ModbusAddressesSpec(input=[41010], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[41010], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[46610], models=Inv.H3_PRO_SET),
        ],
        name="Max SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        icon="mdi:battery-arrow-up",
        validate=[Range(0, 100)],
    )
    yield ModbusNumberDescription(
        key="max_soc",
        address=[
            ModbusAddressSpec(input=41010, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(
                holding=41010, models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressSpec(holding=46610, models=Inv.H3_PRO_SET),
        ],
        name="Max SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-up",
        validate=[Range(0, 100)],
    )

    # Sensor kept for back compat
    yield ModbusSensorDescription(
        key="min_soc_on_grid",
        addresses=[
            ModbusAddressesSpec(input=[41011], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(
                holding=[41011], models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressesSpec(holding=[46611], models=Inv.H3_PRO_SET),
        ],
        name="Min SoC (On Grid)",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        icon="mdi:battery-arrow-down",
        validate=[Range(0, 100)],
    )
    yield ModbusNumberDescription(
        key="min_soc_on_grid",
        address=[
            ModbusAddressSpec(input=41011, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(
                holding=41011, models=Inv.H1_G1 | Inv.H1_G2_SET | Inv.H3_SET | Inv.KH_PRE133 | Inv.KH_133
            ),
            ModbusAddressSpec(holding=46611, models=Inv.H3_PRO_SET),
        ],
        name="Min SoC (On Grid)",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-down",
        validate=[Range(0, 100)],
    )


ENTITIES: list[EntityFactory] = list(
    itertools.chain(
        _version_entities(),
        _pv_entities(),
        _h1_current_voltage_power_entities(),
        _h3_current_voltage_power_entities(),
        _inverter_entities(),
        _bms_entities(),
        _configuration_entities(),
        (description for x in CHARGE_PERIODS for description in x.entity_descriptions),
        REMOTE_CONTROL_DESCRIPTION.entity_descriptions,
    )
)
