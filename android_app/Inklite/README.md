# Inklite Android

Version: **1.0.0-prototype**, package/activity `com.inklite.app/.MainActivity`.

The app combines rear CameraX preview, MediaPipe hand landmarks, custom temporal CW/CCW, configurable physical volume TAP and a separate BLE GATT client. The stable camera/gesture/input modules remain unchanged from Phase 4–7. The hand model and official Gradle Wrapper are included.

`ble/BleConfig.kt` centralizes UUIDs/timeouts; `BleCommandSender.kt` handles scanning, discovery and serialized writes. Commands are dropped when disconnected and are never replayed after unknown outcomes. Normal inputs are active only in the foreground. A ready connection is retained across app switching, then closed on activity destruction/explicit disconnect/error. `singleTask` allows ADB redirects to reuse the interface.

Runtime permissions: Camera; Nearby Devices on Android 12+; Location for legacy Android 8–11 BLE scans. Internet is not requested. Manual TAP/CW/CCW controls exist only in debug builds and are labelled as developer protocol tests.

Build with JDK 17, SDK 35 and Build Tools 35.0.0:

```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --console=plain
```

On Unix, run `chmod +x gradlew` and use `./gradlew`. The APK is under `app/build/outputs/apk/debug`.

See [Android acceptance](../../docs/android-testing.md), [BLE acceptance](../../docs/ble-testing.md), [dependency provenance](../../THIRD_PARTY_NOTICES.md) and [verification](../../docs/verification.md). Camera settings live in `camera/CameraConfig.kt`, thresholds in `gesture/GestureConfig.kt`, and volume defaults in `input/InputConfig.kt`.
