from enum import IntEnum


class RegisterPollType(IntEnum):
    """Describs when a register should be polled"""

    # These must be ordered from least frequent to most frequent
    ON_CONNECTION = 0
    PERIODICALLY = 1
