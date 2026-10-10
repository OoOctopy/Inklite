"""Pillow renderer + mock/Waveshare adapter. No SPI register protocol is implemented here."""
import argparse
from dataclasses import replace
import importlib
import logging
from pathlib import Path
import sys
import threading
import time
from .config import DEFAULT_CONFIG, load_config
from .page_renderer import PageRenderer
from .ui_state import UIState

LOG = logging.getLogger("inklite.pi")


def guarded_driver_class(module, timeout, clock=time.monotonic):
    """Only bound the vendor's BUSY wait; leave its register/SPI/display implementation unchanged.

    This is specific to the bundled epd3in97 driver, whose BUSY polarity is high.
    """
    class GuardedEPD(module.EPD):
        def ReadBusy(self):
            deadline = clock() + timeout
            module.epdconfig.delay_ms(100)
            while module.epdconfig.digital_read(self.busy_pin) == 1:
                if clock() >= deadline:
                    raise TimeoutError("Waveshare BUSY stayed high. Check power, wiring and the screen/driver model.")
                module.epdconfig.delay_ms(5)
    return GuardedEPD


class MockDisplay:
    def __init__(self, config):
        self.directory = config.mock_output_dir

    def open(self):
        self.directory.mkdir(parents=True, exist_ok=True)

    def render(self, image, state):
        image.save(self.directory / "current.png")
        image.save(self.directory / (state.page + ".png"))

    def close(self):
        pass


class WaveshareDisplay:
    def __init__(self, config, driver_factory=None):
        self.config = config
        self.driver_factory = driver_factory
        self.driver = None
        self.module = None
        self.initialised = False

    def open(self):
        if self.driver_factory is None:
            if sys.platform != "linux":
                raise RuntimeError("SPI hardware mode requires Raspberry Pi OS. Use mock mode on Windows.")
            if self.config.driver_module != "waveshare_epd.epd3in97":
                raise ValueError("This adapter targets the confirmed Waveshare 3.97-inch black/white epd3in97 driver")
            if not self.config.driver_path.is_dir():
                raise FileNotFoundError("Manufacturer driver path is missing")
            sys.path.insert(0, str(self.config.driver_path))
            try:
                self.module = importlib.import_module(self.config.driver_module)
                self.driver = guarded_driver_class(self.module, self.config.busy_timeout)()
            except ImportError as error:
                raise RuntimeError("Install Raspberry Pi GPIO/SPI packages (gpiozero, spidev and lgpio); enable SPI.") from error
            finally:
                sys.path.remove(str(self.config.driver_path))
        else:
            self.driver = self.driver_factory()
        for name in ("init", "getbuffer", "display", "sleep"):
            if not callable(getattr(self.driver, name, None)):
                raise TypeError(f"Manufacturer driver lacks {name}()")
        expected = (self.config.height, self.config.width) if self.config.rotation in (90, 270) else (self.config.width, self.config.height)
        if (self.driver.width, self.driver.height) != expected:
            raise ValueError("Configured canvas/rotation does not match the driver's physical resolution")
        result = self.driver.init()
        if result not in (None, 0):
            raise RuntimeError(f"Manufacturer driver initialization failed: {result}")
        self.initialised = True

    def render(self, image, state):
        if not self.initialised:
            raise RuntimeError("Display has not initialized")
        frame = image.convert("1").rotate(self.config.rotation, expand=True)
        if frame.size != (self.driver.width, self.driver.height):
            raise ValueError("Frame dimensions do not match hardware")
        buffer = self.driver.getbuffer(frame)
        if len(buffer) != self.driver.width * self.driver.height // 8:
            raise ValueError("Manufacturer driver returned an unexpected monochrome buffer length")
        self.driver.display(buffer)

    def close(self):
        if self.initialised:
            self.driver.sleep()  # The bundled driver also releases SPI/GPIO in sleep().
            self.initialised = False
        elif self.module is not None:
            self.module.epdconfig.module_exit()


class DisplayController:
    def __init__(self, config, backend=None):
        self.config = config
        self.renderer = PageRenderer(config)
        self.backend = backend or (MockDisplay(config) if config.display_mode == "mock" else WaveshareDisplay(config))

    def open(self):
        self.backend.open()

    def render(self, state):
        image = self.renderer.render(state)
        self.backend.render(image, state)
        LOG.info("[DISPLAY] Render: %s (revision %d, %s)", state.page, state.revision, self.config.display_mode)

    def close(self):
        self.backend.close()


class DisplayWorker:
    """One display thread, one pending latest snapshot. Slow e-paper never blocks a GATT write."""
    def __init__(self, controller):
        self.controller = controller
        self.condition = threading.Condition()
        self.pending = None
        self.closing = False
        self.error = None
        self.ready = threading.Event()
        self.rendered_revision = -1
        self.thread = threading.Thread(target=self._run, name="inklite-display", daemon=True)

    def start(self):
        self.thread.start()
        if not self.ready.wait(self.controller.config.busy_timeout + 5):
            self.close()
            raise TimeoutError("Display initialization timed out")
        if self.error is not None:
            raise RuntimeError("Display initialization failed") from self.error

    def submit(self, state):
        with self.condition:
            if self.closing or self.error is not None:
                raise RuntimeError("Display worker is unavailable")
            self.pending = state
            self.condition.notify_all()

    def wait_for_revision(self, revision, timeout):
        deadline = time.monotonic() + timeout
        with self.condition:
            while self.rendered_revision < revision and self.error is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Display did not render the requested revision")
                self.condition.wait(remaining)
            if self.error is not None:
                raise RuntimeError("Display render failed") from self.error

    def _run(self):
        try:
            self.controller.open()
            self.ready.set()
            last_refresh = float("-inf")
            while True:
                with self.condition:
                    while self.pending is None and not self.closing:
                        self.condition.wait()
                    if self.pending is None:
                        break
                    interval = self.controller.config.min_refresh_interval if self.controller.config.display_mode == "hardware" else 0
                    delay = max(0, last_refresh + interval - time.monotonic())
                    if delay:
                        self.condition.wait(delay)
                        continue
                    state = self.pending
                    self.pending = None
                self.controller.render(state)
                last_refresh = time.monotonic()
                with self.condition:
                    self.rendered_revision = max(self.rendered_revision, state.revision)
                    self.condition.notify_all()
        except Exception as error:
            LOG.exception("[DISPLAY] Worker failed")
            with self.condition:
                self.error = error
                self.condition.notify_all()
        finally:
            self.ready.set()
            try:
                self.controller.close()
            except Exception as error:
                LOG.exception("[DISPLAY] Shutdown failed")
                if self.error is None:
                    self.error = error

    def close(self):
        with self.condition:
            self.closing = True
            self.condition.notify_all()
        if self.thread.ident is not None:
            self.thread.join(self.controller.config.shutdown_timeout)
            if self.thread.is_alive():
                raise TimeoutError("Display driver has not finished; check hardware/driver BUSY handling")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Render one Inklite page, without BLE")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--mode", choices=("mock", "hardware"))
    parser.add_argument("--page", default="home")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    config = load_config(args.config)
    if args.mode:
        config = replace(config, display_mode=args.mode)
    if args.page not in config.pages:
        parser.error("--page must be one of the configured PAGES")
    state = UIState(config.pages, config.timer_minutes)
    state.index = config.pages.index(args.page)
    worker = DisplayWorker(DisplayController(config))
    try:
        worker.start()
        worker.submit(state.snapshot())
        worker.wait_for_revision(0, config.shutdown_timeout)
    finally:
        worker.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
