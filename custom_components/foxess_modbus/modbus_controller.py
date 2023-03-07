"""Modbus controller"""
import logging
from datetime import datetime
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval

from .common.callback_controller import CallbackController
from .common.unload_controller import UnloadController
from .modbus_client import ModbusClient

_LOGGER = logging.getLogger(__name__)

_MAX_READ = 10
_DAY = 40002

_ADDRESSES = [
    {"id": "11000", "start": 11000, "end": 11049},
    {"id": "41000", "start": 41001, "end": 41012},
]


class ModbusController(CallbackController, UnloadController):
    """Class to manage forecast retrieval"""

    def __init__(self, hass: HomeAssistant, modbus: ModbusClient) -> None:
        """Init"""
        self._hass = hass
        self._modbus = modbus
        self._last_update = None
        self._data = dict()

        # Setup mixins
        CallbackController.__init__(self)
        UnloadController.__init__(self)

        if self._hass is not None:
            refresh = async_track_time_interval(
                self._hass,
                self.refresh,
                timedelta(seconds=10),
            )

            self._unload_listeners.append(refresh)

    def refresh(self, *args) -> None:
        """Refresh modbus data"""
        for addr in _ADDRESSES:
            _LOGGER.debug(f"Reading addresses for {addr['id']}")
            start = addr["start"]
            end = addr["end"]
            for i in range(start, end, _MAX_READ):
                data_per_read = min(_MAX_READ, end - i)
                data = self._modbus.read_input_registers(i, data_per_read)
                for j, d in enumerate(data):
                    index = i + j
                    self._data[index] = d

        self._notify_listeners()

    async def ready(self) -> bool:
        """Modbus status"""
        return self._modbus.read_input_registers(_DAY, 1)[0] == datetime.now().day

    def get_raw_value(self, address) -> bool:
        """Modbus status"""
        if address in self._data:
            return self._data[address]
        else:
            return None
