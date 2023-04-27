""""Unsupported inverter exception"""


class UnsupportedInverterException(Exception):
    """ "Unsupported inverter exception"""

    def __init__(self, full_model: str) -> None:
        self.full_model = full_model

    def __str__(self) -> str:
        """String representation"""
        return f"Inverter model not supported: '{self.full_model}'"
