# Android acceptance tests — input and BLE

## Build prerequisites

Open `android_app/Inklite` (the folder containing `settings.gradle.kts`) in Android Studio. Install Android SDK Platform 35 and Build Tools 35.0.0 in SDK Manager. Select a Gradle JDK 17. The checked-in wrapper pins Gradle 8.11.1; AGP is 8.9.2 and Kotlin is 2.1.20. SDK paths belong only in ignored `local.properties`, which Android Studio can generate.

From a PowerShell terminal inside that folder:

```powershell
.\gradlew.bat :app:assembleDebug --console=plain
```

The output APK will be `app/build/outputs/apk/debug/app-debug.apk`. Use Android Studio Run on a connected physical Android 8+ phone, or install it through authorized ADB:

```powershell
adb install -r app/build/outputs/apk/debug/app-debug.apk
adb shell am start -n com.inklite.app/.MainActivity
adb logcat -s Inklite
```

Alternatively, install the delivered final `Inklite-1.0.0-prototype-debug.apk` without rebuilding. Open a terminal in the folder containing that APK:

```powershell
adb install -r Inklite-1.0.0-prototype-debug.apk
adb shell am start -n com.inklite.app/.MainActivity
adb logcat -s Inklite
```

When several devices are connected, use `adb -s SERIAL ...`. Run acceptance tests first without ADB enforcement so that permission dialogs/system apps can operate normally. Once this APK is installed, the original default ADB redirect component is the correct Inklite target.

## Phase 4: rear-camera preview

Grant Camera permission. Expected Logcat:

```text
[CAMERA] Rear preview bound
```

Confirm the preview actually uses the rear camera. Deny permission and tap the retry button: the app should explain the missing permission without crashing. If Android no longer shows the prompt, grant Camera under the app's system settings and return to retry. Leave/return to the app and rotate the phone; the camera must resume/rebind correctly.

Camera preview acceptance requires a physical phone and is not established by compilation alone.

## Phase 5: hand landmarks first

Leave **Enable CW / CCW recognition** unchecked on the first launch. Show one hand with good lighting and the index finger extended. The diagnostics panel is separate from the camera preview and preserves the processed image's aspect ratio; it is not an overlay registered to the preview crop. It should draw 21 landmarks, with fingertip 8 highlighted. Move the hand/fingers and confirm the skeleton follows them.

Expected Logcat:

```text
[LANDMARKS] Model initialized (CPU / VIDEO)
[LANDMARKS] Hands: 1; points per hand: 21
```

Remove the hand: expect `Hands: 0; points per hand: 0`. Show two hands: the app requests one hand and suppresses rotation recognition. Physical TAP remains independent. No camera frames are saved or uploaded; the app declares no Internet permission.

The analyzer uses synchronous `detectForVideo` on a single background executor with increasing uptime timestamps. CameraX keeps only the latest waiting frame. The analyzer always closes the ImageProxy; native initialization and shutdown occur on the same worker. Rotate the phone and leave/return to the app to check that the old camera/model instance is released and no stale commands are emitted.

## Phase 6: CW and CCW

Enable rotational recognition. Keep one visible hand in frame, extending the index finger. Rotate the hand/wrist so the index tip moves angularly around the palm center **in the camera image plane**. Moving the whole hand in a circle while keeping its pose unchanged does not rotate the fingertip relative to the palm and should not trigger.

Start with a smooth 140–180-degree rotation over roughly 0.5–1.5 seconds. Pause at the end before repeating. Avoid rotating out of the image plane or obscuring the hand. The initial threshold is 120 degrees; enough valid samples and trajectory are also required.

Expected clockwise output:

```text
[GESTURE] ROTATE_CW
[COMMAND] CW
```

Expected counter-clockwise output:

```text
[GESTURE] ROTATE_CCW
[COMMAND] CCW
```

Direction is defined in the processed image (x right, y down). If your intended physical clockwise gesture produces CCW, use **Reverse rotation direction** and repeat both directions. That choice persists across launches. Rear camera remains the default; front camera testing requires editing `CameraConfig.USE_FRONT_CAMERA_FOR_TESTING` and rebuilding.

Verify that 5–20-degree jitter produces no command; a continuous rotation produces only one command. Pause to rearm the next gesture. Tracking loss, hand changes, multiple hands, implausible frame jumps and old history reset accumulated motion. Cooldown survives tracking loss. Turning recognition off must suppress camera commands immediately; volume TAP must continue.

Important initial values in `gesture/GestureConfig.kt`:

| Setting | Initial value |
| --- | --- |
| rotationThresholdDegrees | 120 |
| historyWindowMs / historySize | 1600 ms / 60 samples |
| minimumSamples / minimumDurationMs | 8 / 250 ms |
| minimumMovementRadius | 0.045 |
| minimumTrajectoryLength | 0.22 |
| smoothingAlpha / noiseDegrees | 0.65 / 1 degree |
| directionConsistency | 0.82 |
| maximumStepDegrees / maximumFrameGapMs | 45 degrees / 300 ms |
| maximumPalmJump | 0.35 |
| cooldownMs / rearmQuietMs | 900 ms / 250 ms |
| rearmQuietDegrees | 6 degrees |

Radius, path length and palm jump are measured as fractions of the shorter image dimension. Aspect ratio is corrected before atan2. Tune one threshold at a time, rebuild and rerun both directions plus the jitter test. If the phone processes fewer than roughly 4–5 frames/second, frame-gap/sample/window settings may require tuning; synthetic tests do not establish recognition reliability on a specific phone.

## Phase 7: physical TAP

Select both volume buttons, volume up only or volume down only. Press the configured physical key while Inklite is foreground and focused.

```text
[INPUT] Volume key detected
[COMMAND] TAP
```

The screen displays the last command. Hold the configured key: expect one TAP, not repeated confirmations. Release and press again: expect another TAP. The selected key's down and up events are consumed, so they do not change audio volume while Inklite is active. An unselected volume key retains normal behavior. Non-volume keys retain normal Android behavior.

Disable rotational recognition, remove the hand, or deny Camera permission: volume TAP should still work. Leave Inklite: normal system volume behavior should return. There is no pinch or camera TAP implementation.

## Automated checks and full acceptance

```powershell
.\gradlew.bat :app:assembleDebug :app:testDebugUnitTest :app:lintDebug --console=plain
```

Expected successful result: `BUILD SUCCESSFUL`. Kotlin tests cover direction, ±PI crossing, aspect ratio, jitter, minimum radius/path, consistency, history expiry, missing hands, frame gaps, handedness changes, cooldown/rearm, command mapping and physical key repeats/debounce/modes. These tests do not run the actual camera or native MediaPipe model.

- [ ] APK builds and installs on the intended Android phone.
- [ ] Rear preview works; permission denial/retry is usable.
- [ ] One hand produces 21 matching landmarks; absent/two hands do not cause rotation commands.
- [ ] CW and CCW produce the correct command after direction calibration.
- [ ] Small jitter and continuous rotation do not generate repeated commands.
- [ ] Configured volume key produces one TAP per press, including with camera disabled.
- [ ] App background/resume and device rotation release/restart processing safely.
- [ ] ADB `am start -n com.inklite.app/.MainActivity` opens this application.

Input logic remains the Phase 4–7 implementation. BLE, Pi UI and e-paper adapters are now implemented; continue with [BLE tests](ble-testing.md) and [Pi/display tests](raspberry-pi-setup.md).
