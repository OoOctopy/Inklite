# Raspberry Pi 4 + Waveshare 3.97-inch setup

The adapter targets the [official black/white 3.97-inch SPI model](https://www.waveshare.com/wiki/3.97inch_e-Paper_HAT%2B_Manual), 800×480, using `epd3in97`. The four-color `(G)` model has a different driver. This guide assumes the screen has its compatible driver board/HAT; a raw panel alone does not connect directly to GPIO.

## Software

Copy the complete repository to Raspberry Pi OS. In its root:

```bash
sudo apt update
sudo apt install -y bluez python3-venv python3-pip python3-gpiozero python3-spidev python3-lgpio
sudo raspi-config nonint do_spi 0
sudo systemctl enable --now bluetooth
sudo bluetoothctl power on
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r raspberry_pi/requirements.txt
```

Reboot if SPI/device nodes are not available after enabling it. `--system-site-packages` lets the venv use apt's GPIO/SPI libraries. The required original Waveshare Python files are already bundled; no hand-written SPI protocol or second driver download is needed.

First verify software with no screen/radio dependency:

```bash
.venv/bin/python -m unittest discover -s raspberry_pi/tests -v
.venv/bin/python -m raspberry_pi.ble_receiver --dry-run
```

## Wiring

Power the Pi off while connecting the HAT/cable. For the official 9-pin cable, the driver's defaults correspond to this [manufacturer mapping](https://www.waveshare.com/wiki/3.97inch_e-Paper_HAT%2B_Manual):

| Screen signal | Pi BCM | Physical header pin |
| --- | --- | --- |
| VCC | 3.3 V supply | 1 |
| GND | Ground | 6 |
| DIN | GPIO10 / MOSI | 19 |
| CLK | GPIO11 / SCLK | 23 |
| CS | GPIO8 / CE0 | 24 |
| DC | GPIO25 | 22 |
| RST | GPIO17 | 11 |
| BUSY | GPIO24 | 18 |
| PWR | GPIO18 | 12 |

For a 40-pin HAT, use its correctly oriented connector and the manufacturer's instructions. The selected configuration uses SPI0/CE0. Check the actual board labels/model before the first hardware run.

## Stage the physical tests

1. Keep display mode mock and establish Android BLE first:

```bash
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display mock
```

2. Stop that process. Test the physical screen without BLE:

```bash
sudo .venv/bin/python -m raspberry_pi.display_controller --mode hardware --page home
```

Expected: the home frame appears, then the driver sleeps/releases SPI/GPIO. Do not run two hardware display processes together.

3. Run the complete receiver:

```bash
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display hardware
```

Use the Android manual BLE test buttons, then the physical volume key and rear-camera gestures. Expect received commands, UI changes and `[DISPLAY] Render:` after refresh. Full refresh is slower than navigation; the worker serializes access and coalesces pending frames to the latest state.

## Configuration and errors

`raspberry_pi/config.json` centralizes adapter/UUIDs/pages/timer/display settings. Default display is mock. For unattended hardware use, change `DISPLAY_MODE` or pass `--display hardware`.

The defaults are 800×480, rotation 0, the bundled manufacturer path and `waveshare_epd.epd3in97`. Rotation 90/270 requires a 480×800 logical canvas. The adapter rejects mismatched physical dimensions instead of silently sending a blank buffer. `MIN_REFRESH_INTERVAL` throttles full-refresh completion intervals. `BUSY_TIMEOUT` bounds each BUSY-high wait; `SHUTDOWN_TIMEOUT` bounds display-thread shutdown.

- Missing BlueZ managers: check `bluetoothctl list`, adapter name, Bluetooth service and peripheral/advertising support.
- Powered-off adapter: `sudo bluetoothctl power on`.
- D-Bus permission denied: use the shown prototype `sudo .venv/bin/python ...` command.
- GPIO/SPI import failure: check apt packages and `--system-site-packages`.
- BUSY timeout: check supply, all signal wires, PWR and the exact screen/board model.
- A driver failure stops the receiver; do not interpret a previous successful BLE log as a successful screen update.

## Optional boot service

The supplied unit is a template for a repository installed at `/opt/inklite`. Create its venv there, verify the manual hardware command, then install the unit:

```bash
sudo cp deployment/inklite-pi.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now inklite-pi
journalctl -u inklite-pi -f
```

It runs under systemd's default root user for prototype device/D-Bus access and restarts on failure. If you use another installation directory, update `WorkingDirectory` and `ExecStart` first. Stop it with `sudo systemctl stop inklite-pi` before standalone screen tests.
