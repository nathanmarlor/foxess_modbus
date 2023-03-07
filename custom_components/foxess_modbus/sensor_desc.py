"""Custom sensor with optional properties"""
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntityDescription


@dataclass
class SensorDescription(SensorEntityDescription):
    """Custom sensor description"""

    address: int | None = 0
    should_poll: bool | None = False
    post_process: Callable[[int], int] | None = None
