# Raspberry Pi output layer

Implemented modules:

- `config.py/config.json`: portable settings, adapter/UUIDs/pages/timer/display dimensions.
- `gatt_service.py`: typed BlueZ GATT service, writable characteristic and advertisement.
- `bluez_server.py`: actual system D-Bus registration, rollback, shutdown and service-loss handling.
- `ble_receiver.py`: command-line entry point and UI/display lifecycle.
- `command_handler.py`: strict three-word parser and independent command routing.
- `ui_state.py/ui_controller.py`: menu, local focus indicator and monotonic timer.
- `page_renderer.py/display_controller.py`: 1-bit images, real mock PNGs, serial worker and Waveshare adapter.

From the repository root, with `requirements.txt` installed for this directory:

```text
python -m unittest discover -s raspberry_pi/tests -v
python -m raspberry_pi.ble_receiver --dry-run
```

On Pi:

```bash
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display mock
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display hardware
```

Run only one of the above at a time. Default display mode is mock. Real BLE requires Linux/BlueZ; real SPI uses the confirmed Waveshare black/white 3.97-inch driver. Windows can run the parser/state/mock-image pipeline and simulated D-Bus tests, not the actual peripheral.

Setup, wiring and error handling: [Pi guide](../docs/raspberry-pi-setup.md). Phone transport tests: [BLE guide](../docs/ble-testing.md). See [the final acceptance checklist](../docs/hardware-acceptance.md).
