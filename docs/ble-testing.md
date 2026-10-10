# BLE acceptance — Android central to Pi peripheral

The client follows [Android's Bluetooth permission model](https://developer.android.com/develop/connectivity/bluetooth/bt-permissions); the Pi uses the [BlueZ GATT server API](https://github.com/bluez/bluez/blob/master/doc/org.bluez.GattCharacteristic.rst). Local software tests do not prove radio communication.

## 1. Start Pi with mock output

Complete [Pi installation](raspberry-pi-setup.md), then run from the repository root:

```bash
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display mock
```

Expected:

```text
[UI] Home
[BLE] Advertising: Inklite on hci0
[BLE] Ready for TAP / CW / CCW (writes with response)
```

Run one intended Inklite receiver nearby. The app selects the first advertised matching service. Pairing through the phone's system settings is unnecessary for this prototype.

## 2. Manual command test first

Install the final Android APK, open it, and tap **Find and connect to Inklite Pi**. Grant Nearby Devices on Android 12+. On Android 8–11 grant Location and enable system Location services for BLE discovery; no position data is collected. If Bluetooth is off, accept the system enable prompt. Camera permission is independent.

Expected Android Logcat progression:

```text
[BLE] Searching for Inklite Pi…
[BLE] Connecting to Inklite Pi…
[BLE] Discovering command service…
[BLE] BLE connected. TAP / CW / CCW ready.
```

Use the **Developer BLE test commands** panel in the debug APK. Press TAP, CW and CCW. These controls are for protocol testing; they are separate from normal physical/gesture input.

```text
[DEBUG] Manual BLE test: CW
[COMMAND] CW
[BLE] Sending: CW
[BLE] Sent: CW
```

Pi should show:

```text
[BLE] Received: CW
[COMMAND] Next
[UI] Current Page: Focus / Browse
[DISPLAY] Render: focus (..., mock)
```

`work/mock_display/current.png` must change. The Android write response confirms handler acceptance. Refresh completion is represented by the Pi's display log and image/screen, not an extra protocol acknowledgement.

## 3. Connect real inputs

Press the configured volume key:

```text
[INPUT] Volume key detected
[COMMAND] TAP
[BLE] Sending: TAP
```

Enable rotational recognition only after the 21 landmarks are stable. CW/CCW should produce their gesture and command logs, and the Pi should receive the matching word. Use the direction inversion setting when necessary. No camera TAP exists. See [input testing](android-testing.md).

## 4. Failure/reconnect behavior

- No receiver: scan ends after 15 seconds with a useful message; manual buttons remain disabled.
- Receiver stops/range is lost: the app clears its in-flight/pending queue. Restart Pi, then reconnect.
- Permission revoked or Bluetooth disabled: operations fail visibly and release resources. Grant/enable, then reconnect.
- Write times out: delivery may be unknown. Inputs are not replayed automatically because TAP is not idempotent.
- Queue full: newest input is dropped and logged; older accepted writes retain order.
- Switching to an essential app: camera stops, but an established BLE link is retained. Input is foreground-only. Activity destruction or process reclamation can close the link.
- BlueZ restarts/releases advertising: Pi exits with an error and cleans up; relaunch the receiver or let the optional systemd unit restart it.

## Protocol

Service UUID `72fbb2cc-949e-4a4e-9c23-03f50a0798cb`.
Command UUID `10fc5a67-f00e-4d52-94c2-673a573b6722`.
Use write with response. The three payloads are exactly `TAP`, `CW`, `CCW` in UTF-8; no newline/JSON/prepared or fragmented writes.
