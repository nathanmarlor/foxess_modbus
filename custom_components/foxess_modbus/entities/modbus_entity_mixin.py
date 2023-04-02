import logging

from custom_components.foxess_modbus.entities.validation import BaseValidator
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_MANUFACTURER
from homeassistant.const import ATTR_MODEL
from homeassistant.const import ATTR_NAME

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..const import INVERTER_CONN
from ..const import INVERTER_MODEL

_LOGGER = logging.getLogger(__name__)


class ModbusEntityMixin:
    """
    Mixin for subclasses of Entity

    This provides properties which are common to all FoxESS entities.
    It assumes that the following propties are defined on the class:

        controller: CallbackController
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

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        self._controller.add_update_listener(self)

    def update_callback(self, changed_addresses: set[int]) -> None:
        """Schedule a state update."""
        if any(x in changed_addresses for x in self.entity_description.addresses):
            self._address_updated()

    def _address_updated(self) -> None:
        """Called when the controller reads an updated to any of the addresses in entity_description.addresses"""
        self.schedule_update_ha_state(True)

    def _get_unique_id(self):
        """Get unique ID"""
        friendly_name = self._inv_details[FRIENDLY_NAME]
        if friendly_name != "":
            return f"{friendly_name}_{self.entity_description.key}"
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
                    address = address_override
                elif hasattr(self.entity_description, "address"):
                    address = self.entity_description.address
                else:
                    address = None
                _LOGGER.warning(
                    "Value (%s: %s) for entity '%s' address '%s' failed validation against rule (%s : %s)",
                    original,
                    processed,
                    self.entity_id,
                    address,
                    type(rule).__name__,
                    vars(rule),
                )
                valid = False
        return valid
