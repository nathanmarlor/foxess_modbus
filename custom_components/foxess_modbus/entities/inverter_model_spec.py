"""Holds a means of mapping different register addresses and types do different inverter models"""

from abc import ABC
from abc import abstractmethod

from ..common.types import Inv
from ..common.types import RegisterType


class InverterModelSpec(ABC):
    """Base class for specifications which describe which inverter models an entity supports"""

    @abstractmethod
    def addresses_for_inverter_model(self, *, register_type: RegisterType, models: Inv) -> list[int] | None:
        """
        If this spec supports the given inverter model (e.g. "H1") and register type (e.g. "holding"), return the list
        of addresses which it cares about (or an empty list if it dosen't rely on any addresses).

        If this spec does not support the given inverter model and register type, return None
        """


class ModbusAddressSpecBase(InverterModelSpec):
    """
    InverterModelSpec for entities which want to use a list of supported models, and a dict of
    {register type: [addresses]} for those models.

    Entities should normally use one of the other types, which are a bit neater to interface with.
    """

    def __init__(self, addresses: dict[RegisterType, list[int] | None], models: Inv) -> None:
        self._addresses = addresses
        self._models = models

    def addresses_for_inverter_model(self, *, register_type: RegisterType, models: Inv) -> list[int] | None:
        if models not in self._models:
            return None
        return self._addresses.get(register_type)


class ModbusAddressSpec(ModbusAddressSpecBase):
    """InverterModelSpec for entities which rely on a single modbus register"""

    def __init__(
        self,
        *,
        input: int | None = None,  # noqa: A002
        holding: int | None = None,
        models: Inv,
    ) -> None:
        addresses: dict[RegisterType, list[int] | None] = {}
        if input is not None:
            addresses[RegisterType.INPUT] = [input]
        if holding is not None:
            addresses[RegisterType.HOLDING] = [holding]
        super().__init__(addresses, models)


class ModbusAddressesSpec(ModbusAddressSpecBase):
    """InverterModelSpec for entities which rely on one or more modbus registers"""

    def __init__(
        self,
        *,
        input: list[int] | None = None,  # noqa: A002
        holding: list[int] | None = None,
        models: Inv,
    ) -> None:
        addresses: dict[RegisterType, list[int] | None] = {}
        if input is not None:
            addresses[RegisterType.INPUT] = input
        if holding is not None:
            addresses[RegisterType.HOLDING] = holding
        super().__init__(addresses, models)


class EntitySpec(InverterModelSpec):
    """InverterModelSpec for entities which don't rely on any addresses at all"""

    def __init__(self, register_types: list[RegisterType], models: Inv) -> None:
        self._register_types = register_types
        self._models = models

    def addresses_for_inverter_model(self, register_type: RegisterType, models: Inv) -> list[int] | None:
        return [] if register_type in self._register_types and models in self._models else None
