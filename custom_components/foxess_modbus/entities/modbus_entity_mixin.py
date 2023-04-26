import logging

from custom_components.foxess_modbus.common.entity_controller import (
    ModbusControllerEntity,
)
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_MANUFACTURER
from homeassistant.const import ATTR_MODEL
from homeassistant.const import ATTR_NAME

from ..const import DOMAIN
from ..const import ENTITY_ID_PREFIX
from ..const import FRIENDLY_NAME
from ..const import INVERTER_CONN
from ..const import INVERTER_MODEL
from .base_validator import BaseValidator

_LOGGER = logging.getLogger(__name__)


class ModbusEntityMixin(ModbusControllerEntity):
    """
    Mixin for subclasses of Entity

    This provides properties which are common to all FoxESS entities.
    It assumes that the following propties are defined on the class:

        _controller: CallbackController
        entity_description: EntityDescription, EntityFactory
        _inv_details
    """

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "foxess_modbus_" + self._get_unique_id()

    @property
    def device_info(self):
        """Return device specific attributes."""
        friendly_name = self._inv_details[FRIENDLY_NAME]
        inv_model = self._inv_details[INVERTER_MODEL]
        conn_type = self._inv_details[INVERTER_CONN]
        if friendly_name != "":
            attr_name = f"FoxESS - Modbus ({friendly_name})"
        else:
            attr_name = "FoxESS - Modbus"

        return {
            # services/utils.py relies on the order of entries here. Update that if you update this!
            ATTR_IDENTIFIERS: {(DOMAIN, inv_model, conn_type, friendly_name)},
            ATTR_NAME: attr_name,
            ATTR_MODEL: f"{inv_model} - {conn_type}",
            ATTR_MANUFACTURER: "FoxESS",
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        friendly_name = self._inv_details[FRIENDLY_NAME]
        if friendly_name != "":
            return f"{self.entity_description.name} ({friendly_name})"
        else:
            return self.entity_description.name

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
        self.schedule_update_ha_state(True)

    def _address_updated(self) -> None:
        """Called when the controller reads an updated to any of the addresses in self.addresses"""
        self.schedule_update_ha_state(True)

    def _get_unique_id(self):
        """Get unique ID"""
        entity_id_prefix = self._inv_details[ENTITY_ID_PREFIX]
        if entity_id_prefix != "":
            return f"{entity_id_prefix}_{self.entity_description.key}"
        else:
            return f"{self.entity_description.key}"

    def _validate(
        self,
        rules: list[BaseValidator],
        processed,
        original=None,
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

    # Implement reference equality
    def __eq__(self, other):
        return self is other

    def __hash__(self):
        return id(self)
