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


ENTITIES: list[EntityFactory] = [
    ModbusSensorDescription(
        key="pv1_voltage",
        addresses=[
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11000], holding=[31000])
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
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11001], holding=[31001])
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
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11002], holding=[31002])
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
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=[H1, AIO_H1],
            )
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
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11003], holding=[31003])
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
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11004], holding=[31004])
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
            ModbusAddressesSpec(models=[H1, AIO_H1], input=[11005], holding=[31005])
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
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=[H1, AIO_H1],
            )
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
    ModbusSensorDescription(
        key="invbatvolt",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11006])],
        name="Inverter Battery Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        # This can go negative if no battery is attached
    ),
    ModbusSensorDescription(
        key="invbatcurrent",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11007])],
        name="Inverter Battery Current",
        device_class=SensorDeviceClass.CURRENT,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="A",
        scale=0.1,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="invbatpower",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11008], holding=[31022]
            )
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
            )
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
            )
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
        key="rvolt",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11009], holding=[31006]
            )
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
            )
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
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11011])],
        name="Inverter Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-10000, 10000)],
    ),
    ModbusSensorDescription(
        key="rfreq",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11014], holding=[31009]
            )
        ],
        name="Inverter Frequency",
        device_class=SensorDeviceClass.FREQUENCY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="Hz",
        scale=0.01,
        validate=[Range(0, 60)],
    ),
    ModbusSensorDescription(
        key="eps_rvolt",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11015])],
        name="EPS Voltage",
        device_class=SensorDeviceClass.VOLTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="V",
        scale=0.1,
        validate=[Range(0, 300)],
    ),
    ModbusSensorDescription(
        key="grid_ct",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11021], holding=[31014]
            )
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
            )
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
            )
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
            )
        ],
        name="CT2 Meter",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusSensorDescription(
        key="load_power",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11023], holding=[31016]
            )
        ],
        name="Load Power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement="kW",
        scale=0.001,
        validate=[Range(-100, 100)],
    ),
    ModbusIntegrationSensorDescription(
        key="load_power_total",
        models=[
            EntitySpec(
                register_types=[RegisterType.INPUT, RegisterType.HOLDING],
                models=[H1, AIO_H1, AC1],
            )
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Load Power Total",
        round_digits=2,
        source_entity="load_power",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="invtemp",
        addresses=[
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11024], holding=[31018]
            )
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
            )
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
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11034], holding=[31020]
            )
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
            ModbusAddressesSpec(
                models=[H1, AIO_H1, AC1], input=[11035], holding=[31021]
            )
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
            )
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
            )
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
        name="BMS Watthours Total",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        scale=0.001,
        signed=False,
        entity_registry_enabled_default=False,
        validate=[Min(0)],
    ),
    ModbusSensorDescription(
        key="solar_energy_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11070, 11069])],
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
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11071])],
        name="Solar Generation Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="battery_charge_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11073, 11072])],
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
            EntitySpec(register_types=[RegisterType.HOLDING], models=[H1, AIO_H1, AC1])
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
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11074])],
        name="Battery Charge Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="battery_discharge_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11076, 11075])],
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
            EntitySpec(register_types=[RegisterType.HOLDING], models=[H1, AIO_H1, AC1])
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
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11077])],
        name="Battery Discharge Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="feed_in_energy_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11079, 11078])],
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
            EntitySpec(register_types=[RegisterType.HOLDING], models=[H1, AIO_H1, AC1])
        ],
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        integration_method="left",
        name="Feed-in Total",
        round_digits=2,
        source_entity="feed_in",
        unit_time=UnitOfTime.HOURS,
    ),
    ModbusSensorDescription(
        key="feed_in_energy_today",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11080])],
        name="Feed-in Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="grid_consumption_energy_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11082, 11081])],
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
            EntitySpec(register_types=[RegisterType.HOLDING], models=[H1, AIO_H1, AC1])
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
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11083])],
        name="Grid Consumption Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        validate=[Range(0, 100)],
    ),
    ModbusSensorDescription(
        key="total_yield_total",
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11085, 11084])],
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
        addresses=[ModbusAddressesSpec(models=[H1, AIO_H1, AC1], input=[11086])],
        name="Yield Today",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement="kWh",
        scale=0.1,
        # unsure if this actually goes negative
        validate=[Range(-100, 100)],
    ),
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
] + [description for x in CHARGE_PERIODS for description in x.entity_descriptions]
