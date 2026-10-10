import asyncio
import unittest
from dbus_next import Variant
from raspberry_pi.config import load_config
from raspberry_pi.command_handler import CommandHandler
from raspberry_pi.bluez_server import BluezServer, find_adapter
from raspberry_pi.gatt_service import OBJECT_MANAGER, GATT_MANAGER, ADVERTISING_MANAGER, ADAPTER


class FakeBus:
    def __init__(self, fail_advertisement=False):
        self.calls = []
        self.fail_advertisement = fail_advertisement
        self.closed = asyncio.Event()
    async def connect(self):
        return self
    async def introspect(self, service, path):
        return None
    def get_proxy_object(self, service, path, node):
        return self
    def get_interface(self, name):
        return self
    async def call_get_managed_objects(self):
        return {"/org/bluez/hci0": {ADAPTER: {"Powered": Variant("b", True)}, GATT_MANAGER: {}, ADVERTISING_MANAGER: {}}}
    def on_name_owner_changed(self, callback):
        self.owner_callback = callback
    def off_name_owner_changed(self, callback):
        self.owner_callback = None
    def export(self, path, obj):
        self.calls.append(("export", path))
    def unexport(self, path):
        self.calls.append(("unexport", path))
    async def call_register_application(self, path, options):
        self.calls.append(("register_app", path))
    async def call_register_advertisement(self, path, options):
        if self.fail_advertisement:
            raise RuntimeError("Advertising unavailable")
        self.calls.append(("register_adv", path))
    async def call_unregister_application(self, path):
        self.calls.append(("unregister_app", path))
    async def call_unregister_advertisement(self, path):
        self.calls.append(("unregister_adv", path))
    async def wait_for_disconnect(self):
        await self.closed.wait()
    def disconnect(self):
        self.calls.append(("disconnect", None))
        self.closed.set()


class RegistrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_registration_and_cleanup_order(self):
        bus = FakeBus()
        server = BluezServer(load_config(), CommandHandler(), lambda: bus)
        await server.start()
        self.assertEqual([call[0] for call in bus.calls], ["export"] * 4 + ["register_app", "register_adv"])
        await server.close()
        self.assertEqual([call[0] for call in bus.calls][6:8], ["unregister_adv", "unregister_app"])
        self.assertTrue(bus.closed.is_set())

    async def test_failed_advertisement_rolls_back_application(self):
        bus = FakeBus(True)
        server = BluezServer(load_config(), CommandHandler(), lambda: bus)
        with self.assertRaises(RuntimeError):
            await server.start()
        self.assertIn("unregister_app", [call[0] for call in bus.calls])
        self.assertTrue(bus.closed.is_set())

    async def test_stop_event_unregisters_server(self):
        bus = FakeBus()
        server = BluezServer(load_config(), CommandHandler(), lambda: bus)
        stop = asyncio.Event()
        stop.set()
        await server.run_until_stopped(stop)
        self.assertTrue(bus.closed.is_set())

    async def test_bluez_restart_is_detected(self):
        bus = FakeBus()
        server = BluezServer(load_config(), CommandHandler(), lambda: bus)
        await server.start()
        with self.assertLogs("inklite.pi", level="ERROR"):
            server._bluez_owner_changed("org.bluez", ":1.1", "")
        self.assertTrue(server.lost.is_set())
        await server.close()

    async def test_advertisement_release_is_detected(self):
        bus = FakeBus()
        server = BluezServer(load_config(), CommandHandler(), lambda: bus)
        await server.start()
        with self.assertLogs("inklite.pi", level="ERROR"):
            server._advertisement_released()
        self.assertTrue(server.lost.is_set())
        await server.close()

    async def test_unpowered_or_missing_adapter_is_not_assumed_ready(self):
        with self.assertRaises(RuntimeError):
            find_adapter({}, "hci0")
        with self.assertRaises(RuntimeError):
            find_adapter({"/org/bluez/hci0": {ADAPTER: {"Powered": Variant("b", False)}, GATT_MANAGER: {}, ADVERTISING_MANAGER: {}}}, "hci0")


if __name__ == "__main__":
    unittest.main()
