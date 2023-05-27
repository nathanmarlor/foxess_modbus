""""Unsupported inverter exception"""
import logging


class UnsupportedInverterError(Exception):
    """Unsupported inverter exception"""

    def __init__(self, full_model: str) -> None:
        self.full_model = full_model

    def __str__(self) -> str:
        """String representation"""
        return f"Inverter model not supported: '{self.full_model}'"


class AutoconnectFailedError(Exception):
    """Raised when we fail to auto-connect to an inverter during setup"""

    def __init__(self, log_records: list[logging.LogRecord]) -> None:
        self.log_records = log_records
