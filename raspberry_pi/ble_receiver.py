"""Run on Pi: python -m raspberry_pi.ble_receiver. --dry-run also works on Windows."""
import argparse
import asyncio
import logging
import signal
import sys
from dataclasses import replace
from .config import DEFAULT_CONFIG, load_config
from .command_handler import CommandHandler

LOG = logging.getLogger("inklite.pi")


async def run_hardware(config, handler, controller):
    if sys.platform != "linux":
        raise RuntimeError("Real BLE peripheral mode requires Linux/BlueZ (Raspberry Pi OS). Use --dry-run on Windows.")
    from .bluez_server import BluezServer
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stop_event.set)
    async def monitor_ui():
        try:
            while not stop_event.is_set():
                if controller.worker.error is not None:
                    LOG.error("[DISPLAY] Failed; stopping the BLE receiver")
                    stop_event.set()
                    return
                controller.tick()
                await asyncio.sleep(1)
        except Exception:
            LOG.exception("[UI] Update failed; stopping the BLE receiver")
            stop_event.set()
    monitor = asyncio.create_task(monitor_ui())
    try:
        await BluezServer(config, handler).run_until_stopped(stop_event)
        if controller.worker.error is not None:
            raise RuntimeError("Display worker failed") from controller.worker.error
    finally:
        monitor.cancel()
        await asyncio.gather(monitor, return_exceptions=True)
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(signum)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Inklite BlueZ GATT command receiver")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--dry-run", action="store_true", help="Exercise parser/handler without BLE hardware")
    parser.add_argument("--display", choices=("mock", "hardware"), help="Override the configured display backend")
    parser.add_argument("--commands", nargs="+", choices=("TAP", "CW", "CCW"))
    args = parser.parse_args(argv)
    if args.commands and not args.dry_run:
        parser.error("--commands requires --dry-run")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    try:
        config = load_config(args.config)
        if args.display:
            config = replace(config, display_mode=args.display)
        if args.dry_run:
            config = replace(config, display_mode="mock")
        elif sys.platform != "linux":
            raise RuntimeError("Real BLE peripheral mode requires Linux/BlueZ. Use --dry-run on Windows.")
        from .ui_controller import UIController
        controller = UIController(config)
        handler = CommandHandler(controller.on_command)
        try:
            controller.start()
            if args.dry_run:
                controller.worker.wait_for_revision(0, config.shutdown_timeout)
                LOG.info("[DRY-RUN] Local parser/UI/mock display; no BLE radio, D-Bus or SPI connection")
                for command in args.commands or ("CW", "CW", "TAP", "TAP", "CCW", "CW"):
                    handler.receive(command.encode("utf-8"))
                    controller.worker.wait_for_revision(controller.state.revision, config.shutdown_timeout)
            else:
                asyncio.run(run_hardware(config, handler, controller))
        finally:
            controller.close()
        return 0
    except KeyboardInterrupt:
        LOG.info("[BLE] Stopped")
        return 0
    except (OSError, ValueError, RuntimeError, ImportError, asyncio.TimeoutError) as error:
        LOG.error("[BLE] %s", error)
        return 1
    except Exception as error:
        LOG.error("[BLE] Receiver failed: %s. Check BlueZ service, D-Bus permissions and adapter state.", error)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
