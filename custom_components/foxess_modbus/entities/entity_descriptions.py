from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number import NumberMode
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import UnitOfTime

from ..common.register_type import RegisterType
from ..const import AC1
from ..const import AIO_H1
from ..const import H1
from ..const import H3
from ..const import KH
from .charge_periods import CHARGE_PERIODS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import ModbusAddressesSpec
from .inverter_model_spec import ModbusAddressSpec
from .modbus_integration_sensor import (
    ModbusIntegrationSensorDescription,
)
from .modbus_number import ModbusNumberDescription
from .modbus_select import ModbusSelectDescription
from .modbus_sensor import ModbusSensorDescription
from .validation import Min
from .validation import Range


_PV_ENTITIES: list[EntityFactory] = [
    ModbusSensorDescription(
        key="pv1_voltage",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11000], holding=[31000]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31000]),
        ],
        name="PV1 Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        # This can go negative if no panels are attached
    ),
    ModbusSensorDescription(
        key="pv1_current",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11001], holding=[31001]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31001]),
        ],
        name="PV1 Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="pv1_power",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11002], holding=[31002]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31002]),
        ],
        name="PV1 Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        # This can go negative if no panels are attached
    ),
    ModbusIntegrationSensorDescription(
        key="pv1_energy_total",
        models=[
            EntitySpec(
                models=[H1, AIO_H1],
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
            ),
            EntitySpec(
                models=[KH, H3],
                register_types=[RegisterType.HOLDING],
            ),
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="PV1 Power Total",
        round_digits=2,
        source_entity="pv1_power",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="pv2_voltage",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11003], holding=[31003]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31003]),
        ],
        name="PV2 Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        # This can go negative if no panels are attached
    ),
    ModbusSensorDescription(
        key="pv2_current",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11004], holding=[31004]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31004]),
        ],
        name="PV2 Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="pv2_power",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11005], holding=[31005]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31005]),
        ],
        name="PV2 Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        # This can go negative if no panels are attached
    ),
    ModbusIntegrationSensorDescription(
        key="pv2_energy_total",
        models=[
            EntitySpec(
                models=[H1, AIO_H1],
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
            ),
            EntitySpec(
                models=[KH, H3],
                register_types=[RegisterType.HOLDING],
            ),
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="PV2 Power Total",
        round_digits=2,
        source_entity="pv2_power",
        unit_time=UnitOfTime.HOURS,
    ),
]

_H1_CURRENT_VOLTAGE_POWER_ENTITIES = [
    ModbusSensorDescription(
        key="invbatvolt",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11006], holding=[31020]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31020]),
        ],
        name="Inverter Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        # This can go negative if no battery is attached
    ),
    ModbusSensorDescription(
        key="invbatcurrent",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11007], holding=[31021]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31021]),
        ],
        name="Inverter Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="load_power",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11023], holding=[31016]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31016]),
        ],
        name="Load Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="rvolt",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11009], holding=[31006]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31006]),
        ],
        name="Inverter Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="rcurrent",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11010], holding=[31007]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31007]),
        ],
        name="Inverter Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="rpower",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11011], holding=[31008]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31008]),
        ],
        name="Inverter Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-10000, 10000)],
    ),
    ModbusSensorDescription(
        key="eps_rvolt",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11015], holding=[31010]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31010]),
        ],
        entity_registry_enabled_default=False,
        name="EPS Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="eps_rcurrent",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11016], holding=[31011]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31011]),
        ],
        entity_registry_enabled_default=False,
        name="EPS Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="eps_rpower",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11017], holding=[31012]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31012]),
        ],
        entity_registry_enabled_default=False,
        name="EPS Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-10000, 10000)],
    ),
    ModbusSensorDescription(
        key="grid_ct",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11021], holding=[31014]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31014]),
        ],
        name="Grid CT",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11021], holding=[31014]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31014]),
        ],
        name="Feed-in",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_consumption",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11021], holding=[31014]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31014]),
        ],
        name="Grid Consumption",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="ct2_meter",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11022], holding=[31015]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31015]),
        ],
        name="CT2 Meter",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
]

_H3_CURRENT_VOLTAGE_POWER_ENTITIES = [
    ModbusSensorDescription(
        key="grid_voltage_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31006])],
        name="Grid Voltage R",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="grid_voltage_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31007])],
        name="Grid Voltage S",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="grid_voltage_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31008])],
        name="Grid Voltage T",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="inv_current_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31009])],
        name="Inverter Current R",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="inv_current_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31010])],
        name="Inverter Current S",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="inv_current_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31011])],
        name="Inverter Current T",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="inv_power_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31012])],
        name="Inverter Power R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="inv_power_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31013])],
        name="Inverter Power S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="inv_power_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31014])],
        name="Inverter Power T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="eps_power_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31022])],
        entity_registry_enabled_default=False,
        name="EPS Power R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="eps_power_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31023])],
        entity_registry_enabled_default=False,
        name="EPS Power S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="eps_power_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31024])],
        entity_registry_enabled_default=False,
        name="EPS Power T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_ct_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31026])],
        name="Grid CT R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31026])],
        name="Feed-in R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_consumption_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31026])],
        name="Grid Consumption R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_ct_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31027])],
        name="Grid CT S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31027])],
        name="Feed-in S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_consumption_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31027])],
        name="Grid Consumption S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_ct_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31028])],
        name="Grid CT T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31028])],
        name="Feed-in T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_consumption_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31028])],
        name="Grid Consumption T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="load_power_R",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31029])],
        name="Load Power R",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="load_power_S",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31030])],
        name="Load Power S",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="load_power_T",
        addresses=[ModbusAddressesSpec(models=[H3], holding=[31031])],
        name="Load Power T",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(0, 100)],
    ),
]

_INVERTER_ENTITIES = [
    ModbusSensorDescription(
        key="invbatpower",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11008], holding=[31022]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31022]),
            ModbusAddressesSpec(models=[H3], holding=[31036]),
        ],
        name="Inverter Battery Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-10000, 10000)],
    ),
    ModbusSensorDescription(
        key="battery_discharge",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11008], holding=[31022]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31022]),
            ModbusAddressesSpec(models=[H3], holding=[31036]),
        ],
        name="Battery Discharge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: v if v > 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="battery_charge",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11008], holding=[31022]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31022]),
            ModbusAddressesSpec(models=[H3], holding=[31036]),
        ],
        name="Battery Charge",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        post_process=lambda v: abs(v) if v < 0 else 0,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="rfreq",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11014], holding=[31009]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31009]),
            ModbusAddressesSpec(models=[H3], holding=[31015]),
        ],
        name="Inverter Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
        validate=[Range(0, 60)],
    ),
    ModbusSensorDescription(
        key="eps_frequency",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11020], holding=[31013]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31013]),
            ModbusAddressesSpec(models=[H3], holding=[31025]),
        ],
        entity_registry_enabled_default=False,
        name="EPS Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
        validate=[Range(0, 60)],
    ),
    ModbusSensorDescription(
        key="invtemp",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11024], holding=[31018]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31018]),
            ModbusAddressesSpec(models=[H3], holding=[31032]),
        ],
        name="Inverter Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="ambtemp",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11025], holding=[31019]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31019]),
            ModbusAddressesSpec(models=[H3], holding=[31033]),
        ],
        name="Ambient Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="batvolt",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11034]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31034]),
        ],
        name="Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="bat_current",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11035]),
            ModbusAddressesSpec(models=[KH, H3], holding=[31035]),
        ],
        name="Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="battery_soc",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11036], holding=[31024]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31024]),
            ModbusAddressesSpec(models=[H3], holding=[31038]),
        ],
        name="Battery SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="bms_kwh_remaining",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11037])],
        name="BMS kWh Remaining",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.01,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="battery_temp",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11038], holding=[31023]
            ),
            ModbusAddressesSpec(models=[KH], holding=[31023]),
            ModbusAddressesSpec(models=[H3], holding=[31037]),
        ],
        name="Battery Temp",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="bms_charge_rate",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11041])],
        name="BMS Charge Rate",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="bms_discharge_rate",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11042])],
        name="BMS Discharge Rate",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="bms_cell_temp_high",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11043])],
        name="BMS Cell Temp High",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="bms_cell_temp_low",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11044])],
        name="BMS Cell Temp Low",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="°C",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="bms_cell_mv_high",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11045])],
        name="BMS Cell mV High",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="bms_cell_mv_low",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11046])],
        name="BMS Cell mV Low",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="mV",
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="bms_cycle_count",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11048])],
        name="BMS Cycle Count",
        state_class=SensorStateClass.MEASUREMENT,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="bms_watthours_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11049])],
        entity_registry_enabled_default=False,
        name="BMS Watthours Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    # There are 32xxx holding registers on the H1, but they're only accessible over RS485
    ModbusSensorDescription(
        key="solar_energy_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11070, 11069]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32001, 32000]),
        ],
        name="Solar Generation Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="solar_energy_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11071]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32002]),
        ],
        name="Solar Generation Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="battery_charge_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11073, 11072]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32004, 32003]),
        ],
        name="Battery Charge Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusIntegrationSensorDescription(
        key="battery_charge_total",
        models=[
            EntitySpec(models=[H1, AIO_H1, AC1], register_types=[RegisterType.HOLDING])
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Battery Charge Total",
        round_digits=2,
        source_entity="battery_charge",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="battery_charge_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11074]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32005]),
        ],
        name="Battery Charge Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="battery_discharge_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11076, 11075]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32007, 32006]),
        ],
        name="Battery Discharge Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusIntegrationSensorDescription(
        key="battery_discharge_total",
        models=[
            EntitySpec(models=[H1, AIO_H1, AC1], register_types=[RegisterType.HOLDING])
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Battery Discharge Total",
        round_digits=2,
        source_entity="battery_discharge",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="battery_discharge_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11077]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32008]),
        ],
        name="Battery Discharge Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in_energy_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11079, 11078]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32010, 32009]),
        ],
        name="Feed-in Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusIntegrationSensorDescription(
        key="feed_in_energy_total",
        models=[
            EntitySpec(models=[H1, AIO_H1, AC1], register_types=[RegisterType.HOLDING]),
        ],
        name="Feed-in Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        round_digits=2,
        source_entity="feed_in",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="feed_in_energy_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11080]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32011]),
        ],
        name="Feed-in Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_consumption_energy_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11082, 11081]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32013, 32012]),
        ],
        name="Grid Consumption Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusIntegrationSensorDescription(
        key="grid_consumption_energy_total",
        models=[
            EntitySpec(models=[H1, AIO_H1, AC1], register_types=[RegisterType.HOLDING])
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Grid Consumption Total",
        round_digits=2,
        source_entity="grid_consumption",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="grid_consumption_energy_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11083]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32014]),
        ],
        name="Grid Consumption Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="total_yield_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11085, 11084]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32016, 32015]),
        ],
        name="Yield Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="total_yield_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11086]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32017]),
        ],
        name="Yield Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="input_energy_total",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11088, 11087]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32019, 32018]),
        ],
        name="Input Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="input_energy_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11089]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32020]),
        ],
        name="Input Energy Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="load_power_total",
        addresses=[
            # TODO: There are registers for H1, but we currently use an integration
            # ModbusAddressesSpec(
            #     models=[H1, AIO_H1, AC1], input=[11091, 11090]
            # ),
            ModbusAddressesSpec(models=[KH, H3], holding=[32022, 32021]),
        ],
        name="Load Energy Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.1,
        signed=False,
        validate=[Min(0)],
    ),
    ModbusIntegrationSensorDescription(
        key="load_power_total",
        models=[
            EntitySpec(
                models=[H1, AIO_H1, AC1],
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
            )
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Load Energy Total",
        round_digits=2,
        source_entity="load_power",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="load_energy_today",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11092]),
            ModbusAddressesSpec(models=[KH, H3], holding=[32023]),
        ],
        name="Load Energy Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="state_code",
        addresses=[ModbusAddressesSpec(models=[KH, H3], holding=[31041])],
        name="Inverter State Code",
        state_class=SensorStateClass.MEASUREMENT,
    ),
    # We'll re-introduce these as a single sensor showing the current fault code(s)
    # ModbusSensorDescription(
    #     key="fault1_code",
    #     addresses=[ModbusAddressesSpec(models=[H3], holding=[31044])],
    #     name="Inverter Fault 1 Code",
    #     state_class=SensorStateClass.MEASUREMENT,
    # ),
    # ModbusSensorDescription(
    #     key="fault2_code",
    #     addresses=[ModbusAddressesSpec(models=[H3], holding=[31045])],
    #     name="Inverter Fault 2 Code",
    #     state_class=SensorStateClass.MEASUREMENT,
    # ),
    # ModbusSensorDescription(
    #     key="fault3_code",
    #     addresses=[ModbusAddressesSpec(models=[H3], holding=[31046])],
    #     name="Inverter Fault 3 Code",
    #     state_class=SensorStateClass.MEASUREMENT,
    # ),
]

_CONFIGURATION_ENTITIES: list[EntityFactory] = [
    ModbusSelectDescription(
        key="work_mode",
        address=[ModbusAddressSpec(models=[H1, AIO_H1, AC1], input=41000)],
        name="Work Mode",
        options_map={0: "Self Use", 1: "Feed-in First", 2: "Back-up"},
    ),
    # Sensor kept for back compat
    ModbusSensorDescription(
        key="min_soc",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[41009])],
        name="Min SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        validate=[Range(0, 100)],
    ),
    ModbusNumberDescription(
        key="min_soc",
        address=[ModbusAddressSpec(models=[H1, AIO_H1, AC1], input=41009)],
        name="Min SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-down",
        validate=[Range(0, 100)],
    ),
    # Sensor kept for back compat
    ModbusSensorDescription(
        key="max_soc",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[41010])],
        name="Max SoC",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        validate=[Range(0, 100)],
    ),
    ModbusNumberDescription(
        key="max_soc",
        address=[ModbusAddressSpec(models=[H1, AIO_H1, AC1], input=41010)],
        name="Max SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-up",
        validate=[Range(0, 100)],
    ),
    # Sensor kept for back compat
    ModbusSensorDescription(
        key="min_soc_on_grid",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[41011])],
        name="Min SoC (On Grid)",
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="%",
        validate=[Range(0, 100)],
    ),
    ModbusNumberDescription(
        key="min_soc_on_grid",
        address=[ModbusAddressSpec(models=[H1, AIO_H1, AC1], input=41011)],
        name="Min SoC (On Grid)",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-down",
        validate=[Range(0, 100)],
    ),
]

ENTITIES = (
    _PV_ENTITIES
    + _H1_CURRENT_VOLTAGE_POWER_ENTITIES
    + _H3_CURRENT_VOLTAGE_POWER_ENTITIES
    + _INVERTER_ENTITIES
    + _CONFIGURATION_ENTITIES
    + [description for x in CHARGE_PERIODS for description in x.entity_descriptions]
)
