import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from adb_control.adb_client import AdbClient, AdbError
from adb_control.app_monitor import AppMonitor, main
from adb_control.config import DEFAULT_CONFIG, load_config, load_whitelist
from adb_control.usage_reader import ForegroundApp, UsageReader, parse_foreground


class ParsingTests(unittest.TestCase):
    def test_modern_and_legacy_records(self):
        for marker in ("topResumedActivity", "mTopResumedActivity", "mResumedActivity", "ResumedActivity:"):
            output = f"{marker}=ActivityRecord{{123 u10 com.tencent.mm/.ui.LauncherUI t83}}"
            self.assertEqual(parse_foreground(output, (marker,)), ForegroundApp("com.tencent.mm", 10))

    def test_top_priority(self):
        adb = Mock()
        adb.shell.return_value = ("mResumedActivity: ActivityRecord{x u0 com.old/.Main t1}\n"
                                  "topResumedActivity=ActivityRecord{x u0 com.new/.Main t2}")
        self.assertEqual(UsageReader(adb).foreground().package, "com.new")

    def test_ambiguous_records_do_not_select_arbitrary_app(self):
        output = "mResumedActivity: x u0 com.one/.Main\nmResumedActivity: x u0 com.two/.Main"
        with self.assertRaises(AdbError):
            parse_foreground(output, ("mResumedActivity",))

    def test_window_fallback(self):
        adb = Mock()
        adb.shell.side_effect = ["unrecognized format", "mCurrentFocus=Window{x u0 com.android.settings/.Settings}"]
        self.assertEqual(UsageReader(adb).foreground().package, "com.android.settings")

    def test_null_focus_does_not_use_stale_focused_app(self):
        adb = Mock()
        adb.shell.side_effect = ["", "mCurrentFocus=null\nmFocusedApp=x u0 com.stale/.Main"]
        self.assertIsNone(UsageReader(adb).foreground())

    def test_raw_usage_stats(self):
        adb = Mock()
        adb.shell.return_value = "OEM-specific data"
        self.assertEqual(UsageReader(adb).usage_stats(), "OEM-specific data")
        adb.shell.assert_called_once_with("dumpsys", "usagestats")


class AdbTests(unittest.TestCase):
    def client_with_devices(self, output, serial=None):
        adb = AdbClient(serial=serial)
        adb._run = Mock(return_value=output)
        return adb

    def test_single_device(self):
        adb = self.client_with_devices("List of devices attached\nabc\tdevice\n")
        self.assertEqual(adb.connect(), "abc")
        adb.shell("dumpsys", "activity", "activities")
        adb._run.assert_called_with(["-s", "abc", "shell", "dumpsys", "activity", "activities"])

    def test_no_offline_unauthorized_or_multiple_device(self):
        for output in ("", "a offline", "a unauthorized", "a device\nb device", "a device\nb offline"):
            with self.subTest(output=output), self.assertRaises(AdbError):
                self.client_with_devices(output).connect()

    def test_explicit_device(self):
        self.assertEqual(self.client_with_devices("a device\nb device", "b").connect(), "b")
        with self.assertRaises(AdbError):
            self.client_with_devices("a device", "b").connect()

    @patch("adb_control.adb_client.subprocess.run")
    def test_missing_and_timeout(self, run):
        for error in (FileNotFoundError(), subprocess.TimeoutExpired("adb", 10)):
            run.side_effect = error
            with self.assertRaises(AdbError):
                AdbClient().connect()

    @patch("adb_control.adb_client.subprocess.run")
    def test_exit_zero_shell_error(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, "Error type 3\nError: Activity class does not exist", "")
        with self.assertRaises(AdbError):
            AdbClient()._run(["shell", "am", "start"])

    def test_force_stop_and_start_arguments(self):
        adb = AdbClient()
        adb.serial = "phone"
        adb._run = Mock(return_value="")
        adb.force_stop("com.example.app", 10)
        adb._run.assert_called_with(["-s", "phone", "shell", "am", "force-stop", "--user", "10", "com.example.app"])
        adb.start_activity("com.inklite.app/.MainActivity", 10)
        adb._run.assert_called_with(["-s", "phone", "shell", "am", "start", "--user", "10", "-n", "com.inklite.app/.MainActivity"])
        with self.assertRaises(ValueError):
            adb.force_stop("com.bad;reboot", 0)

    def test_missing_redirect(self):
        adb = AdbClient()
        adb.shell = Mock(return_value="No activity found")
        with self.assertRaises(AdbError):
            adb.validate_activity("com.inklite.app/.MainActivity", 0)


class ConfigTests(unittest.TestCase):
    def test_defaults_and_self_whitelist(self):
        config = load_config()
        self.assertEqual(config.interval, 0.75)
        with tempfile.TemporaryDirectory() as folder:
            whitelist = Path(folder) / "whitelist.json"
            whitelist.write_text('["com.android.settings"]', encoding="utf-8")
            self.assertIn(config.inklite_package, load_whitelist(whitelist, config.inklite_package))
            whitelist.write_text('["bad;command"]', encoding="utf-8")
            with self.assertRaises(ValueError):
                load_whitelist(whitelist, config.inklite_package)

    def test_invalid_configuration(self):
        base = json.loads(DEFAULT_CONFIG.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "config.json"
            for key, value in (("CHECK_INTERVAL", 0), ("ADB_TIMEOUT", True),
                               ("INKLITE_ACTIVITY", "com.other/.Main"), ("DEVICE_SERIAL", ""),
                               ("WHITELIST_PATH", ""), ("TYPO", 1)):
                data = {**base, key: value}
                path.write_text(json.dumps(data), encoding="utf-8")
                with self.subTest(key=key), self.assertRaises(ValueError):
                    load_config(path)


class MonitorTests(unittest.TestCase):
    def monitor(self, enforce=True):
        adb = Mock()
        monitor = AppMonitor(load_config(), adb, {"com.android.settings", "com.inklite.app"}, enforce)
        monitor.reader = Mock()
        monitor.reader.foreground.return_value = ForegroundApp("com.blocked.app", 0)
        return monitor, adb

    def test_observation_never_stops(self):
        monitor, adb = self.monitor(False)
        with self.assertLogs("inklite") as logs:
            monitor.poll()
            monitor.poll()
        self.assertEqual(sum("Foreground App:" in line for line in logs.output), 1)
        adb.force_stop.assert_not_called()
        adb.start_activity.assert_not_called()

    def test_whitelisted_and_unknown_are_untouched(self):
        monitor, adb = self.monitor()
        for app in (ForegroundApp("com.android.settings", 0), None):
            monitor.reader.foreground.return_value = app
            monitor.poll()
        adb.force_stop.assert_not_called()

    def test_block_redirect_and_cooldown(self):
        monitor, adb = self.monitor()
        monitor.poll()
        monitor.poll()
        adb.validate_activity.assert_called_once_with("com.inklite.app/.MainActivity", 0)
        adb.force_stop.assert_called_once_with("com.blocked.app", 0)
        adb.start_activity.assert_called_once_with("com.inklite.app/.MainActivity", 0)
        self.assertEqual([call[0] for call in adb.method_calls], ["validate_activity", "force_stop", "start_activity"])

    def test_uninstalled_target_prevents_stop(self):
        monitor, adb = self.monitor()
        adb.validate_activity.side_effect = AdbError("No activity found")
        with self.assertRaises(AdbError):
            monitor.poll()
        adb.force_stop.assert_not_called()

    def test_foreground_change_before_stop(self):
        monitor, adb = self.monitor()
        monitor.reader.foreground.side_effect = [ForegroundApp("com.blocked.app", 0), ForegroundApp("com.android.settings", 0)]
        monitor.poll()
        adb.force_stop.assert_not_called()

    @patch("adb_control.app_monitor.time.sleep")
    def test_disconnect_recovers(self, sleep):
        monitor, adb = self.monitor(False)
        adb.connect.side_effect = [AdbError("disconnected"), "phone"]
        monitor.reader.foreground.side_effect = [ForegroundApp("com.android.settings", 0), KeyboardInterrupt()]
        with self.assertRaises(KeyboardInterrupt):
            monitor.run()
        self.assertEqual(adb.connect.call_count, 2)
        sleep.assert_any_call(monitor.config.retry_interval)

    @patch("adb_control.app_monitor.AdbClient")
    def test_once_failure_exit(self, client):
        client.return_value.connect.side_effect = AdbError("no device")
        self.assertEqual(main(["--once"]), 1)


if __name__ == "__main__":
    unittest.main()
