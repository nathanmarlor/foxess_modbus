"""Defines RegisterType"""
from enum import Enum


class RegisterType(Enum):
    """The different register types exposed by inverters"""

    INPUT = 1
    HOLDING = 2
