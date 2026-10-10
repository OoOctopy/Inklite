from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from PIL import Image
from raspberry_pi.config import load_config
from raspberry_pi.command_handler import Command, CommandHandler
from raspberry_pi.display_controller import DisplayController, DisplayWorker, WaveshareDisplay, guarded_driver_class
from raspberry_pi.page_renderer import PageRenderer
from raspberry_pi.ui_controller import UIController
from raspberry_pi.ui_state import UIState


class FakeDriver:
    width = 800
    height = 480
    def __init__(self):
        self.calls = []
    def init(self):
        self.calls.append("init")
    def getbuffer(self, image):
        self.calls.append(("getbuffer", image.mode, image.size))
        return image.tobytes()
    def display(self, buffer):
        self.calls.append(("display", len(buffer)))
    def sleep(self):
        self.calls.append("sleep")


class RenderTests(unittest.TestCase):
    def test_all_assets_are_real_one_bit_bitmaps(self):
        config = load_config()
        for page in config.pages:
            with Image.open(config.assets_path / (page + ".bmp")) as image:
                self.assertEqual(image.format, "BMP")
                self.assertEqual(image.mode, "1")
                self.assertEqual(image.size, (800, 480))

    def test_all_pages_render_to_correct_monochrome_dimensions(self):
        config = load_config()
        renderer = PageRenderer(config)
        state = UIState(config.pages)
        rendered = []
        for i in range(len(config.pages)):
            state.index = i
            frame = renderer.render(state.snapshot())
            self.assertEqual(frame.mode, "1")
            self.assertEqual(frame.size, (800, 480))
            self.assertEqual(len(frame.tobytes()), 48000)
            rendered.append(frame.tobytes())
        self.assertEqual(len(set(rendered)), 4)

    def test_status_and_enter_state_change_real_pixels(self):
        config = load_config()
        renderer = PageRenderer(config)
        state = UIState()
        state.index = 3
        before = renderer.render(state.snapshot()).tobytes()
        state.apply(Command.TAP)
        self.assertNotEqual(before, renderer.render(state.snapshot()).tobytes())

    def test_missing_assets_fail_before_hardware_access(self):
        with tempfile.TemporaryDirectory() as folder:
            config = replace(load_config(), assets_path=Path(folder))
            with self.assertRaises(FileNotFoundError):
                DisplayController(config)

    def test_mock_controller_writes_actual_pngs(self):
        with tempfile.TemporaryDirectory() as folder:
            config = replace(load_config(), mock_output_dir=Path(folder))
            display = DisplayController(config)
            display.open()
            display.render(UIState().snapshot())
            display.close()
            with Image.open(Path(folder) / "current.png") as image:
                self.assertEqual(image.mode, "1")
                self.assertEqual(image.size, (800, 480))


class HardwareAdapterTests(unittest.TestCase):
    def test_driver_contract_and_shutdown(self):
        driver = FakeDriver()
        adapter = WaveshareDisplay(load_config(), lambda: driver)
        adapter.open()
        adapter.render(Image.new("1", (800, 480), 1), UIState().snapshot())
        adapter.close()
        self.assertEqual(driver.calls, ["init", ("getbuffer", "1", (800, 480)), ("display", 48000), "sleep"])

    def test_incorrect_resolution_is_not_silently_sent(self):
        config = replace(load_config(), width=480, height=800)
        driver = FakeDriver()
        with self.assertRaises(ValueError):
            WaveshareDisplay(config, lambda: driver).open()
        self.assertEqual(driver.calls, [])

    def test_portrait_rotation_matches_driver_dimensions(self):
        config = replace(load_config(), width=480, height=800, rotation=90)
        driver = FakeDriver()
        adapter = WaveshareDisplay(config, lambda: driver)
        adapter.open()
        adapter.render(Image.new("1", (480, 800), 1), UIState().snapshot())
        adapter.close()
        self.assertIn(("getbuffer", "1", (800, 480)), driver.calls)

    def test_failed_driver_init_is_reported(self):
        driver = FakeDriver()
        driver.init = lambda: -1
        adapter = WaveshareDisplay(load_config(), lambda: driver)
        with self.assertRaises(RuntimeError):
            adapter.open()

    def test_incorrect_buffer_length_is_rejected(self):
        driver = FakeDriver()
        driver.getbuffer = lambda image: b"x"
        adapter = WaveshareDisplay(load_config(), lambda: driver)
        adapter.open()
        try:
            with self.assertRaises(ValueError):
                adapter.render(Image.new("1", (800, 480)), UIState().snapshot())
            self.assertFalse(any(isinstance(call, tuple) and call[0] == "display" for call in driver.calls))
        finally:
            adapter.close()

    def test_stuck_busy_pin_has_bounded_wait(self):
        clock = [0.0]
        epdconfig = types.SimpleNamespace(
            digital_read=lambda pin: 1,
            delay_ms=lambda milliseconds: clock.__setitem__(0, clock[0] + milliseconds / 1000)
        )
        class Driver:
            busy_pin = 24
        module = types.SimpleNamespace(EPD=Driver, epdconfig=epdconfig)
        guarded = guarded_driver_class(module, 0.2, lambda: clock[0])()
        with self.assertRaises(TimeoutError):
            guarded.ReadBusy()
        self.assertLess(clock[0], 0.3)

    def test_vendor_files_are_unchanged_from_recorded_download(self):
        root = load_config().driver_path.parent
        metadata = json.loads((root / "provenance.json").read_text())
        for item in metadata["files"]:
            file = root / "lib/waveshare_epd" / item["file"]
            self.assertEqual(hashlib.sha256(file.read_bytes()).hexdigest(), item["sha256"])

    def test_actual_vendor_getbuffer_packs_pillow_one_bit_frame(self):
        # Import the unchanged vendor module with only GPIO access stubbed, not its buffer implementation.
        package = types.ModuleType("inklite_test_vendor")
        package.__path__ = []
        gpio = types.ModuleType("inklite_test_vendor.epdconfig")
        for name, number in (("RST_PIN", 17), ("DC_PIN", 25), ("BUSY_PIN", 24), ("CS_PIN", 8)):
            setattr(gpio, name, number)
        with patch.dict(sys.modules, {package.__name__: package, gpio.__name__: gpio}):
            path = load_config().driver_path / "waveshare_epd/epd3in97.py"
            spec = importlib.util.spec_from_file_location("inklite_test_vendor.epd3in97", path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            driver = module.EPD()
            image = Image.new("1", (800, 480), 1)
            image.putpixel((0, 0), 0)
            buffer = driver.getbuffer(image)
            self.assertEqual(len(buffer), 48000)
            self.assertEqual(buffer[0], 0x7f)
            self.assertEqual(buffer[1], 0xff)


class WorkerTests(unittest.TestCase):
    def test_slow_display_coalesces_to_latest_state_without_blocking_input(self):
        started, release = threading.Event(), threading.Event()
        class Backend:
            def __init__(self):
                self.revisions = []
            def open(self):
                pass
            def render(self, image, state):
                self.revisions.append(state.revision)
                if state.revision == 0:
                    started.set()
                    if not release.wait(3):
                        raise TimeoutError("Test release missing")
            def close(self):
                pass
        backend = Backend()
        worker = DisplayWorker(DisplayController(load_config(), backend))
        state = UIState()
        worker.start()
        try:
            worker.submit(state.snapshot())
            self.assertTrue(started.wait(3))
            for _ in range(3):
                worker.submit(state.apply(Command.CW))
            release.set()
            worker.wait_for_revision(3, 3)
            self.assertEqual(backend.revisions, [0, 3])
        finally:
            release.set()
            worker.close()

    def test_renderer_failure_is_observable(self):
        class Backend:
            def open(self):
                pass
            def render(self, image, state):
                raise OSError("Display unavailable")
            def close(self):
                pass
        worker = DisplayWorker(DisplayController(load_config(), Backend()))
        with self.assertLogs("inklite.pi", level="ERROR"):
            worker.start()
            worker.submit(UIState().snapshot())
            with self.assertRaises(RuntimeError):
                worker.wait_for_revision(0, 3)
            worker.close()
        self.assertIsInstance(worker.error, OSError)

    def test_full_gatt_parser_ui_mock_pipeline(self):
        from raspberry_pi.gatt_service import GattApplication
        with tempfile.TemporaryDirectory() as folder:
            config = replace(load_config(), mock_output_dir=Path(folder))
            controller = UIController(config)
            app = GattApplication(config, CommandHandler(controller.on_command))
            controller.start()
            try:
                for command in (b"CW", b"CW", b"TAP", b"TAP", b"CCW"):
                    app.characteristic.receive_write(command, {})
                    controller.worker.wait_for_revision(controller.state.revision, 3)
                snapshot = controller.state.snapshot()
                self.assertEqual(snapshot.page, "timer")
                self.assertFalse(snapshot.entered)
                self.assertEqual(snapshot.timer_state, "running")
                self.assertEqual(snapshot.received_count, 5)
                self.assertTrue((Path(folder) / "timer.png").is_file())
            finally:
                controller.close()


if __name__ == "__main__":
    unittest.main()
