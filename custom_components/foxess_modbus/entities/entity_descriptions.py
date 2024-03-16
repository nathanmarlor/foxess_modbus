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
from .modbus_fault_sensor import ModbusFaultSensorDescription
from .modbus_integration_sensor import ModbusIntegrationSensorDescription
from .modbus_inverter_state_sensor import H1_INVERTER_STATES
from .modbus_inverter_state_sensor import KH_INVERTER_STATES
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


# TODO: There should be equivalent registers for the H3 somewhere
BMS_CONNECT_STATE_ADDRESS = [
    ModbusAddressSpec(input=11058, models=Inv.H1_G1 | Inv.KH_PRE119),
    ModbusAddressSpec(holding=31029, models=Inv.H1_G1 | Inv.H1_LAN),
    ModbusAddressSpec(holding=31028, models=Inv.KH_119),
    ModbusAddressSpec(holding=31042, models=Inv.H3_SET),
]


def _version_entities() -> Iterable[EntityFactory]:
    # Named so that they sort together
    yield ModbusVersionSensorDescription(
        key="master_version",
        address=[
            ModbusAddressSpec(input=11016, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=30016, models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
        ],
        is_hex=False,
        name="Version: Master",
        icon="mdi:source-branch",
    )
    yield ModbusVersionSensorDescription(
        key="slave_version",
        address=[
            ModbusAddressSpec(input=11017, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=30017, models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
        ],
        is_hex=False,
        name="Version: Slave",
        icon="mdi:source-branch",
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
            ModbusAddressSpec(input=11018, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=30018, models=Inv.H1_G1 | Inv.H1_LAN | Inv.H3_SET),
        ],
        is_hex=False,
    )
    yield _manager_version(
        address=[
            ModbusAddressSpec(holding=30018, models=Inv.KH_119),
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

    def _pv_current(key: str, addresses: list[ModbusAddressesSpec], name: str) -> EntityFactory:
        return ModbusSensorDescription(
            key=key,
            addresses=addresses,
            name=name,
            device_class=SensorDeviceClass.CURRENT,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="A",
            scale=0.1,
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
            ModbusAddressesSpec(holding=[31000], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
        ],
        name="PV1 Voltage",
    )
    yield _pv_current(
        key="pv1_current",
        addresses=[
            ModbusAddressesSpec(input=[11001], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31001], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
        ],
        name="PV1 Current",
    )
    yield _pv_power(
        key="pv1_power",
        addresses=[
            ModbusAddressesSpec(input=[11002], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31002], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[31003], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
        ],
        name="PV2 Voltage",
    )
    yield _pv_current(
        key="pv2_current",
        addresses=[
            ModbusAddressesSpec(input=[11004], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31004], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
        ],
        name="PV2 Current",
    )
    yield _pv_power(
        key="pv2_power",
        addresses=[
            ModbusAddressesSpec(input=[11005], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31005], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[31039], models=Inv.KH_119),
        ],
        name="PV3 Voltage",
    )
    yield _pv_current(
        key="pv3_current",
        addresses=[
            ModbusAddressesSpec(input=[11097], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31040], models=Inv.KH_119),
        ],
        name="PV3 Current",
    )
    yield _pv_power(
        key="pv3_power",
        addresses=[
            ModbusAddressesSpec(input=[11098], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31041], models=Inv.KH_119),
        ],
        name="PV3 Power",
    )
    yield _pv_energy_total(
        key="pv3_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.KH_SET,
            ),
        ],
        name="PV3 Power Total",
        source_entity="pv3_power",
    )
    yield _pv_voltage(
        key="pv4_voltage",
        addresses=[
            ModbusAddressesSpec(input=[11099], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31042], models=Inv.KH_119),
        ],
        name="PV4 Voltage",
    )
    yield _pv_current(
        key="pv4_current",
        addresses=[
            ModbusAddressesSpec(input=[11100], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31043], models=Inv.KH_119),
        ],
        name="PV4 Current",
    )
    yield _pv_power(
        key="pv4_power",
        addresses=[
            ModbusAddressesSpec(input=[11101], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31044], models=Inv.KH_119),
        ],
        name="PV4 Power",
    )
    yield _pv_energy_total(
        key="pv4_energy_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.KH_SET,
            ),
        ],
        name="PV4 Power Total",
        source_entity="pv4_power",
    )
    yield ModbusLambdaSensorDescription(
        key="pv_power_now",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=Inv.ALL & ~Inv.KH_SET,
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


def _h1_current_voltage_power_entities() -> Iterable[EntityFactory]:
    yield ModbusSensorDescription(
        key="invbatvolt",
        addresses=[
            ModbusAddressesSpec(input=[11006], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31020], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
        ],
        name="Inverter Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        # This can go negative if no battery is attached
    )
    yield ModbusSensorDescription(
        key="invbatcurrent",
        addresses=[
            ModbusAddressesSpec(input=[11007], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31021], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
        ],
        name="Inverter Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="load_power",
        addresses=[
            ModbusAddressesSpec(input=[11007], models=Inv.H1_G1),
            ModbusAddressesSpec(input=[11023], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31016], models=Inv.H1_G1 | Inv.H1_LAN),
            ModbusAddressesSpec(holding=[31054, 31053], models=Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31006], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31007], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31008], models=Inv.H1_G1 | Inv.H1_LAN),
            ModbusAddressesSpec(holding=[31046, 31045], models=Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31010], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31011], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31012], models=Inv.H1_G1 | Inv.H1_LAN),
            ModbusAddressesSpec(holding=[31048, 31047], models=Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31014], models=Inv.H1_G1 | Inv.H1_LAN),
        ],
        scale=0.001,
    )
    yield from _grid_ct(
        addresses=[
            ModbusAddressesSpec(input=[11021], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31050, 31049], models=Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31015], models=Inv.H1_G1 | Inv.H1_LAN),
        ],
        scale=0.001,
    )
    yield _ct2_meter(
        addresses=[
            ModbusAddressesSpec(input=[11022], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31052, 31051], models=Inv.KH_119),
        ],
        scale=-0.001,
    )


def _h3_current_voltage_power_entities() -> Iterable[EntityFactory]:
    yield ModbusSensorDescription(
        key="grid_voltage_R",
        addresses=[ModbusAddressesSpec(holding=[31006], models=Inv.H3_SET)],
        entity_registry_enabled_default=False,
        name="Grid Voltage R",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        signed=False,
        validate=[Range(0, 300)],
    )
    yield ModbusSensorDescription(
        key="grid_voltage_S",
        addresses=[ModbusAddressesSpec(holding=[31007], models=Inv.H3_SET)],
        entity_registry_enabled_default=False,
        name="Grid Voltage S",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        signed=False,
        validate=[Range(0, 300)],
    )
    yield ModbusSensorDescription(
        key="grid_voltage_T",
        addresses=[ModbusAddressesSpec(holding=[31008], models=Inv.H3_SET)],
        entity_registry_enabled_default=False,
        name="Grid Voltage T",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        signed=False,
        validate=[Range(0, 300)],
    )
    yield ModbusSensorDescription(
        key="inv_current_R",
        addresses=[ModbusAddressesSpec(holding=[31009], models=Inv.H3_SET)],
        name="Inverter Current R",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="inv_current_S",
        addresses=[ModbusAddressesSpec(holding=[31010], models=Inv.H3_SET)],
        name="Inverter Current S",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="inv_current_T",
        addresses=[ModbusAddressesSpec(holding=[31011], models=Inv.H3_SET)],
        name="Inverter Current T",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="inv_power_R",
        addresses=[ModbusAddressesSpec(holding=[31012], models=Inv.H3_SET)],
        name="Inverter Power R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="inv_power_S",
        addresses=[ModbusAddressesSpec(holding=[31013], models=Inv.H3_SET)],
        name="Inverter Power S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="inv_power_T",
        addresses=[ModbusAddressesSpec(holding=[31014], models=Inv.H3_SET)],
        name="Inverter Power T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_power_R",
        addresses=[ModbusAddressesSpec(holding=[31022], models=Inv.H3_SET)],
        entity_registry_enabled_default=False,
        name="EPS Power R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:power-socket",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_power_S",
        addresses=[ModbusAddressesSpec(holding=[31023], models=Inv.H3_SET)],
        entity_registry_enabled_default=False,
        name="EPS Power S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:power-socket",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="eps_power_T",
        addresses=[ModbusAddressesSpec(holding=[31024], models=Inv.H3_SET)],
        entity_registry_enabled_default=False,
        name="EPS Power T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:power-socket",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="grid_ct_R",
        addresses=[ModbusAddressesSpec(holding=[31026], models=Inv.H3_SET)],
        name="Grid CT R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:meter-electric-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="feed_in_R",
        addresses=[ModbusAddressesSpec(holding=[31026], models=Inv.H3_SET)],
        name="Feed-in R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:transmission-tower-import",
        scale=0.001,
        round_to=0.01,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="grid_consumption_R",
        addresses=[ModbusAddressesSpec(holding=[31026], models=Inv.H3_SET)],
        name="Grid Consumption R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:transmission-tower-export",
        scale=0.001,
        round_to=0.01,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="grid_ct_S",
        addresses=[ModbusAddressesSpec(holding=[31027], models=Inv.H3_SET)],
        name="Grid CT S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:meter-electric-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="feed_in_S",
        addresses=[ModbusAddressesSpec(holding=[31027], models=Inv.H3_SET)],
        name="Feed-in S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:transmission-tower-import",
        scale=0.001,
        round_to=0.01,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="grid_consumption_S",
        addresses=[ModbusAddressesSpec(holding=[31027], models=Inv.H3_SET)],
        name="Grid Consumption S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:transmission-tower-export",
        scale=0.001,
        round_to=0.01,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="grid_ct_T",
        addresses=[ModbusAddressesSpec(holding=[31028], models=Inv.H3_SET)],
        name="Grid CT T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:meter-electric-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="feed_in_T",
        addresses=[ModbusAddressesSpec(holding=[31028], models=Inv.H3_SET)],
        name="Feed-in T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:transmission-tower-import",
        scale=0.001,
        round_to=0.01,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="grid_consumption_T",
        addresses=[ModbusAddressesSpec(holding=[31028], models=Inv.H3_SET)],
        name="Grid Consumption T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:transmission-tower-export",
        scale=0.001,
        round_to=0.01,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="load_power_R",
        addresses=[ModbusAddressesSpec(holding=[31029], models=Inv.H3_SET)],
        name="Load Power R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:home-lightning-bolt-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="load_power_S",
        addresses=[ModbusAddressesSpec(holding=[31030], models=Inv.H3_SET)],
        name="Load Power S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:home-lightning-bolt-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="load_power_T",
        addresses=[ModbusAddressesSpec(holding=[31031], models=Inv.H3_SET)],
        name="Load Power T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        icon="mdi:home-lightning-bolt-outline",
        scale=0.001,
        round_to=0.01,
        validate=[Range(-100, 100)],
    )


def _inverter_entities() -> Iterable[EntityFactory]:
    def _invbatpower(addresses: list[ModbusAddressesSpec]) -> Iterable[ModbusSensorDescription]:
        yield ModbusSensorDescription(
            key="invbatpower",
            addresses=addresses,
            name="Inverter Battery Power",
            device_class=SensorDeviceClass.POWER,
            state_class=SensorStateClass.MEASUREMENT,
            native_unit_of_measurement="kW",
            scale=0.001,
            round_to=0.01,
            validate=[Range(-100, 100)],
        )
        yield ModbusSensorDescription(
            key="battery_discharge",
            addresses=addresses,
            name="Battery Discharge",
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
            key="battery_charge",
            addresses=addresses,
            name="Battery Charge",
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
        addresses=[
            ModbusAddressesSpec(input=[11008], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31022], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
            ModbusAddressesSpec(holding=[31039], models=Inv.H3_SET),
        ]
    )

    yield ModbusSensorDescription(
        key="rfreq",
        addresses=[
            ModbusAddressesSpec(input=[11014], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31009], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
            ModbusAddressesSpec(holding=[31015], models=Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[31013], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31018], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
            ModbusAddressesSpec(holding=[31032], models=Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[31019], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
    yield ModbusSensorDescription(
        key="batvolt",
        addresses=[
            ModbusAddressesSpec(input=[11034], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31034], models=Inv.H3_SET),
        ],
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        round_to=1,
        validate=[Min(0)],
    )
    yield ModbusSensorDescription(
        key="bat_current",
        addresses=[
            ModbusAddressesSpec(input=[11035], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31035], models=Inv.H3_SET),
        ],
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        round_to=1,
        validate=[Range(-100, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="battery_soc",
        addresses=[
            ModbusAddressesSpec(input=[11036], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31024], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
            ModbusAddressesSpec(holding=[31038], models=Inv.H3_SET),
        ],
        # TODO: There might be an equivalent register for the H3?
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="Battery SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        signed=False,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_kwh_remaining",
        addresses=[
            ModbusAddressesSpec(input=[11037], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS kWh Remaining",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.01,
        signed=False,
        validate=[Min(0)],
    )
    yield ModbusBatterySensorDescription(
        key="battery_temp",
        addresses=[
            ModbusAddressesSpec(input=[11038], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31023], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
            ModbusAddressesSpec(holding=[31037], models=Inv.H3_SET),
        ],
        # TODO: There might be an equivalent register for the H3
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="Battery Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_charge_rate",
        addresses=[
            ModbusAddressesSpec(input=[11041], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[31025], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
            ModbusAddressesSpec(holding=[31026], models=Inv.H1_G1 | Inv.H1_LAN | Inv.KH_119),
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
        key="bms_cell_temp_high",
        addresses=[
            ModbusAddressesSpec(input=[11043], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Cell Temp High",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_cell_temp_low",
        addresses=[
            ModbusAddressesSpec(input=[11044], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Cell Temp Low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_cell_mv_high",
        addresses=[
            ModbusAddressesSpec(input=[11045], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Cell mV High",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        signed=False,
        round_to=10,
        validate=[Min(0)],
    )
    yield ModbusBatterySensorDescription(
        key="bms_cell_mv_low",
        addresses=[
            ModbusAddressesSpec(input=[11046], models=Inv.H1_G1 | Inv.KH_PRE119),
        ],
        bms_connect_state_address=BMS_CONNECT_STATE_ADDRESS,
        name="BMS Cell mV Low",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        signed=False,
        validate=[Min(0)],
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
    yield ModbusFaultSensorDescription(
        key="inverter_fault_code",
        # We don't map Fault Code 3, as it's unused
        addresses=[
            # These addresses are correct for the KH, but the fault codes are not
            ModbusAddressesSpec(input=[11061, 11062, 11064, 11065, 11066, 11067, 11068], models=Inv.H1_G1),
            ModbusAddressesSpec(
                holding=[31031, 31032, 31034, 31035, 31036, 31037, 31038], models=Inv.H1_G1 | Inv.H1_LAN
            ),
            ModbusAddressesSpec(holding=[31044, 31045, 31047, 31048, 31049, 31050, 31051], models=Inv.H3_SET),
        ],
        name="Inverter Fault Code",
        icon="mdi:alert-circle-outline",
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
            ModbusAddressSpec(holding=31027, models=Inv.KH_119),
        ],
        name="Inverter State",
        states=KH_INVERTER_STATES,
    )
    yield ModbusSensorDescription(
        key="state_code",
        addresses=[
            ModbusAddressesSpec(holding=[31041], models=Inv.H3_SET),
        ],
        name="Inverter State Code",
        state_class=SensorStateClass.MEASUREMENT,
    )
    # There are 32xxx holding registers on the H1, but they're only accessible over RS485
    yield ModbusSensorDescription(
        key="solar_energy_total",
        addresses=[
            ModbusAddressesSpec(input=[11070, 11069], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32001, 32000], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Solar Generation Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:solar-power",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    )
    yield ModbusSensorDescription(
        key="solar_energy_today",
        addresses=[
            ModbusAddressesSpec(input=[11071], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32002], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Solar Generation Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:solar-power",
        scale=0.1,
        signed=False,
        validate=[Range(0, 1000)],
    )
    yield ModbusSensorDescription(
        key="battery_charge_total",
        addresses=[
            ModbusAddressesSpec(input=[11073, 11072], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32004, 32003], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Battery Charge Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-up-outline",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
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
    yield ModbusSensorDescription(
        key="battery_charge_today",
        addresses=[
            ModbusAddressesSpec(input=[11074], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32005], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Battery Charge Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-up-outline",
        scale=0.1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="battery_discharge_total",
        addresses=[
            ModbusAddressesSpec(input=[11076, 11075], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32007, 32006], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Battery Discharge Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-down-outline",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
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
    yield ModbusSensorDescription(
        key="battery_discharge_today",
        addresses=[
            ModbusAddressesSpec(input=[11077], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32008], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Battery Discharge Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:battery-arrow-down-outline",
        scale=0.1,
        validate=[Range(0, 100)],
    )
    yield ModbusSensorDescription(
        key="feed_in_energy_total",
        addresses=[
            ModbusAddressesSpec(input=[11079, 11078], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32010, 32009], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Feed-in Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower-import",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
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
    yield ModbusSensorDescription(
        key="feed_in_energy_today",
        addresses=[
            ModbusAddressesSpec(input=[11080], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32011], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Feed-in Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower-import",
        scale=0.1,
        validate=[Range(0, 1000)],
    )
    yield ModbusSensorDescription(
        key="grid_consumption_energy_total",
        addresses=[
            ModbusAddressesSpec(input=[11082, 11081], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32013, 32012], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Grid Consumption Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower-export",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
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
    yield ModbusSensorDescription(
        key="grid_consumption_energy_today",
        addresses=[
            ModbusAddressesSpec(input=[11083], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32014], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Grid Consumption Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower-export",
        scale=0.1,
        validate=[Range(0, 1000)],
    )
    yield ModbusSensorDescription(
        key="total_yield_total",
        addresses=[
            ModbusAddressesSpec(input=[11085, 11084], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32016, 32015], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Yield Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:export",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    )
    yield ModbusSensorDescription(
        key="total_yield_today",
        addresses=[
            ModbusAddressesSpec(input=[11086], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32017], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Yield Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:export",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-100, 100)],
    )
    yield ModbusSensorDescription(
        key="input_energy_total",
        addresses=[
            ModbusAddressesSpec(input=[11088, 11087], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32019, 32018], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Input Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:import",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    )
    yield ModbusSensorDescription(
        key="input_energy_today",
        addresses=[
            ModbusAddressesSpec(input=[11089], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32020], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Input Energy Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:import",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-1000, 1000)],
    )
    yield ModbusSensorDescription(
        key="load_power_total",
        addresses=[
            # TODO: There are registers for H1, but we currently use an integration
            # ModbusAddressesSpec(
            #     models=H1_SET, input=[11091, 11090]
            # ),
            ModbusAddressesSpec(input=[11091, 11090], models=Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32022, 32021], models=Inv.KH_119 | Inv.H3_SET),
        ],
        name="Load Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:home-lightning-bolt-outline",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
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
    yield ModbusSensorDescription(
        key="load_energy_today",
        addresses=[
            ModbusAddressesSpec(input=[11092], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[32023], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Load Energy Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        icon="mdi:home-lightning-bolt-outline",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-1000, 1000)],
    )


def _configuration_entities() -> Iterable[EntityFactory]:
    yield ModbusWorkModeSelectDescription(
        key="work_mode",
        address=[
            ModbusAddressSpec(input=41000, models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressSpec(holding=41000, models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
        ],
        name="Work Mode",
        options_map={0: "Self Use", 1: "Feed-in First", 2: "Back-up"},
    )
    # Sensors are a bit nicer to look at: keep for consistency with other numbers
    yield ModbusSensorDescription(
        key="max_charge_current",
        addresses=[
            ModbusAddressesSpec(input=[41007], models=Inv.H1_G1 | Inv.KH_PRE119),
            ModbusAddressesSpec(holding=[41007], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressSpec(holding=41007, models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[41008], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressSpec(holding=41008, models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[41009], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressSpec(holding=41009, models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[41010], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressSpec(holding=41010, models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressesSpec(holding=[41011], models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
            ModbusAddressSpec(holding=41011, models=Inv.H1_G1 | Inv.KH_119 | Inv.H3_SET),
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
        _configuration_entities(),
        (description for x in CHARGE_PERIODS for description in x.entity_descriptions),
        REMOTE_CONTROL_DESCRIPTION.entity_descriptions,
    )
)
