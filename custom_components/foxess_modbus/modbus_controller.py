"""Modbus controller"""
import logging
import queue
from asyncio.exceptions import TimeoutError
from datetime import timedelta

from custom_components.foxess_modbus.const import AUTODETECT
from custom_components.foxess_modbus.const import AUX
from custom_components.foxess_modbus.const import LAN
from homeassistant.helpers.event import async_track_time_interval
from pymodbus.exceptions import ModbusException

from .common.callback_controller import CallbackController
from .common.unload_controller import UnloadController

_LOGGER = logging.getLogger(__name__)

_SERIALS = {AUX: 10000, LAN: 30000}
# LAN uses holding registers / AUX uses input registers
_HOLDING = {AUX: False, LAN: True}

_ADDRESSES = {
    LAN: [
        (31000, 31025),
    ],
    AUX: [
        (11000, 11050),
        (41000, 41012),
    ],
}


class ModbusController(CallbackController, UnloadController):
    """Class to manage forecast retrieval"""

    def __init__(
        self, hass, client, connection_type, slave, poll_rate, max_read
    ) -> None:
        """Init"""
        self._hass = hass
        self._data = dict()
        self._client = client
        self._connection_type = connection_type
        self._slave = slave
        self._poll_rate = poll_rate
        self._max_read = max_read
        self._write_queue = queue.Queue()

        # Setup mixins
        CallbackController.__init__(self)
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
        holding = _HOLDING[self._connection_type]
        try:
            changed_addresses = set()
            for start, end in _ADDRESSES[self._connection_type]:
                _LOGGER.debug(f"Reading addresses for ({start}:{end-start})")
                for i in range(start, end, self._max_read):
                    data_per_read = min(self._max_read, end - i)
                    data = await self._client.read_registers(
                        i, data_per_read, holding, self._slave
                    )
                    for j, d in enumerate(data):
                        address = i + j
                        if self._data.get(address) != d:
                            changed_addresses.add(address)
                            self._data[address] = d

            _LOGGER.debug("Refresh complete - notifying sensors: %s", changed_addresses)
            self._notify_listeners(changed_addresses)
        except TimeoutError:
            _LOGGER.debug("Timed out when contacting device, cancelling poll loop")
        except ModbusException as ex:
            _LOGGER.debug(f"Modbus exception when polling - {ex}")
        except Exception as ex:
            _LOGGER.debug(f"General exception when polling - {ex!r}")

    async def autodetect(self) -> bool:
        """Modbus status"""
        for conn_type, serial_addr in _SERIALS.items():
            holding = _HOLDING[conn_type]
            try:
                result = await self._client.read_registers(
                    serial_addr, 10, holding, self._slave
                )
                for model in AUTODETECT:
                    inverter_str = "".join([chr(i) for i in result])
                    base_model = inverter_str[: len(model)]
                    if base_model == model:
                        full_model = inverter_str[: len(model) + 4]
                        _LOGGER.info(
                            f"Autodetected inverter as {full_model} using {conn_type} connection"
                        )
                        return base_model, full_model, conn_type

                raise ConnectionRefusedError(f"{inverter_str} not supported")
            finally:
                await self._client.close()
