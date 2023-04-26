"""Modbus controller"""
import logging
import threading
from asyncio.exceptions import TimeoutError
from contextlib import contextmanager
from datetime import datetime
from datetime import timedelta
from typing import Iterable

from homeassistant.helpers.event import async_track_time_interval
from pymodbus.exceptions import ConnectionException
from pymodbus.exceptions import ModbusException

from .common.entity_controller import EntityController
from .common.entity_controller import ModbusControllerEntity
from .common.exceptions import UnsupportedInverterException
from .common.register_type import RegisterType
from .common.unload_controller import UnloadController
from .inverter_adapters import InverterAdapter
from .inverter_profiles import INVERTER_PROFILES
from .inverter_profiles import InverterModelConnectionTypeProfile
from .modbus_client import ModbusClient

_LOGGER = logging.getLogger(__name__)

# How many failed polls before we mark sensors as Unavailable
_NUM_FAILED_POLLS_FOR_DISCONNECTION = 5

_MODEL_START_ADDRESS = 30000
_MODEL_LENGTH = 15


@contextmanager
def _acquire_nonblocking(lock: threading.Lock) -> bool:
    locked = lock.acquire(False)
    try:
        yield locked
    finally:
        if locked:
            lock.release()


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
        self._update_listeners: set[ModbusControllerEntity] = set()
        self._data = {}
        self._client = client
        self._connection_type_profile = connection_type_profile
        self.charge_periods = connection_type_profile.create_charge_periods()
        self._slave = slave
        self._poll_rate = poll_rate
        self._max_read = max_read
        self._refresh_lock = threading.Lock()
        self._num_failed_poll_attempts = 0
        self._is_connected = True  # Start off assuming we can connect

        # Setup mixins
        EntityController.__init__(self)
        UnloadController.__init__(self)

        if self._hass is not None:
            refresh = async_track_time_interval(
                self._hass,
                self._refresh,
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
        _LOGGER.debug(
            "Writing registers for %s %s: (%s, %s)",
            self._client,
            self._slave,
            start_address,
            values,
        )
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

    async def _refresh(self, _time: datetime) -> None:
        """Refresh modbus data"""
        # Make sure that we don't do two refreshes at the same time, if one is too slow
        with _acquire_nonblocking(self._refresh_lock) as acquired:
            if not acquired:
                _LOGGER.warning(
                    "Aborting refresh of %s %s as a previous refresh is still in progress. Is your poll rate '%s' too high?",
                    self._client,
                    self._slave,
                    self._poll_rate,
                )
                return

            # List of (start address, [read values starting at that address])
            read_values: list[tuple[int, list[int]]] = []
            succeeded = False
            try:
                for (
                    start_address,
                    num_reads,
                ) in self._create_read_ranges(self._max_read):
                    _LOGGER.debug(
                        "Reading addresses on %s %s: (%s, %s)",
                        self._client,
                        self._slave,
                        start_address,
                        num_reads,
                    )
                    reads = await self._client.read_registers(
                        start_address,
                        num_reads,
                        self._connection_type_profile.register_type,
                        self._slave,
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

                _LOGGER.debug(
                    "Refresh of %s %s complete - notifying sensors: %s",
                    self._client,
                    self._slave,
                    changed_addresses,
                )
                self._notify_update(changed_addresses)
            except TimeoutError:
                _LOGGER.debug(
                    "Timed out when contacting device %s %s, cancelling poll loop",
                    self._client,
                    self._slave,
                )
            except ModbusException as ex:
                _LOGGER.debug(
                    "Modbus exception when polling %s %s - %s",
                    self._client,
                    self._slave,
                    ex,
                )
            except Exception as ex:
                _LOGGER.warning(
                    "General exception when polling %s %s - %s",
                    self._client,
                    self._slave,
                    repr(ex),
                    exc_info=True,
                )

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
                if (
                    self._num_failed_poll_attempts
                    >= _NUM_FAILED_POLLS_FOR_DISCONNECTION
                ):
                    _LOGGER.debug(
                        "%s failed poll attempts: now not connected",
                        self._num_failed_poll_attempts,
                    )
                    self._is_connected = False
                    self._notify_is_connected_changed()

    def _create_read_ranges(self, max_read: int) -> Iterable[tuple[int, int]]:
        """
        Generates a set of read ranges to cover the addresses of all registers on this inverter,
        respecting the maxumum number of registers to read at a time

        :returns: Sequence of tuples of (start_address, num_registers_to_read)
        """

        # The idea here is that read operations are expensive (there seems to be a large round-trip time at least
        # with the W610), but reading additional unneeded registers is relatively cheap (probably < 1ms).

        # To give some intuition, here are some examples of the groupings we want to achieve, assuming max_read = 5
        # 1,2 / 4,5 -> 1,2,3,4,5 (i.e. to read the registers 1, 2, 4 and 5, we'll do a single read spanning 1-5)
        # 1,2 / 5,6,7,8 -> 1,2 / 5,6,7,8
        # 1,2 / 5,6,7,8,9 -> 1,2 / 5,6,7,8,9
        # 1,2 / 5,6,7,8,9,10 -> 1,2,3,4,5 / 6,7,8,9,10
        # 1,2,3 / 5,6,7 / 9,10 -> 1,2,3,4,5 / 6,7,8,9,10

        # The problem as a whole looks like it's NP-hard (although I can't find a name for it).
        # We're therefore going to use a fairly simple algorithm which just makes each read as large as it can be.

        start_address: int | None = None
        read_size = 0
        # TODO: Do we want to cache the result of this?
        for address in sorted(self._data.keys()):
            if start_address is None:
                start_address, read_size = address, 1
            # If we're just increasing the previous read size by 1, then don't test whether we're extending
            # the read over an invalid range (as we assume that registers we're reading to read won't be
            # inside invalid ranges, tested in __init__). This also assumes that read_size != max_read here.
            elif address == start_address + 1 or (
                address <= start_address + max_read - 1
                and not self._connection_type_profile.overlaps_invalid_range(
                    start_address, address - 1
                )
            ):
                # There's a previous read which we can extend
                read_size = address - start_address + 1
            else:
                # There's a previous read, and we can't extend it to cover this address
                yield (start_address, read_size)
                start_address, read_size = address, 1

            if read_size == max_read:
                yield (start_address, read_size)
                start_address, read_size = None, 0

        if start_address is not None:
            yield (start_address, read_size)

    def register_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        self._update_listeners.add(listener)
        for address in listener.addresses:
            assert not self._connection_type_profile.overlaps_invalid_range(
                address, address
            )
            if address not in self._data:
                self._data[address] = None

    def remove_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        self._update_listeners.discard(listener)
        # If this was the only entity listening on this address, remove it from self._data
        other_addresses = set(
            address for entity in self._update_listeners for address in entity.addresses
        )
        for address in listener.addresses:
            if address not in other_addresses and address in self._data:
                del self._data[address]

    def _notify_update(self, changed_addresses: set[int]) -> None:
        """Notify listeners"""
        for listener in self._update_listeners:
            listener.update_callback(changed_addresses)

    def _notify_is_connected_changed(self) -> None:
        """Notify listeners that the availability states of the inverter changed"""
        for listener in self._update_listeners:
            listener.is_connected_changed_callback()

    @staticmethod
    async def autodetect(
        client: ModbusClient, slave: int, adapter: InverterAdapter
    ) -> tuple[str, str]:
        """
        Attempts to auto-detect the inverter type at the other end of the given connection

        :returns: Tuple of (inverter type name e.g. "H1", inverter full name e.g. "H1-3.7")
        """
        try:
            # All known inverter types expose the serial number at holding register 30000
            # The H1 series expose the holding registers over both LAN and AUX, and the H3
            # only expose holding.
            # Holding registers 30000-300015 seem to be all used for the model (with registers
            # after the model containing 32 (an ascii space) or 0, whereas input registers 10008 onwards
            # are for the serial number (and there doesn't seem to be enough space to hold all models!)
            result = []
            start_address = _MODEL_START_ADDRESS
            while len(result) < _MODEL_LENGTH:
                result.extend(
                    await client.read_registers(
                        start_address,
                        min(adapter.max_read, _MODEL_LENGTH - len(result)),
                        RegisterType.HOLDING,
                        slave,
                    )
                )
                start_address += adapter.max_read

            # Stop as soon as we find a space or something non-ASCII
            full_model = ""
            for char in result:
                if char > 0x20 and char < 0x7F:  # Exclude space (0x20)
                    full_model += chr(char)
                else:
                    break
            for model in INVERTER_PROFILES.values():
                if full_model.startswith(model.model):
                    _LOGGER.info(
                        "Autodetected inverter as %s (%s)", full_model, model.model
                    )
                    return model.model, full_model

            # We've read the model type, but been unable to match it against a supported model
            _LOGGER.warning("Did not recognise inverter model %s", full_model)
            raise UnsupportedInverterException(f"Inverter ({full_model}) not supported")
        except ModbusException:
            _LOGGER.warning("Failed to autodetect (%s)", client, exc_info=True)
        finally:
            await client.close()

        raise ConnectionException("Could not connect to Modbus device")
