"""Validation"""
from .base_validator import BaseValidator
from .modbus_charge_period_sensors import is_time_value_valid


class Range(BaseValidator):
    """Range validator"""

    def __init__(self, min_value: float, max_value: float) -> None:
        """Init"""
        self._min = min_value
        self._max = max_value

    def validate(self, data: int | float) -> bool:
        """Validate a value against a set of rules"""

        return self._min <= data <= self._max


class Min(BaseValidator):
    """Min validator"""

    def __init__(self, min_value: float) -> None:
        """Init"""
        self._min = min_value

    def validate(self, data: int | float) -> bool:
        """Validate a value against a set of rules"""

        return data >= self._min


class Max(BaseValidator):
    """Max validator"""

    def __init__(self, max_value: float) -> None:
        """Init"""
        self._max = max_value

    def validate(self, data: int | float) -> bool:
        """Validate a value against a set of rules"""

        return data <= self._max


class Time(BaseValidator):
    """Time validator"""

    def validate(self, data: int | float) -> bool:
        """Validate a value against a set of rules"""
        return isinstance(data, int) and is_time_value_valid(data)
