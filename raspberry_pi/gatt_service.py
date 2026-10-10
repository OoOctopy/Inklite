"""BlueZ D-Bus server objects. Literal annotations below are D-Bus signatures."""
import logging
from dbus_next import DBusError, Variant
from dbus_next.constants import PropertyAccess
from dbus_next.service import ServiceInterface, dbus_property, method
from .config import APPLICATION_PATH, ADVERTISEMENT_PATH

OBJECT_MANAGER = "org.freedesktop.DBus.ObjectManager"
GATT_SERVICE = "org.bluez.GattService1"
GATT_CHARACTERISTIC = "org.bluez.GattCharacteristic1"
ADVERTISEMENT = "org.bluez.LEAdvertisement1"
GATT_MANAGER = "org.bluez.GattManager1"
ADVERTISING_MANAGER = "org.bluez.LEAdvertisingManager1"
ADAPTER = "org.bluez.Adapter1"
LOG = logging.getLogger("inklite.pi")


class GattService(ServiceInterface):
    def __init__(self, config):
        super().__init__(GATT_SERVICE)
        self.path = APPLICATION_PATH + "/service0"
        self.uuid = config.service_uuid

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Primary(self) -> 'b':
        return True

    @dbus_property(access=PropertyAccess.READ)
    def Includes(self) -> 'ao':
        return []

    def properties(self):
        return {"UUID": Variant("s", self.uuid), "Primary": Variant("b", True), "Includes": Variant("ao", [])}


class CommandCharacteristic(ServiceInterface):
    def __init__(self, config, service, handler):
        super().__init__(GATT_CHARACTERISTIC)
        self.path = service.path + "/char0"
        self.service_path = service.path
        self.uuid = config.command_uuid
        self.handler = handler

    @dbus_property(access=PropertyAccess.READ)
    def UUID(self) -> 's':
        return self.uuid

    @dbus_property(access=PropertyAccess.READ)
    def Service(self) -> 'o':
        return self.service_path

    @dbus_property(access=PropertyAccess.READ)
    def Flags(self) -> 'as':
        return ["write"]

    def properties(self):
        return {"UUID": Variant("s", self.uuid), "Service": Variant("o", self.service_path), "Flags": Variant("as", ["write"])}

    def receive_write(self, value, options):
        if options.get("offset", Variant("q", 0)).value != 0:
            raise DBusError("org.bluez.Error.InvalidOffset", "Commands cannot be fragmented")
        if options.get("prepare-authorize", Variant("b", False)).value:
            raise DBusError("org.bluez.Error.NotSupported", "Prepared writes are not supported")
        if options.get("type", Variant("s", "request")).value != "request":
            raise DBusError("org.bluez.Error.NotSupported", "Use a write with response")
        try:
            self.handler.receive(value)
        except ValueError as error:
            raise DBusError("org.bluez.Error.InvalidValueLength", str(error)) from error
        except Exception as error:
            LOG.exception("[COMMAND] Handler failed")
            raise DBusError("org.bluez.Error.Failed", "Command handler failed") from error

    @method()
    def WriteValue(self, value: 'ay', options: 'a{sv}'):
        self.receive_write(value, options)


class GattApplication(ServiceInterface):
    def __init__(self, config, handler):
        super().__init__(OBJECT_MANAGER)
        self.path = APPLICATION_PATH
        self.service = GattService(config)
        self.characteristic = CommandCharacteristic(config, self.service, handler)

    def managed_objects(self):
        return {
            self.service.path: {GATT_SERVICE: self.service.properties()},
            self.characteristic.path: {GATT_CHARACTERISTIC: self.characteristic.properties()},
        }

    @method()
    def GetManagedObjects(self) -> 'a{oa{sa{sv}}}':
        return self.managed_objects()


class Advertisement(ServiceInterface):
    def __init__(self, config, on_release=None):
        super().__init__(ADVERTISEMENT)
        self.path = ADVERTISEMENT_PATH
        self.config = config
        self.on_release = on_release

    @dbus_property(access=PropertyAccess.READ)
    def Type(self) -> 's':
        return "peripheral"

    @dbus_property(access=PropertyAccess.READ)
    def ServiceUUIDs(self) -> 'as':
        return [self.config.service_uuid]

    @dbus_property(access=PropertyAccess.READ)
    def LocalName(self) -> 's':
        return self.config.advertising_name

    @method()
    def Release(self):
        LOG.info("[BLE] Advertisement released by BlueZ")
        if self.on_release is not None:
            self.on_release()
