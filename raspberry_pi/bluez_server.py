"""Register the local GATT service and connectable advertisement with Linux BlueZ."""
import asyncio
import logging
from dbus_next.aio import MessageBus
from dbus_next.constants import BusType
from .gatt_service import (GattApplication, Advertisement, OBJECT_MANAGER, GATT_MANAGER,
                           ADVERTISING_MANAGER, ADAPTER)

LOG = logging.getLogger("inklite.pi")


def find_adapter(objects, adapter):
    path = "/org/bluez/" + adapter
    interfaces = objects.get(path, {})
    if not all(name in interfaces for name in (ADAPTER, GATT_MANAGER, ADVERTISING_MANAGER)):
        raise RuntimeError(f"{adapter} does not expose GATT and LE advertising managers. Check BlueZ and Bluetooth hardware.")
    if not interfaces[ADAPTER].get("Powered") or not interfaces[ADAPTER]["Powered"].value:
        raise RuntimeError(f"{adapter} is powered off. Run: sudo bluetoothctl power on")
    return path


class BluezServer:
    def __init__(self, config, handler, bus_factory=None):
        self.config = config
        self.application = GattApplication(config, handler)
        self.advertisement = Advertisement(config, self._advertisement_released)
        self.bus_factory = bus_factory or (lambda: MessageBus(bus_type=BusType.SYSTEM))
        self.bus = None
        self.gatt_manager = None
        self.advertising_manager = None
        self.dbus_interface = None
        self.application_registered = False
        self.advertisement_registered = False
        self.closing = False
        self.lost = asyncio.Event()
        self.exported_paths = []

    async def _call(self, awaitable):
        return await asyncio.wait_for(awaitable, timeout=self.config.register_timeout)

    def _bluez_owner_changed(self, name, old_owner, new_owner):
        if name == "org.bluez" and old_owner and old_owner != new_owner and not self.closing:
            LOG.error("[BLE] BlueZ stopped/restarted. Relaunch the receiver after Bluetooth recovers.")
            self.lost.set()

    def _advertisement_released(self):
        self.advertisement_registered = False
        if not self.closing:
            LOG.error("[BLE] Advertising stopped. Check Bluetooth and restart the receiver.")
            self.lost.set()

    async def start(self):
        try:
            self.bus = self.bus_factory()
            await self._call(self.bus.connect())
            node = await self._call(self.bus.introspect("org.bluez", "/"))
            manager = self.bus.get_proxy_object("org.bluez", "/", node).get_interface(OBJECT_MANAGER)
            objects = await self._call(manager.call_get_managed_objects())
            adapter_path = find_adapter(objects, self.config.adapter)
            adapter_node = await self._call(self.bus.introspect("org.bluez", adapter_path))
            adapter = self.bus.get_proxy_object("org.bluez", adapter_path, adapter_node)
            self.gatt_manager = adapter.get_interface(GATT_MANAGER)
            self.advertising_manager = adapter.get_interface(ADVERTISING_MANAGER)
            dbus_node = await self._call(self.bus.introspect("org.freedesktop.DBus", "/org/freedesktop/DBus"))
            self.dbus_interface = self.bus.get_proxy_object("org.freedesktop.DBus", "/org/freedesktop/DBus", dbus_node).get_interface("org.freedesktop.DBus")
            self.dbus_interface.on_name_owner_changed(self._bluez_owner_changed)
            for obj in (self.application, self.application.service, self.application.characteristic, self.advertisement):
                self.bus.export(obj.path, obj)
                self.exported_paths.append(obj.path)
            await self._call(self.gatt_manager.call_register_application(self.application.path, {}))
            self.application_registered = True
            await self._call(self.advertising_manager.call_register_advertisement(self.advertisement.path, {}))
            self.advertisement_registered = True
            LOG.info("[BLE] Advertising: %s on %s", self.config.advertising_name, self.config.adapter)
            LOG.info("[BLE] Ready for TAP / CW / CCW (writes with response)")
        except BaseException:
            await self.close()
            raise

    async def run_until_stopped(self, stop_event):
        await self.start()
        tasks = [asyncio.create_task(stop_event.wait()), asyncio.create_task(self.lost.wait()),
                 asyncio.create_task(self.bus.wait_for_disconnect())]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            if tasks[2] in done:
                await tasks[2]
                raise RuntimeError("System D-Bus disconnected")
            if self.lost.is_set():
                raise RuntimeError("BlueZ connection lost")
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            await self.close()

    async def close(self):
        if self.closing:
            return
        self.closing = True
        # Roll back a partially registered server, and release advertising before unexporting paths.
        for registered, manager, method_name, path in (
            (self.advertisement_registered, self.advertising_manager, "call_unregister_advertisement", self.advertisement.path),
            (self.application_registered, self.gatt_manager, "call_unregister_application", self.application.path),
        ):
            if registered and manager is not None:
                try:
                    await self._call(getattr(manager, method_name)(path))
                except Exception as error:
                    LOG.warning("[BLE] Cleanup: %s", error)
        if self.dbus_interface is not None:
            try:
                self.dbus_interface.off_name_owner_changed(self._bluez_owner_changed)
            except Exception as error:
                LOG.warning("[BLE] Signal cleanup: %s", error)
        if self.bus is not None:
            for path in reversed(self.exported_paths):
                try:
                    self.bus.unexport(path)
                except Exception as error:
                    LOG.warning("[BLE] Object cleanup: %s", error)
            try:
                self.bus.disconnect()
            except Exception as error:
                LOG.warning("[BLE] Bus cleanup: %s", error)
        self.application_registered = False
        self.advertisement_registered = False
        self.exported_paths.clear()
