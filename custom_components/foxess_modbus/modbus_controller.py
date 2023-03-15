"""Modbus controller"""
import logging
import queue
from asyncio.exceptions import TimeoutError
from datetime import timedelta

from custom_components.foxess_modbus.const import AUX
from custom_components.foxess_modbus.const import H1
from custom_components.foxess_modbus.const import LAN
from homeassistant.helpers.event import async_track_time_interval
from pymodbus.exceptions import ModbusException

from .common.callback_controller import CallbackController
from .common.unload_controller import UnloadController

_LOGGER = logging.getLogger(__name__)

_SERIALS = {AUX: 10000, LAN: 30000}
# LAN uses holding registers / AUX uses input registers
_HOLDING = {AUX: False, LAN: True}

# 5 seconds refresh with max read of 50
_LAN_POLL = (5, 50)
# 10 seconds refresh with max read of 8
_AUX_POLL = (10, 8)
_POLL_RATES = {LAN: _LAN_POLL, AUX: _AUX_POLL}

_ADDRESSES = {
    LAN: [
        (31000, 31025),
    ],
    AUX: [
        (11000, 11050),
        (41001, 41012),
    ],
}


class ModbusController(CallbackController, UnloadController):
    """Class to manage forecast retrieval"""

    def __init__(self, hass, client, connection_type, slave) -> None:
        """Init"""
        self._hass = hass
        self._data = dict()
        self._client = client
        self._connection_type = connection_type
        self._slave = slave
        self._write_queue = queue.Queue()

        # Setup mixins
        CallbackController.__init__(self)
        UnloadController.__init__(self)

        if self._hass is not None:
            poll_rate, _ = _POLL_RATES[connection_type]
            refresh = async_track_time_interval(
                self._hass,
                self.refresh,
                timedelta(seconds=poll_rate),
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
            await self._client.write_registers(start_address, values, self._slave)
        else:
            _LOGGER.warning("Modbus write service called with incorrect data format")

    async def refresh(self, *args) -> None:
        """Refresh modbus data"""
        _, max_read = _POLL_RATES[self._connection_type]
        holding = _HOLDING[self._connection_type]
        try:
            for start, end in _ADDRESSES[self._connection_type]:
                _LOGGER.debug(f"Reading addresses for ({start}:{end-start})")
                for i in range(start, end, max_read):
                    data_per_read = min(max_read, end - i)
                    data = await self._client.read_registers(
                        i, data_per_read, holding, self._slave
                    )
                    for j, d in enumerate(data):
                        index = i + j
                        self._data[index] = d

            _LOGGER.debug("Refresh complete - notifying sensors")
            self._notify_listeners()
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
                    serial_addr, 2, holding, self._slave
                )
                inverter_type = "".join([chr(i) for i in result])
                if inverter_type == H1:
                    _LOGGER.info(
                        f"Autodetected inverter as {inverter_type} using {conn_type} connection"
                    )
                    return inverter_type, conn_type
                else:
                    raise ConnectionRefusedError(f"{inverter_type} not supported")
            finally:
                await self._client.close()
