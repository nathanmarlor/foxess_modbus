"""Validation"""
from abc import ABC
from abc import abstractmethod


class BaseValidator(ABC):
    """Base validator"""

    @abstractmethod
    def validate(self, data) -> bool:
        """Validate a value against a set of rules"""
