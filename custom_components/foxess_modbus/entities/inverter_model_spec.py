from abc import ABC
from abc import abstractmethod

from ..const import AUX
from ..const import LAN


class InverterModelSpec(ABC):
    """Base class for specifications which describe which inverter models an entity supports"""

    @abstractmethod
    def addresses_for_inverter_model(
        self, inverter_model: str, connection_type: str
    ) -> list[int] | None:
        """
        If this spec supports the given inverter model (e.g. "H1") and connection type (e.g. "LAN"), return the list
        of addresses which it cares about (or an empty list if it dosen't rely on any addresses).

        If this spec does not support the given inverter model and connection type, return None
        """


class ModbusAddressSpecBase(InverterModelSpec):
    """
    InverterModelSpec for entities which want to use a list of supported models, and a dict of {connection type: [addresses]} for those models.

    Entities should normally use one of the other types, which are a bit neater to interface with.
    """

    def __init__(self, models: list[str], addresses: dict[str, list[int]]) -> None:
        self._models = models
        self._addresses = addresses

    def addresses_for_inverter_model(
        self, inverter_model: str, connection_type: str
    ) -> list[int] | None:
        if inverter_model not in self._models:
            return None
        return self._addresses.get(connection_type)


class ModbusAddressSpec(ModbusAddressSpecBase):
    """InverterModelSpec for entities which rely on a single modbus register"""

    def __init__(
        self, models: list[str], aux: int | None = None, lan: int | None = None
    ) -> None:
        addresses = {}
        if aux is not None:
            addresses[AUX] = [aux]
        if lan is not None:
            addresses[LAN] = [lan]
        super().__init__(models, addresses)


class ModbusAddressesSpec(ModbusAddressSpecBase):
    """InverterModelSpec for entities which rely on one or more modbus registers"""

    def __init__(
        self,
        models: list[str],
        lan: list[int] | None = None,
        aux: list[int] | None = None,
    ) -> None:
        addresses = {}
        if aux is not None:
            addresses[AUX] = aux
        if lan is not None:
            addresses[LAN] = lan
        super().__init__(models, addresses)


class EntitySpec(InverterModelSpec):
    """InverterModelSpec for entities which don't rely on any addresses at all"""

    def __init__(self, connection_types: list[str], models: list[str]) -> None:
        self._connection_types = connection_types
        self._models = models

    def addresses_for_inverter_model(
        self, inverter_model: str, connection_type: str
    ) -> list[int] | None:
        return (
            []
            if connection_type in self._connection_types
            and inverter_model in self._models
            else None
        )
