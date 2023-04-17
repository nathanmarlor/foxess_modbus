"""Modbus controller"""
import logging
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

# How many failed polls before we mark sensors as Unavailable
_NUM_FAILED_POLLS_FOR_DISCONNECTION = 5


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
        self._data = {x: None for x in connection_type_profile.all_addresses}
        self._client = client
        self.connection_type_profile = connection_type_profile
        self._slave = slave
        self._poll_rate = poll_rate
        self._max_read = max_read
        self._num_failed_poll_attempts = 0
        self._is_connected = True  # Start off assuming we can connect

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

    @property
    def is_connected(self) -> bool:
        return self._is_connected

    def read(self, address) -> bool:
        """Modbus status"""
        return self._data.get(address)

    async def write_register(self, address, value) -> None:
        await self.write_registers(address, [value])

    async def write_registers(self, start_address, values) -> None:
        """Write multiple registers"""
        await self._client.write_registers(start_address, values, self._slave)
        changed_addresses = set()
        for i, value in enumerate(values):
            address = start_address + i
            value = int(value)  # Ensure that we've been given an int
            # Only store the result of the write if it's a register we care about ourselves
            if self._data.get(address, value) != value:
                self._data[address] = value
                changed_addresses.add(address)
        self._notify_update(changed_addresses)

    async def refresh(self, *args) -> None:
        """Refresh modbus data"""
        holding = self.connection_type_profile.connection_type.read_holding_registers
        # List of (start address, [read values starting at that address])
        read_values: list[tuple[int, list[int]]] = []
        succeeded = False
        try:
            for (
                start_address,
                num_reads,
            ) in self.connection_type_profile.create_read_ranges(self._max_read):
                _LOGGER.debug(
                    "Reading addresses for (%s, %s)", start_address, num_reads
                )
                reads = await self._client.read_registers(
                    start_address, num_reads, holding, self._slave
                )
                read_values.append((start_address, reads))

            # If we made it to here, then all reads succeeded. Write them to _data and notify the sensors.
            # This avoids recording reads if poll failed partway through (ensuring that we don't record potentially
            # inconsistent data)
            succeeded = True
            changed_addresses = set()
            for start_address, reads in read_values:
                for i, value in enumerate(reads):
                    address = start_address + i
                    # We might be reading a register we don't care about (for efficiency). Discard it if so
                    if self._data.get(address, value) != value:
                        changed_addresses.add(address)
                        self._data[address] = value

            _LOGGER.debug("Refresh complete - notifying sensors: %s", changed_addresses)
            self._notify_update(changed_addresses)
        except TimeoutError:
            _LOGGER.debug("Timed out when contacting device, cancelling poll loop")
        except ModbusException as ex:
            _LOGGER.debug(f"Modbus exception when polling - {ex}")
        except Exception as ex:
            _LOGGER.warning(f"General exception when polling - {ex!r}")

        # Do this after recording new values in _data. That way the sensors show the new values when they
        # become available after a disconnection
        if succeeded:
            self._num_failed_poll_attempts = 0
            if not self._is_connected:
                _LOGGER.debug("Poll succeeded: now connected")
                self._is_connected = True
                self._notify_is_connected_changed()
        elif self._is_connected:
            self._num_failed_poll_attempts += 1
            if self._num_failed_poll_attempts >= _NUM_FAILED_POLLS_FOR_DISCONNECTION:
                _LOGGER.debug(
                    "%s failed poll attempts: now not connected",
                    self._num_failed_poll_attempts,
                )
                self._is_connected = False
                self._notify_is_connected_changed()

    @staticmethod
    async def autodetect(client: ModbusClient, slave: int) -> tuple[str, str, str]:
        """
        Attempts to auto-detect the inverter type at the other end of the given connection

        :returns: Tuple of (inverter type name e.g. "H1", inverter full name e.g. "H1-3.7", connection type e.g. "LAN")
        """
        for conn_type_name, conn_type in CONNECTION_TYPES.items():
            try:
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
