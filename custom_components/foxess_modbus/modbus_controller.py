"""Modbus controller"""

import logging
import re
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from enum import Enum
from typing import Any
from typing import Iterable
from typing import Iterator

from homeassistant.components.logbook import async_log_entry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import issue_registry
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.issue_registry import IssueSeverity
from pymodbus.exceptions import ConnectionException

from .client.modbus_client import ModbusClient
from .client.modbus_client import ModbusClientFailedError
from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.exceptions import AutoconnectFailedError
from .common.exceptions import UnsupportedInverterError
from .common.types import RegisterPollType
from .common.types import RegisterType
from .common.unload_controller import UnloadController
from .const import DOMAIN
from .const import ENTITY_ID_PREFIX
from .const import FRIENDLY_NAME
from .const import INVERTER_MODEL
from .const import MAX_READ
from .inverter_profiles import INVERTER_PROFILES
from .inverter_profiles import InverterModelConnectionTypeProfile
from .remote_control_manager import RemoteControlManager

_LOGGER = logging.getLogger(__name__)

# How many failed polls before we mark sensors as Unavailable
_NUM_FAILED_POLLS_FOR_DISCONNECTION = 5

_MODEL_START_ADDRESS = 30000
_MODEL_LENGTH = 15

_INT16_MIN = -32768
_UINT16_MAX = 65535

_INVERTER_WRITE_DELAY_SECS = 5


@dataclass
class RegisterValue:
    poll_type: RegisterPollType
    read_value: int | None = None
    written_value: int | None = None
    written_at: float | None = None  # From time.monotonic()


class ConnectionState(Enum):
    INITIAL = 0
    DISCONNECTED = 1
    CONNECTED = 2


@contextmanager
def _acquire_nonblocking(lock: threading.Lock) -> Iterator[bool]:
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
        hass: HomeAssistant,
        client: ModbusClient,
        connection_type_profile: InverterModelConnectionTypeProfile,
        inverter_details: dict[str, Any],
        slave: int,
        poll_rate: int,
        max_read: int,
    ) -> None:
        """Init"""
        self._hass = hass
        self._update_listeners: set[ModbusControllerEntity] = set()
        self._data: dict[int, RegisterValue] = {}
        self._client = client
        self._connection_type_profile = connection_type_profile
        self._inverter_details = inverter_details
        self._slave = slave
        self._poll_rate = poll_rate
        self._max_read = max_read
        self._refresh_lock = threading.Lock()
        self._num_failed_poll_attempts = 0
        # To start, we're neither connected nor disconnected
        self._connection_state = ConnectionState.INITIAL
        self._current_connection_error: str | None = None
        self._inverter_capacity = connection_type_profile.inverter_model_profile.inverter_capacity(
            self.inverter_details[INVERTER_MODEL]
        )

        # Setup mixins
        EntityController.__init__(self)
        UnloadController.__init__(self)

        self.charge_periods = connection_type_profile.create_charge_periods(self)
        # This will call back into us to register its addresses
        remote_control_config = connection_type_profile.create_remote_control_config(self)
        self._remote_control_manager = (
            RemoteControlManager(self, remote_control_config, poll_rate) if remote_control_config is not None else None
        )

        if self._hass is not None:
            refresh = async_track_time_interval(
                self._hass,
                self._refresh,
                timedelta(seconds=self._poll_rate),
            )

            self._unload_listeners.append(refresh)

    @property
    def hass(self) -> HomeAssistant:
        return self._hass

    @property
    def is_connected(self) -> bool:
        # Only tell things we're not connected if we're actually disconnected
        return self._connection_state == ConnectionState.INITIAL or self._connection_state == ConnectionState.CONNECTED

    @property
    def current_connection_error(self) -> str | None:
        return self._current_connection_error

    @property
    def remote_control_manager(self) -> EntityRemoteControlManager | None:
        return self._remote_control_manager

    @property
    def inverter_capacity(self) -> int:
        return self._inverter_capacity

    @property
    def inverter_details(self) -> dict[str, Any]:
        return self._inverter_details

    def read(self, address: int, *, signed: bool) -> int | None:
        # There can be a delay between writing a register, and actually reading that value back (presumably the delay
        # is on the inverter somewhere). If we've recently written a value, use that value, rather than the latest-read
        # value
        register_value = self._data.get(address)
        if register_value is None:
            return None

        now = time.monotonic()
        value: int | None
        if (
            register_value.written_value is not None
            and register_value.written_at is not None
            and now - register_value.written_at < _INVERTER_WRITE_DELAY_SECS
        ):
            value = register_value.written_value
        else:
            value = register_value.read_value

        if signed and value is not None:
            sign_bit = 1 << (16 - 1)
            value = (value & (sign_bit - 1)) - (value & sign_bit)
        return value

    async def read_registers(self, start_address: int, num_registers: int, register_type: RegisterType) -> list[int]:
        """Read one of more registers, used by the read_registers_service"""
        return await self._client.read_registers(start_address, num_registers, register_type, self._slave)

    async def write_register(self, address: int, value: int) -> None:
        await self.write_registers(address, [value])

    async def write_registers(self, start_address: int, values: list[int]) -> None:
        """Write multiple registers"""
        _LOGGER.debug(
            "Writing registers for %s %s: (%s, %s)",
            self._client,
            self._slave,
            start_address,
            values,
        )
        try:
            for i, value in enumerate(values):
                value = int(value)  # Ensure that we've been given an int
                if not (_INT16_MIN <= value <= _UINT16_MAX):
                    raise ValueError(f"Value {value} must be between {_INT16_MIN} and {_UINT16_MAX}")
                # pymodbus doesn't like negative values
                if value < 0:
                    value = _UINT16_MAX + value + 1
                values[i] = value

            await self._client.write_registers(start_address, values, self._slave)

            changed_addresses = set()
            for i, value in enumerate(values):
                address = start_address + i
                # Only store the result of the write if it's a register we care about ourselves
                register_value = self._data.get(address)
                if register_value is not None:
                    register_value.written_value = value
                    register_value.written_at = time.monotonic()
                    changed_addresses.add(address)
            if len(changed_addresses) > 0:
                self._notify_update(changed_addresses)
        except Exception as ex:
            # Failed writes are always bad
            _LOGGER.error("Failed to write registers", exc_info=True)
            raise ex

    async def _refresh(self, _time: datetime) -> None:
        """Refresh modbus data"""
        # Make sure that we don't do two refreshes at the same time, if one is too slow
        with _acquire_nonblocking(self._refresh_lock) as acquired:
            if not acquired:
                _LOGGER.warning(
                    "Aborting refresh of %s %s as a previous refresh is still in progress. Is your poll rate '%s' too "
                    "high?",
                    self._client,
                    self._slave,
                    self._poll_rate,
                )
                return

            # List of (start address, [read values starting at that address])
            read_values: list[tuple[int, list[int]]] = []
            exception: Exception | None = None
            try:
                read_ranges = self._create_read_ranges(
                    self._max_read, is_initial_connection=self._connection_state != ConnectionState.CONNECTED
                )
                for start_address, num_reads in read_ranges:
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
                changed_addresses = set()
                for start_address, reads in read_values:
                    for i, value in enumerate(reads):
                        address = start_address + i
                        # We might be reading a register we don't care about (for efficiency). Discard it if so
                        register_value = self._data.get(address)
                        if register_value is not None:
                            register_value.read_value = value
                            changed_addresses.add(address)

                _LOGGER.debug(
                    "Refresh of %s %s complete - notifying sensors: %s",
                    self._client,
                    self._slave,
                    changed_addresses,
                )
                self._notify_update(changed_addresses)
            except ConnectionException as ex:
                exception = ex
                _LOGGER.debug(
                    "Failed to connect to %s %s: %s",
                    self._client,
                    self._slave,
                    ex,
                )
            except ModbusClientFailedError as ex:
                exception = ex
                _LOGGER.debug(
                    "Modbus error when polling %s %s: %s",
                    self._client,
                    self._slave,
                    ex.response,
                )
            except Exception as ex:
                exception = ex
                _LOGGER.warning(
                    "General exception when polling %s %s: %s",
                    self._client,
                    self._slave,
                    repr(ex),
                    exc_info=True,
                )

            # Do this after recording new values in _data. That way the sensors show the new values when they
            # become available after a disconnection
            if exception is None:
                self._num_failed_poll_attempts = 0
                if self._connection_state == ConnectionState.INITIAL:
                    self._connection_state = ConnectionState.CONNECTED
                elif self._connection_state == ConnectionState.DISCONNECTED:
                    _LOGGER.info(
                        "%s %s - poll succeeded: now connected",
                        self._client,
                        self._slave,
                    )
                    self._connection_state = ConnectionState.CONNECTED
                    self._current_connection_error = None
                    self._log_message("Connection restored")
                    issue_registry.async_delete_issue(
                        self._hass,
                        domain=DOMAIN,
                        issue_id=f"connection_error_{self.inverter_details[ENTITY_ID_PREFIX]}",
                    )
                    await self._notify_is_connected_changed(is_connected=True)
            elif self._connection_state != ConnectionState.DISCONNECTED:
                self._num_failed_poll_attempts += 1
                if self._num_failed_poll_attempts >= _NUM_FAILED_POLLS_FOR_DISCONNECTION:
                    _LOGGER.warning(
                        "%s %s - %s failed poll attempts: now not connected. Last error: %s",
                        self._client,
                        self._slave,
                        self._num_failed_poll_attempts,
                        exception,
                    )
                    self._connection_state = ConnectionState.DISCONNECTED
                    self._current_connection_error = str(exception)
                    self._log_message(f"Connection error: {exception}")
                    issue_registry.async_create_issue(
                        self._hass,
                        domain=DOMAIN,
                        issue_id=f"connection_error_{self.inverter_details[ENTITY_ID_PREFIX]}",
                        is_fixable=False,
                        is_persistent=False,
                        severity=IssueSeverity.ERROR,
                        translation_key="connection_error",
                        translation_placeholders={
                            "friendly_name": self.inverter_details[FRIENDLY_NAME],
                            "error": str(exception),
                        },
                    )
                    await self._notify_is_connected_changed(is_connected=False)

        if self._remote_control_manager is not None:
            await self._remote_control_manager.poll_complete_callback()

    def _log_message(self, message: str) -> None:
        friendly_name = self.inverter_details[FRIENDLY_NAME]
        if friendly_name:
            name = f"FoxESS - Modbus ({friendly_name})"
        else:
            name = "FoxESS - Modbus"
        async_log_entry(self._hass, name=name, message=message, domain=DOMAIN)

    def _create_read_ranges(self, max_read: int, is_initial_connection: bool) -> Iterable[tuple[int, int]]:
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
        for address, register_value in sorted(self._data.items()):
            if register_value.poll_type == RegisterPollType.ON_CONNECTION and not is_initial_connection:
                continue

            # This register must be read in a single individual read. Yield any ranges we've found so far,
            # and yield just this register on its own
            if self._connection_type_profile.is_individual_read(address):
                if start_address is not None:
                    yield (start_address, read_size)
                    start_address, read_size = None, 0
                yield (address, 1)
            elif start_address is None:
                start_address, read_size = address, 1
            # If we're just increasing the previous read size by 1, then don't test whether we're extending
            # the read over an invalid range (as we assume that registers we're reading to read won't be
            # inside invalid ranges, tested in __init__). This also assumes that read_size != max_read here.
            elif address == start_address + 1 or (
                address <= start_address + max_read - 1
                and not self._connection_type_profile.overlaps_invalid_range(start_address, address - 1)
            ):
                # There's a previous read which we can extend
                read_size = address - start_address + 1
            else:
                # There's a previous read, and we can't extend it to cover this address
                yield (start_address, read_size)
                start_address, read_size = address, 1

            if read_size == max_read:
                # (can't get here if start_address is None, as read_size would be 0
                yield (start_address, read_size)  # type: ignore
                start_address, read_size = None, 0

        if start_address is not None:
            yield (start_address, read_size)

    def register_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        self._update_listeners.add(listener)
        for address in listener.addresses:
            assert not self._connection_type_profile.overlaps_invalid_range(address, address), (
                f"Entity {listener} address {address} overlaps an invalid range in "
                f"{self._connection_type_profile.special_registers.invalid_register_ranges}"
            )
            if address not in self._data:
                self._data[address] = RegisterValue(poll_type=listener.register_poll_type)
            else:
                # We could handle this (removing gets harder), but it shouldn't happen in practice anyway
                assert self._data[address].poll_type == listener.register_poll_type

    def remove_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        self._update_listeners.discard(listener)
        # If this was the only entity listening on this address, remove it from self._data
        other_addresses = {address for entity in self._update_listeners for address in entity.addresses}
        for address in listener.addresses:
            if address not in other_addresses and address in self._data:
                del self._data[address]

    def _notify_update(self, changed_addresses: set[int]) -> None:
        """Notify listeners"""
        for listener in self._update_listeners:
            listener.update_callback(changed_addresses)

    async def _notify_is_connected_changed(self, is_connected: bool) -> None:
        """Notify listeners that the availability states of the inverter changed"""
        for listener in self._update_listeners:
            listener.is_connected_changed_callback()

        if is_connected and self._remote_control_manager is not None:
            await self._remote_control_manager.became_connected_callback()

    @staticmethod
    async def autodetect(client: ModbusClient, slave: int, adapter_config: dict[str, Any]) -> tuple[str, str]:
        """
        Attempts to auto-detect the inverter type at the other end of the given connection

        :returns: Tuple of (inverter type name e.g. "H1", inverter full name e.g. "H1-3.7-E")
        """
        # Annoyingly pymodbus logs the important stuff to its logger, and doesn't add that info to the exceptions it
        # throws
        spy_handler = _SpyHandler()
        pymodbus_logger = logging.getLogger("pymodbus")

        try:
            pymodbus_logger.addHandler(spy_handler)

            # All known inverter types expose the model number at holding register 30000 onwards.
            # (The H1 series additionally expose some model info in input registers))
            # Holding registers 30000-300015 seem to be all used for the model, with registers
            # after the model containing 32 (an ascii space) or 0. Input registers 10008 onwards
            # are for the serial number (and there doesn't seem to be enough space to hold all models!)
            # The H3 starts the model number with a space, annoyingly.
            # Some models (H1-5.0-E-G2 and H3-PRO) pack two ASCII chars into each register.
            register_values: list[int] = []
            start_address = _MODEL_START_ADDRESS
            while len(register_values) < _MODEL_LENGTH:
                register_values.extend(
                    await client.read_registers(
                        start_address,
                        min(adapter_config[MAX_READ], _MODEL_LENGTH - len(register_values)),
                        RegisterType.HOLDING,
                        slave,
                    )
                )
                start_address += adapter_config[MAX_READ]

            # If they've packed 2 ASCII chars into each register, unpack them
            if (register_values[0] & 0xFF00) != 0:
                model_chars = []
                # High byte, then low byte
                for register in register_values:
                    model_chars.append((register >> 8) & 0xFF)
                    model_chars.append(register & 0xFF)
            else:
                model_chars = register_values

            # Stop as soon as we find something non-printable-ASCII
            full_model = ""
            for char in model_chars:
                if 0x20 <= char < 0x7F:
                    full_model += chr(char)
                else:
                    break
            # Take off tailing spaces and H3's leading space
            full_model = full_model.strip()
            for model in INVERTER_PROFILES.values():
                if re.match(model.model_pattern, full_model):
                    # Make sure that we can parse the capacity out
                    capacity = model.inverter_capacity(full_model)
                    _LOGGER.info("Autodetected inverter as '%s' (%s, %sW)", model.model, full_model, capacity)
                    return model.model, full_model

            # We've read the model type, but been unable to match it against a supported model
            _LOGGER.error("Did not recognise inverter model '%s' (%s)", full_model, register_values)
            raise UnsupportedInverterError(full_model)
        except Exception as ex:
            _LOGGER.error("Autodetect: failed to connect to (%s)", client, exc_info=True)
            raise AutoconnectFailedError(spy_handler.records) from ex
        finally:
            pymodbus_logger.removeHandler(spy_handler)
            await client.close()


class _SpyHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__(level=logging.ERROR)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
