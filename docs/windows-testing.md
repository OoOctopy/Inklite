# Windows + VS Code acceptance tests (Phase 1–3)

## Before testing

1. Open `Inklite-System-Prototype` in VS Code, then Terminal → New Terminal (PowerShell).
2. Install Python 3.10+ and official Android SDK Platform Tools. `python --version` and `adb version` must work. Reopen the terminal after PATH changes.
3. Connect/unlock your phone, enable USB debugging and approve its authorization dialog.
4. Run `adb devices -l`. Record the serial. If multiple phones/emulators are present, pass `--serial SERIAL` to every monitor command. Add `-s SERIAL` before `shell` in the standalone ADB commands below.
5. Create `.venv` using `python -m venv .venv`. Run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.

## Phase 1: configuration and structure

Read `adb_control/config.json` and `whitelist.json`. The sample whitelist needs your phone's actual packages, particularly dialer, messages, launcher and system/permission interfaces. Changes take effect on restart. Inklite's configured package is automatically protected.

Phase 4–7 now includes an Android project. [Build/install it](android-testing.md) to use the default `com.inklite.app/.MainActivity` redirect. For another installed Inklite build, set its actual package/component. To test redirect before installing Inklite, Settings remains an optional temporary target:

```powershell
Copy-Item adb_control/config.json adb_control/config.local.json
adb shell cmd package resolve-activity --brief -a android.settings.SETTINGS
```

The last command should output a component such as `com.android.settings/.Settings`. Copy the actual component into `INKLITE_ACTIVITY` and its package (left of `/`) into `INKLITE_PACKAGE` in `adb_control/config.local.json`. Retain the sample whitelist path, which is relative to that file. Use the installed app for the same Android user/profile being tested. Settings is a temporary test destination; this does not create the Inklite app.

Verify the destination explicitly, using the component you found:

```powershell
adb shell am start -n com.android.settings/.Settings
```

Expected: `Starting: Intent ...`, and Settings opens. If `Error type 3`, use the resolved component for your phone instead.

## Phase 2: foreground detection

```powershell
.\.venv\Scripts\python.exe -m adb_control.app_monitor
```

Open WeChat and another app. Example logs (timestamps omitted):

```text
[INKLITE] Mode: MONITOR ONLY
[ADB] Connected: SERIAL
[INKLITE] Foreground App: com.tencent.mm (user 0)
[INKLITE] Would block: com.tencent.mm (monitor-only)
[INKLITE] Foreground App: com.android.settings (user 0)
```

Keeping the same app open should not repeatedly log its foreground name. WeChat may have a different package for a clone/work profile. Monitor-only never changes app state.

Unplug the cable. Expected: one ADB error followed by retry attempts; the process stays running. Reconnect, unlock and authorize: expect `[ADB] Connected: SERIAL`, foreground logs and recovery. Repeated identical error logs are suppressed.

If no package can be parsed, run these and inspect their foreground records:

```powershell
adb shell dumpsys activity activities
adb shell dumpsys window windows
```

Unsupported formats and ambiguous resumed records cause a skipped intervention. Test full-screen first. Dumpsys can contain personal device/app information; redact it before sharing.

## Phase 3: whitelist, force-stop, redirect

1. Stop monitoring with Ctrl+C.
2. Add an app's exact package to `adb_control/whitelist.json`, then start enforcement using your verified local config:

```powershell
.\.venv\Scripts\python.exe -m adb_control.app_monitor --config adb_control/config.local.json --enforce
```

3. Open that allowed app. Expected: foreground log, app remains usable, no `Blocked App` line.
4. Pick a nonessential app with no unsaved work, remove its package from the whitelist if present, restart enforcement and open it.

Expected:

```text
[INKLITE] Mode: ENFORCE
[ADB] Connected: SERIAL
[INKLITE] Foreground App: com.example.testapp (user 0)
[INKLITE] Blocked App: com.example.testapp
[INKLITE] Force stopping...
[INKLITE] Opening Inklite...
[INKLITE] Foreground App: com.android.settings (user 0)
```

`Opening Inklite...` means opening the configured destination; in this temporary setup it is Settings. Confirm the blocked app closes and the destination appears. Once the real Inklite activity is available, switch the config back and repeat this test to validate the actual Inklite redirect.

If you keep the default missing `com.inklite.app/.MainActivity` target, expect `Redirect activity cannot be resolved ... Install/configure it before --enforce.` The foreground app should not be force-stopped in that case.

Press Ctrl+C to exit; expected `[INKLITE] Stopped`. Apps that were force-stopped can be reopened manually. Force-stop can suspend background work and notifications until the app is restarted.

## Optional statistics

```powershell
.\.venv\Scripts\python.exe -m adb_control.app_monitor --usage-stats
```

Expected: raw Android/OEM usage diagnostics. No portable usage-duration parsing is claimed.

## Acceptance checklist

- [ ] Same foreground app logs once; switching apps logs the correct package.
- [ ] Missing/offline/unauthorized devices produce actionable messages.
- [ ] Multiple devices require selection; selected phone receives commands.
- [ ] Disconnect/reconnect recovers without restarting the process.
- [ ] Allowed app remains running.
- [ ] Unlisted test app is closed; configured destination opens.
- [ ] Missing destination does not force-stop apps.
- [ ] Actual installed Inklite activity opens (build/install the Phase 4–7 Android app first).

Hardware acceptance remains pending until these are performed on your phone. Software through Phase 14 is now present; continue with the Android/BLE/Pi guides.
