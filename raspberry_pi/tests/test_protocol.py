import json
from pathlib import Path
import re
import tempfile
import unittest
from dbus_next import DBusError, Variant
from dbus_next.signature import SignatureTree
from raspberry_pi.config import load_config, DEFAULT_CONFIG
from raspberry_pi.command_handler import Command, CommandHandler, parse_command
from raspberry_pi.gatt_service import GattApplication, Advertisement, GATT_CHARACTERISTIC, GATT_SERVICE


class ProtocolTests(unittest.TestCase):
    def test_three_exact_commands(self):
        for command in Command:
            self.assertEqual(parse_command(command.value.encode()), command)

    def test_invalid_payloads_are_rejected(self):
        for payload in (b"", b"TAP\n", b"tap", b" CW", b"CWCCW", b"\xff\xfe", b"{}", "TAP", [84, 65, 80]):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                parse_command(payload)

    def test_mapping_and_consumer_order(self):
        received = []
        handler = CommandHandler(received.append)
        with self.assertLogs("inklite.pi", level="INFO") as logs:
            for payload in (b"TAP", b"CW", b"CCW"):
                handler.receive(payload)
        self.assertEqual(received, list(Command))
        self.assertTrue(any("[COMMAND] Next" in line for line in logs.output))
        self.assertTrue(any("[COMMAND] Back" in line for line in logs.output))

    def test_android_pi_uuids_match(self):
        config = load_config()
        source = DEFAULT_CONFIG.parent.parent / "android_app/Inklite/app/src/main/java/com/inklite/app/ble/BleConfig.kt"
        values = re.findall(r'UUID.fromString\("([^"]+)"\)', source.read_text(encoding="utf-8-sig"))
        self.assertEqual(values, [config.service_uuid, config.command_uuid])

    def test_invalid_config_values(self):
        original = json.loads(DEFAULT_CONFIG.read_text())
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for key, value in (("ADAPTER", "../../hci0"), ("ADVERTISING_NAME", "A long Bluetooth name"),
                               ("SERVICE_UUID", "invalid"), ("PAGES", ["../home"]), ("PAGES", [[]]),
                               ("DISPLAY_MODE", "fake"), ("WIDTH", True), ("BUSY_TIMEOUT", 0),
                               ("ROTATION", 45), ("TIMER_MINUTES", 0)):
                path.write_text(json.dumps({**original, key: value}), encoding="utf-8")
                with self.subTest(key=key), self.assertRaises(ValueError):
                    load_config(path)


class GattTests(unittest.TestCase):
    def setUp(self):
        self.commands = []
        self.app = GattApplication(load_config(), CommandHandler(self.commands.append))
        self.char = self.app.characteristic

    def test_object_tree_has_valid_dbus_signature_and_parent(self):
        tree = self.app.managed_objects()
        SignatureTree("a{oa{sa{sv}}}").verify([tree])
        self.assertEqual(len(tree), 2)
        self.assertTrue(tree[self.app.service.path][GATT_SERVICE]["Primary"].value)
        props = tree[self.char.path][GATT_CHARACTERISTIC]
        self.assertEqual(props["Service"].value, self.app.service.path)
        self.assertEqual(props["Flags"].value, ["write"])

    def test_write_method_introspection(self):
        method = next(item for item in self.char.introspect().methods if item.name == "WriteValue")
        self.assertEqual([arg.signature for arg in method.in_args], ["ay", "a{sv}"])
        self.assertEqual(method.out_args, [])

    def test_valid_writes_reach_command_handler(self):
        for command in Command:
            self.char.receive_write(command.value.encode(), {"offset": Variant("q", 0), "type": Variant("s", "request")})
        self.assertEqual(self.commands, list(Command))

    def test_invalid_and_fragmented_writes_have_no_side_effect(self):
        for payload, options in ((b"CW", {"offset": Variant("q", 1)}), (b"TAP", {"prepare-authorize": Variant("b", True)}),
                                 (b"CW", {"type": Variant("s", "command")}), (b"bad", {})):
            with self.subTest(options=options), self.assertRaises(DBusError):
                self.char.receive_write(payload, options)
        self.assertEqual(self.commands, [])

    def test_advertisement_is_connectable_and_matches_service(self):
        adv = Advertisement(load_config())
        self.assertEqual(adv.Type, "peripheral")
        self.assertEqual(adv.ServiceUUIDs, [load_config().service_uuid])
        self.assertEqual(adv.LocalName, "Inklite")


if __name__ == "__main__":
    unittest.main()
