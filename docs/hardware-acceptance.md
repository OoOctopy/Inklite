# Final physical acceptance checklist

Software tests/builds are recorded in [verification.md](verification.md). Complete these on the intended phone/Pi/screen; results have not been filled in as passing.

| Test | Expected result | Result |
| --- | --- | --- |
| ADB device authorization/selection | Correct phone selected; disconnect/reconnect recovers | Not yet tested |
| Foreground app | WeChat/other exact package changes logged once | Not yet tested |
| Allowed app | Remains usable | Not yet tested |
| Unlisted app | Force-stopped; installed Inklite interface opens | Not yet tested |
| Camera permission | Grant/deny/retry works; denial leaves TAP usable | Not yet tested |
| Rear preview/landmarks | Rear lens, 21 tracking points, absent/two-hand suppression | Not yet tested |
| CW / CCW | Calibrated directions generate one correct command | Not yet tested |
| Rotation noise | Small jitter/continuous rotation does not duplicate commands | Not yet tested |
| Volume key | Chosen key produces TAP once; unchosen key remains normal | Not yet tested |
| Manual BLE test | All three UTF-8 writes appear on Pi | Not yet tested |
| Real-input BLE | Volume/rotation route to the same receiver | Not yet tested |
| Link loss/reconnect | Visible failure; stale commands are not replayed | Not yet tested |
| UI navigation | CW next, CCW return/previous, TAP enter/confirm | Not yet tested |
| Focus / timer | Local focus indicator toggles; timer starts/pauses/resumes/completes | Not yet tested |
| Mock output | PNG follows actual state and counters | Not yet tested on Pi |
| Standalone SPI | Home bitmap appears using official black/white driver | Not yet tested |
| Combined physical output | BLE state transitions cause visible e-paper refresh | Not yet tested |
| Exit/reboot service | BLE unregisters, display sleeps, optional service restarts | Not yet tested |

Use [Windows tests](windows-testing.md), [Android tests](android-testing.md), [BLE tests](ble-testing.md) and [Pi setup](raspberry-pi-setup.md) in that order. Grant camera/Bluetooth permissions and review essential package names before enabling ADB enforcement.
