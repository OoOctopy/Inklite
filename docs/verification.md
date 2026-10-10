# Verification records

## Final software checkpoint — Phase 1–14, 2026-10-09

**Software implementation is complete. Physical acceptance is intentionally left for the hardware owner.** Earlier sections below are historical checkpoints, not the current feature scope.

| Check | Result |
| --- | --- |
| ADB suite | **22 tests passed** |
| Android suite | **28 tests passed**: 17 gestures, 6 physical-input mapping, 5 BLE queue/protocol/permission tests |
| Pi/UI/display suite | **40 tests passed** |
| Android build | `assembleDebug`, `testDebugUnitTest`, `lintDebug` completed with **BUILD SUCCESSFUL** |
| Lint | **0 errors**, 8 warnings: 5 dependency-update notices, 2 inlined permission-string API notices, 1 version-specific manifest attribute notice |
| Python imports/syntax | `compileall` succeeded for ADB, Pi, tools and the bundled manufacturer files |
| Local full pipeline | Dry-run parsed CW/TAP/TAP, selected/entered Focus, enabled the actual local focus state and wrote a real 800×480 monochrome PNG |
| UI/timer | Navigation/return, immutable snapshots, real counters, focus toggle, monotonic start/pause/resume/completion and minute refresh were tested |
| D-Bus | Actual interface signatures and object tree validated; simulated registration, failure rollback, stop, BlueZ restart and advertisement release tested |
| Display | Valid BMP/PNG output, serial latest-state coalescing, error propagation, driver calls/rotation/buffer length and BUSY timeout tested |
| Manufacturer | Three unchanged Waveshare files pinned to commit `86aa9932f471a50157cf02fafadc2c1b4a965449`; hashes verified; real vendor `getbuffer` tested with GPIO access stubbed |
| Existing input code | **19 ADB/camera/gesture/input source and test files** are byte-identical to the Phase 1–7 source archive |
| APK | Version `1.0.0-prototype`, package `com.inklite.app`, signature scheme v2 verified; model asset hash verified |
| Permissions | Camera, legacy Bluetooth/Location through SDK 30, modern Scan/Connect, internal AndroidX receiver; **no Internet permission** |
| Documentation/package | Local links validated; source excludes builds/caches/keystores/personal configuration; CI and optional Pi service supplied |

The inlined permission constants are literal strings used by a helper that selects the correct list for the actual SDK version. The `neverForLocation` manifest attribute intentionally applies only to API 31+. These warnings are non-blocking version-analysis hints. The BLE class has a narrowly explained MissingPermission Lint annotation because grants cross asynchronous callbacks; runtime entry checks and revocation/error handling are present. Dependency versions remain fixed to the tested SDK 35/JDK 17 combination.

The final debug APK is 58,317,587 bytes, SHA-256 `b95a9364a414f10fa2eae950718fa2e9440b90518e1da0d5a7ce533ab6ffdd67`.

**Not verified here:** actual phone camera/physical keys, Android-to-Pi BLE radio, Linux BlueZ registration on a live adapter, SPI wiring/refresh or boot-service execution. Mock/fake-bus/GPIO-stub tests are not represented as hardware success. GitHub CI is supplied but has not been run in a hosted repository. Complete [the hardware checklist](hardware-acceptance.md) using [the Chinese guide](START_HERE_ZH.md).

Workspace-only tools handled Windows path/loopback constraints and intermittent public-repository TLS downloads. Those personal paths/tool settings are not included in the project. The system remains a functional prototype, with production authentication, release signing and persistence explicitly outside its scope.

## Phase 4–7 — 2026-10-09

The Android implementation and a clean build were verified. Physical-phone acceptance remains pending.

| Check | Result |
| --- | --- |
| Clean Android build | `:app:clean :app:assembleDebug :app:testDebugUnitTest :app:lintDebug` — **BUILD SUCCESSFUL**, 52 tasks executed |
| Kotlin unit tests | **23 passed**, zero failures/errors: 17 temporal gesture tests and 6 command/volume-key tests |
| Android Lint | **0 errors**; 6 warnings: 5 notices about newer dependency releases and 1 obsolete resource-folder hint |
| APK signature | APK Signature Scheme v2 verified with Android SDK `apksigner` |
| APK identity | `com.inklite.app`, version 0.2.0, minSdk 26, targetSdk 35; launcher `com.inklite.app.MainActivity` |
| Packaged permissions | Camera plus AndroidX's internal receiver permission; **no Internet, network-state or Bluetooth permission** |
| Model asset | Packaged task bundle SHA-256 matches Google's downloaded model; see [provenance](../THIRD_PARTY_NOTICES.md) |
| Existing ADB modules | All 7 files byte-identical to the Phase 1–3 source archive; the original 22 Python tests remain applicable |
| Connected hardware | `adb devices -l` returned an empty device list; no camera, physical key or real app-intervention acceptance was performed |

The dependency versions remain deliberately pinned to the SDK 35/JDK 17 combination that was compiled and tested. Lint's resource-folder hint came from the old empty `mipmap-anydpi-v26` folder left after moving the icon. That empty folder was removed; the delivered source uses `mipmap-anydpi`. No Lint error was suppressed and no baseline was used.

Implemented phase boundaries:

- **Phase 4:** rear CameraX preview, permission handling, lifecycle shutdown/restart and explicit display rotation. APIs compile; actual camera output needs a phone.
- **Phase 5:** CPU Hand Landmarker integration, model packaging, background frame processing and a separate landmark diagnostics panel. Model initialization and real 21-point detection need a phone.
- **Phase 6:** custom temporal CW/CCW detector, angle wrapping, aspect correction, noise/trajectory checks, cooldown and quiet rearming. Synthetic trajectories were tested; real motion reliability is unverified.
- **Phase 7:** public `onKeyDown/onKeyUp` interception, configurable volume keys, repeat/debounce suppression and TAP mapping. Logic was unit-tested; physical key delivery needs a phone.

Build checks found and fixed a restricted AndroidX key-dispatch API use, transitive network permissions, and resource/configuration issues. Windows temporary-path limits and intermittent official-repository TLS failures were handled in workspace-only tooling. A small temporary Maven cache used unchanged official artifacts with upstream hash verification. No machine-specific repository URL, SDK path, keystore or tool installation is included in the source archive.

The final APK SHA-256 is `ee1af49fa5c9a9b9ce6e33379732517744b4578460c34737d22ad24675a97473` (58,270,368 bytes). It is a debug-signed prototype APK. Native debug symbols were left in the provided libraries; this affects file size, not the command mapping.

Follow [Android acceptance tests](android-testing.md) and [ADB phone tests](windows-testing.md) before treating Phase 1–7 as hardware-validated. BLE, Raspberry Pi and display work remain outside this phase.

## Phase 1–3 — 2026-10-07

Scope at this checkpoint: Phase 1–3 only. No hardware acceptance was claimed.

| Phase | Delivered | Verification |
| --- | --- | --- |
| 1 | Repository structure, English README, centralized JSON configuration, whitelist, ignore rules | Configuration/whitelist loading and invalid-input tests passed; README contains setup, commands, expected logs and limitations |
| 2 | ADB wrapper, foreground parser, optional raw usage diagnostics, timeout/device errors and reconnect loop | Parser/device-selection/timeout/recovery tests passed; CLI missing-ADB smoke check returned an actionable error and exit code 1 |
| 3 | Whitelist enforcement, force-stop, destination resolution, redirect and cooldown | Allowed/unknown apps untouched; missing target prevents stop; changing foreground cancels intervention; command order and user-specific arguments tested |

Commands executed from the repository root with the available bundled Python runtime:

```text
python -m unittest discover -s tests -v
Ran 22 tests — OK

python -m compileall -q adb_control tests
Exit code 0

python -m adb_control.app_monitor --once
[INKLITE] Mode: MONITOR ONLY
[INKLITE] ADB not installed/found. Install Platform Tools and set ADB_PATH or PATH.
Exit code 1 (expected in this environment)
```

The first test run hit the execution sandbox's default temporary-directory permissions for two file tests. Rerunning with TEMP/TMP set to the writable workspace scratch directory passed all 22 tests; no product behavior was changed to bypass permissions. A normal local Python installation can run the documented command without that sandbox-specific setup.

No third-party Python imports or dependency installation are required. ADB was not available on PATH in this environment, so no real foreground query, app force-stop or activity redirect was performed. Follow [Windows phone testing](windows-testing.md) for those acceptance checks. Exact Android/OEM dumpsys compatibility is still unverified. Android/CameraX/MediaPipe/BLE/Pi/display implementation is deferred as requested.
