"""Mixin providing common functionality for all entity classes"""

import logging
from typing import TYPE_CHECKING
from typing import Any
from typing import Protocol
from typing import cast

from homeassistant.const import Platform
from homeassistant.util import slugify
from homeassistant.helpers import entity_registry
from homeassistant.helpers.entity import ABCCachedProperties
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity import Entity
from propcache import cached_property

from ..common.entity_controller import EntityController
from ..common.entity_controller import ModbusControllerEntity
from ..const import DOMAIN
from ..const import ENTITY_ID_PREFIX
from ..const import FRIENDLY_NAME
from ..const import INVERTER_CONN
from ..const import INVERTER_MODEL
from ..const import UNIQUE_ID_PREFIX
from .base_validator import BaseValidator

_LOGGER = logging.getLogger(__name__)


def get_entity_id(controller: EntityController, platform: Platform, key: str) -> str:
    """Gets the entity ID for the entity with the given platform and key"""

    unique_id = _create_unique_id(key, controller.inverter_details)

    er = entity_registry.async_get(controller.hass)

    # Type annotation missing in the annotations package maybe?
    entity_id = er.async_get_entity_id(platform, DOMAIN, unique_id)

    if entity_id is None:
        # This can happen when first setting up, as the target entity hasn't been created yet.
        # In this case, assume that it's going to be correctly named
        entity_id = _add_entity_id_prefix(key, controller.inverter_details)

    return entity_id


def _add_entity_id_prefix(key: str, inv_details: dict[str, Any]) -> str:
    """Add the entity ID prefix to the beginning of the given input string"""
    entity_id_prefix = inv_details[ENTITY_ID_PREFIX]

    if entity_id_prefix:
        key = f"{entity_id_prefix}_{key}"

    return slugify(key, separator="_")


def _create_unique_id(key: str, inv_details: dict[str, Any]) -> str:
    unique_id_prefix = inv_details[UNIQUE_ID_PREFIX]
    if unique_id_prefix:
        key = f"{unique_id_prefix}_{key}"

    # We don't need to prefix unique ids with foxess_modbus, but we do for some reason.
    return "foxess_modbus_" + key


class ModbusEntityProtocol(Protocol):
    """Protocol which types including ModbusEntityMixin must implement"""

    _controller: EntityController


# HA introduced a ABCCachedProperties metaclass which is used by Entity, and which derives from ABCMeta.
# This conflicts with Protocol's metaclass (from ModbusEntityProtocol).
class ModbusEntityMixinMetaclass(ABCCachedProperties, type(Protocol)):  # type: ignore
    pass


if TYPE_CHECKING:
    _ModbusEntityMixinBase = Entity
else:
    _ModbusEntityMixinBase = object


class ModbusEntityMixin(
    ModbusControllerEntity, ModbusEntityProtocol, _ModbusEntityMixinBase, metaclass=ModbusEntityMixinMetaclass
):
    """
    Mixin for subclasses of Entity

    This provides properties which are common to all FoxESS entities.
    """

    @cached_property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return _create_unique_id(self.entity_description.key, self._controller.inverter_details)

    @property
    def device_info(self) -> DeviceInfo:
        """Return device specific attributes."""
        friendly_name = self._controller.inverter_details[FRIENDLY_NAME]
        inv_model = self._controller.inverter_details[INVERTER_MODEL]
        conn_type = self._controller.inverter_details[INVERTER_CONN]
        if friendly_name:
            attr_name = f"FoxESS - Modbus ({friendly_name})"
        else:
            attr_name = "FoxESS - Modbus"

        return DeviceInfo(
            # services/utils.py relies on the order of entries here. Update that if you update this!
            identifiers={(DOMAIN, inv_model, conn_type, friendly_name)},  # type: ignore
            name=attr_name,
            model=f"{inv_model} - {conn_type}",
            manufacturer="FoxESS",
        )

    @property
    def name(self) -> str | None:
        """Return the name of the sensor."""
        friendly_name = self._controller.inverter_details[FRIENDLY_NAME]
        if friendly_name:
            return f"{self.entity_description.name} ({friendly_name})"
        return cast(str | None, self.entity_description.name)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._controller.is_connected

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        self._controller.register_modbus_entity(self)

    async def async_will_remove_from_hass(self) -> None:
        """Called when the entity is about to be removed from hass"""
        self._controller.remove_modbus_entity(self)
        await super().async_will_remove_from_hass()

    def update_callback(self, changed_addresses: set[int]) -> None:
        if any(x in changed_addresses for x in self.addresses):
            self._address_updated()

    def is_connected_changed_callback(self) -> None:
        self.schedule_update_ha_state()

    def _address_updated(self) -> None:
        """Called when the controller reads an updated to any of the addresses in self.addresses"""
        self.schedule_update_ha_state()

    def _get_entity_id(self, platform: Platform) -> str:
        """Gets the entity ID"""
        return f"{platform}.{_add_entity_id_prefix(self.entity_description.key, self._controller.inverter_details)}"

    def _validate(
        self,
        rules: list[BaseValidator],
        processed: float,
        original: float | None = None,
        address_override: int | None = None,
    ) -> bool:
        """Validate against a set of rules"""
        original = original if original is not None else processed

        valid = True
        for rule in rules:
            if not rule.validate(processed):
                if address_override is not None:
                    addresses = [address_override]
                else:
                    addresses = self.addresses
                _LOGGER.warning(
                    "Value (%s: %s) for entity '%s' address(es) '%s' failed validation against rule (%s : %s)",
                    original,
                    processed,
                    self.entity_id,
                    addresses,
                    type(rule).__name__,
                    vars(rule),
                )
                valid = False
        return valid

    @property
    def should_poll(self) -> bool:
        return False

    # Implement reference equality
    def __eq__(self, other: object) -> bool:
        return self is other

    def __hash__(self) -> int:
        return id(self)
