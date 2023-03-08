"""Modbus controller"""
import logging
from datetime import timedelta

from custom_components.foxess_modbus.const import AUX
from custom_components.foxess_modbus.const import H1
from custom_components.foxess_modbus.const import LAN
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .common.callback_controller import CallbackController
from .common.unload_controller import UnloadController
from .modbus_client import ModbusClient

_LOGGER = logging.getLogger(__name__)

_LAN_SN = 30000
_AUX_SN = 10000
# LAN uses holding registers / AUX uses input registers
_SERIALS = {AUX: (_AUX_SN, False), LAN: (_LAN_SN, True)}

# 5 seconds refresh with max read of 50
_LAN_POLL = (5, 50)
# 10 seconds refresh with max read of 10
_AUX_POLL = (10, 10)
_POLL_RATES = {LAN: _LAN_POLL, AUX: _AUX_POLL}

_ADDRESSES = {
    LAN: [
        (31000, 31025),
    ],
    AUX: [
        (11000, 11049),
        (41001, 41012),
    ],
}


class ModbusController(CallbackController, UnloadController):
    """Class to manage forecast retrieval"""

    def __init__(
        self,
        hass: HomeAssistant,
        modbus: ModbusClient,
        connection_type: str,
    ) -> None:
        """Init"""
        self._hass = hass
        self._modbus = modbus
        self._last_update = None
        self._connection_type = connection_type
        self._data = dict()

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

    def refresh(self, *args) -> None:
        """Refresh modbus data"""
        _, max_read = _POLL_RATES[self._connection_type]
        _, holding = _SERIALS[self._connection_type]
        try:
            for start, end in _ADDRESSES[self._connection_type]:
                _LOGGER.debug(f"Reading addresses for ({start}:{end-start})")
                for i in range(start, end, max_read):
                    data_per_read = min(max_read, end - i)
                    data = self._modbus.read_registers(i, data_per_read, holding)
                    for j, d in enumerate(data):
                        index = i + j
                        self._data[index] = d

            _LOGGER.debug("Refresh complete - notifying sensors")
            self._notify_listeners()
        except ConnectionError as ex:
            _LOGGER.debug(f"Exception when polling modbus - {ex}")

    async def autodetect(self) -> bool:
        """Modbus status"""
        for conn_type, (serial_addr, holding) in _SERIALS.items():
            try:
                result = self._modbus.read_registers(serial_addr, 2, holding)
                inverter_type = "".join([chr(i) for i in result])
                if inverter_type == H1:
                    _LOGGER.info(
                        f"Autodetected inverter as {inverter_type} using {conn_type} connection"
                    )
                    return True, inverter_type, conn_type
            except ConnectionError:
                continue
        return False, None, None

    def get_raw_value(self, address) -> bool:
        """Modbus status"""
        if address in self._data:
            return self._data[address]
        else:
            return None
