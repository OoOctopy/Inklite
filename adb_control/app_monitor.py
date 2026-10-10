"""Run with python -m adb_control.app_monitor; Ctrl+C exits cleanly."""
import argparse
import logging
import time
from .adb_client import AdbClient, AdbError
from .config import DEFAULT_CONFIG, load_config, load_whitelist
from .usage_reader import UsageReader

LOG = logging.getLogger("inklite")


class AppMonitor:
    def __init__(self, config, adb, whitelist, enforce=False):
        self.config = config
        self.adb = adb
        self.reader = UsageReader(adb)
        self.whitelist = whitelist
        self.enforce = enforce
        self.previous = None
        self.last_attempt = {}

    def poll(self):
        app = self.reader.foreground()
        if app is None:
            self.previous = None
            return False
        if app != self.previous:
            LOG.info("[INKLITE] Foreground App: %s (user %s)", app.package, app.user)
            self.previous = app
            if not self.enforce and app.package not in self.whitelist:
                LOG.info("[INKLITE] Would block: %s (monitor-only)", app.package)
        if not self.enforce or app.package in self.whitelist:
            return True
        now = time.monotonic()
        if now - self.last_attempt.get(app, float("-inf")) < self.config.block_cooldown:
            return True
        self.last_attempt[app] = now
        # Check the destination before stopping anything; Phase 1–3 does not create an APK.
        self.adb.validate_activity(self.config.inklite_activity, app.user)
        # Re-read immediately before intervention to avoid blocking an app already left.
        if self.reader.foreground() != app:
            return True
        LOG.info("[INKLITE] Blocked App: %s", app.package)
        LOG.info("[INKLITE] Force stopping...")
        self.adb.force_stop(app.package, app.user)
        LOG.info("[INKLITE] Opening Inklite...")
        self.adb.start_activity(self.config.inklite_activity, app.user)
        return True

    def run(self):
        connected = False
        last_error = None
        unknown = False
        while True:
            started = time.monotonic()
            try:
                if not connected:
                    serial = self.adb.connect()
                    LOG.info("[ADB] Connected: %s", serial)
                    connected = True
                    self.previous = None
                known = self.poll()
                if not known and not unknown:
                    LOG.warning("[INKLITE] No unambiguous foreground package; skipping intervention.")
                unknown = not known
                if last_error is not None:
                    LOG.info("[ADB] Monitoring recovered")
                last_error = None
            except AdbError as exc:
                message = str(exc)
                if message != last_error:
                    LOG.warning("[ADB] %s Retrying in %.1fs (repeated messages suppressed).", message, self.config.retry_interval)
                last_error = message
                connected = False
                time.sleep(self.config.retry_interval)
                continue
            time.sleep(max(0, self.config.interval - (time.monotonic() - started)))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inklite ADB foreground monitor (monitor-only by default)")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="JSON settings file")
    parser.add_argument("--serial", help="Select device serial from adb devices")
    parser.add_argument("--enforce", action="store_true", help="Force-stop apps outside whitelist and redirect")
    parser.add_argument("--once", action="store_true", help="One observation/intervention then exit")
    parser.add_argument("--usage-stats", action="store_true", help="Print raw dumpsys usagestats then exit")
    args = parser.parse_args(argv)
    if args.enforce and args.usage_stats:
        parser.error("--usage-stats cannot be combined with --enforce")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    try:
        config = load_config(args.config)
        whitelist = load_whitelist(config.whitelist_path, config.inklite_package)
        adb = AdbClient(config.adb_path, args.serial or config.serial, config.timeout)
        monitor = AppMonitor(config, adb, whitelist, args.enforce)
        LOG.info("[INKLITE] Mode: %s", "ENFORCE" if args.enforce else "MONITOR ONLY")
        if args.once or args.usage_stats:
            LOG.info("[ADB] Connected: %s", adb.connect())
            if args.usage_stats:
                print(monitor.reader.usage_stats())
            elif not monitor.poll():
                LOG.warning("[INKLITE] No unambiguous foreground package")
                return 1
        else:
            monitor.run()
        return 0
    except KeyboardInterrupt:
        LOG.info("[INKLITE] Stopped")
        return 0
    except (AdbError, OSError, ValueError, KeyError) as exc:
        LOG.error("[INKLITE] %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
