"""Modbus controller"""
import logging
import queue
from asyncio.exceptions import TimeoutError
from datetime import timedelta

from homeassistant.helpers.event import async_track_time_interval
from pymodbus.exceptions import ConnectionException
from pymodbus.exceptions import ModbusException

from .common.entity_controller import EntityController
from .common.exceptions import UnsupportedInverterException
from .common.unload_controller import UnloadController
from .inverter_profiles import CONNECTION_TYPES
from .inverter_profiles import INVERTER_PROFILES
from .inverter_profiles import InverterModelConnectionTypeProfile
from .modbus_client import ModbusClient

_LOGGER = logging.getLogger(__name__)


class ModbusController(EntityController, UnloadController):
    """Class to manage forecast retrieval"""

    def __init__(
        self,
        hass,
        client: ModbusClient,
        connection_type_profile: InverterModelConnectionTypeProfile,
        slave: int,
        poll_rate: int,
        max_read: int,
    ) -> None:
        """Init"""
        self._hass = hass
        self._data = dict()
        self._client = client
        self._connection_type_profile = connection_type_profile
        self._slave = slave
        self._poll_rate = poll_rate
        self._max_read = max_read
        self._write_queue = queue.Queue()

        # Setup mixins
        EntityController.__init__(self)
        UnloadController.__init__(self)

        if self._hass is not None:
            refresh = async_track_time_interval(
                self._hass,
                self.refresh,
                timedelta(seconds=self._poll_rate),
            )

            self._unload_listeners.append(refresh)

    def read(self, address) -> bool:
        """Modbus status"""
        if address in self._data:
            return self._data[address]
        else:
            return None

    async def write(self, service) -> bool:
        """Modbus write"""
        if {"start_address", "values"} <= set(service.data):
            start_address = service.data["start_address"]
            values = service.data["values"].split(",")
            await self._write_registers(start_address, values)
        else:
            _LOGGER.warning("Modbus write service called with incorrect data format")

    async def write_register(self, address, value) -> None:
        await self._write_registers(address, [value])

    async def _write_registers(self, start_address, values) -> None:
        await self._client.write_registers(start_address, values, self._slave)
        changed_addresses = set()
        for i, value in enumerate(values):
            address = start_address + i
            if self._data.get(address, value) != value:
                self._data[address] = value
                changed_addresses.add(address)
        self._notify_listeners(changed_addresses)

    async def refresh(self, *args) -> None:
        """Refresh modbus data"""
        holding = self._connection_type_profile.connection_type.read_holding_registers
        try:
            changed_addresses = set()
            for (
                start_address,
                num_reads,
            ) in self._connection_type_profile.create_read_ranges(self._max_read):
                _LOGGER.debug(
                    "Reading addresses for (%s, %s)", start_address, num_reads
                )
                reads = await self._client.read_registers(
                    start_address, num_reads, holding, self._slave
                )
                for i, value in enumerate(reads):
                    address = start_address + i
                    if self._data.get(address) != value:
                        changed_addresses.add(address)
                        self._data[address] = value

            _LOGGER.debug("Refresh complete - notifying sensors: %s", changed_addresses)
            self._notify_listeners(changed_addresses)
        except TimeoutError:
            _LOGGER.debug("Timed out when contacting device, cancelling poll loop")
        except ModbusException as ex:
            _LOGGER.debug(f"Modbus exception when polling - {ex}")
        except Exception as ex:
            _LOGGER.debug(f"General exception when polling - {ex!r}")

    @staticmethod
    async def autodetect(client: ModbusClient, slave: int) -> tuple[str, str, str]:
        """
        Attempts to auto-detect the inverter type at the other end of the given connection

        :returns: Tuple of (inverter type name e.g. "H1", inverter full name e.g. "H1-3.7", connection type e.g. "LAN")
        """
        for conn_type_name, conn_type in CONNECTION_TYPES.items():
            try:
                await client.connect()
                result = await client.read_registers(
                    conn_type.serial_start_address,
                    10,
                    conn_type.read_holding_registers,
                    slave,
                )
                inverter_str = "".join([chr(i) for i in result])
                for model_key, model in INVERTER_PROFILES.items():
                    if conn_type_name in model.connection_types:
                        base_model = inverter_str[: len(model.model)]
                        if base_model == model.model:
                            full_model = inverter_str[: len(model.model) + 4]
                            _LOGGER.info(
                                "Autodetected inverter as %s using %s connection",
                                full_model,
                                conn_type_name,
                            )
                            return model_key, full_model, conn_type_name
                # here we've read the model type, but been unable to match it against a supported model
                raise UnsupportedInverterException(
                    f"Inverter ({inverter_str}) not supported"
                )
            except ModbusException:
                _LOGGER.warning("Failed to autodetect (%s)", conn_type_name)
                continue
            finally:
                await client.close()

        raise ConnectionException("Could not connect to Modbus device")
