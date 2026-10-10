# Third-party assets and dependency provenance

## Waveshare 3.97-inch SPI driver

The files under `third_party/waveshare_3in97/lib/waveshare_epd` are unchanged official Waveshare files from commit `86aa9932f471a50157cf02fafadc2c1b4a965449`. Original permission/copyright notices are retained; `provenance.json` lists the source URLs and SHA-256 values. Git attributes preserve their original bytes across platforms. See the [driver README](third_party/waveshare_3in97/README.md) and [official hardware manual](https://www.waveshare.com/wiki/3.97inch_e-Paper_HAT%2B_Manual).

The application uses the manufacturer's SPI and buffer code. A subclass bounds the existing BUSY-high polling loop; the vendor files themselves are not modified.

## Python runtime dependencies

The Pi requirements pin [dbus-next 0.2.3](https://python-dbus-next.readthedocs.io/en/latest/) and [Pillow 11.3.0](https://pillow.readthedocs.io/). Both are installed dependencies, not modified/vendored library code. GPIO/SPI support comes from Raspberry Pi OS packages required by the manufacturer driver.

## MediaPipe Hand Landmarker model

The unchanged task bundle at `android_app/Inklite/app/src/main/assets/hand_landmarker.task` was downloaded from Google's [official model storage, model version 1](https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task).

- SHA-256: `fbc2a30080c3c557093b5ddfc334698132eb341044ccee322ccf8bcf3607cde1`
- Size: 7,819,105 bytes.
- [Official task/model documentation](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker).
- [MediaPipe upstream project and license](https://github.com/google-ai-edge/mediapipe).

The task predicts hand landmarks. Inklite's custom Kotlin trajectory detector determines CW/CCW; it does not use MediaPipe Gesture Recognizer or infer TAP.

## Gradle Wrapper

The wrapper scripts and JAR are unchanged files from [Gradle v8.11.1](https://github.com/gradle/gradle/tree/v8.11.1). Gradle is licensed under Apache License 2.0; see `licenses/Apache-2.0.txt` and the scripts' original notices.

- Wrapper JAR SHA-256: `2db75c40782f5e8ba1fc278a5574bab070adccb2d21ca5a6e5ed840888448046`.
- Distribution SHA-256: `f397b287023acdba1e9f6fc5ea72d22dd63669d59ed4a289a29b1a76eee151c6` (also enforced in wrapper properties).

## Pinned Android dependencies

AGP 8.9.2 / Gradle 8.11.1 / JDK 17 / SDK 35 follow the [official AGP compatibility table](https://developer.android.com/build/releases/agp-8-9-0-release-notes). Kotlin 2.1.20 is documented in [Kotlin release notes](https://kotlinlang.org/docs/whatsnew2120.html). CameraX 1.4.2 is listed in the [AndroidX release notes](https://developer.android.com/jetpack/androidx/releases/camera). MediaPipe Tasks Vision 0.10.35 is a fixed release published in [Google Maven](https://dl.google.com/dl/android/maven2/com/google/mediapipe/tasks-vision/0.10.35/tasks-vision-0.10.35.pom); the app uses the [documented Hand Landmarker API](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/android). Dependencies are resolved through Google Maven and Maven Central, with their upstream licenses.
