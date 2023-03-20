""""Unsupported inverter exception"""


class UnsupportedInverterException(Exception):
    """ "Unsupported inverter exception"""

    def __init__(self, message) -> None:
        self.message = message
        super().__init__(self.message)

    def __str__(self) -> str:
        """String representation"""
        return f"{self.message}"
