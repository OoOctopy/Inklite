# Inklite：只测试手机相关部分

你需要 Android 8 或以上的手机。只检查相机、手势和音量键时，安装 APK 就够了；检查 ADB 监控/限制时，再连接 Windows 电脑。无需树莓派或墨水屏，也不需要安装树莓派的 Python 依赖。

## 1. 安装 APK

可以把 `Inklite-1.0.0-prototype-debug.apk` 传到手机直接安装。若使用 ADB，在 APK 所在目录运行：

```powershell
adb devices -l
adb install -r Inklite-1.0.0-prototype-debug.apk
adb shell am start -n com.inklite.app/.MainActivity
```

用 ADB 时，开启 USB 调试并在手机上允许电脑访问。设备应显示 `device`；多个设备时使用 `adb -s 序列号 ...`。

## 2. 音量键 TAP（先测这个）

打开 Inklite，在“Volume key for TAP”选择两个键、上键或下键。先不连接 BLE，也可以不允许相机。

- 按所选音量键：屏幕的“Last input”应显示 `TAP · Confirm / Enter`。
- 长按：应只有一次 TAP；松开后再按才产生下一次。
- 选择仅上键时，下键应正常调整音量，反之亦然。
- 离开 Inklite 后，音量键应恢复系统行为。

若查看日志，另开电脑终端：

```powershell
adb logcat -s Inklite
```

预期：

```text
[INPUT] Volume key detected
[COMMAND] TAP
[BLE] Not connected; dropped: TAP
```

最后一行只表示没有 BLE 接收端，**不代表按键识别失败**。当前要验证的是前两行及手机上的 Last input。TAP 在手机界面表示识别出的命令；树莓派页面的实际“进入/确认”不在这次测试范围内。

## 3. 后置相机和手部关键点

允许相机权限，先保持“Enable CW / CCW recognition”未勾选。

- 确认画面来自后置摄像头。
- 光线充足时，伸出食指、展示一只手。下方独立的关键点面板应显示 21 个点，食指尖有突出标记。
- 移动手指，确认骨架跟随；移开手应显示未检测到手。
- 展示两只手时，应提示只展示一只，旋转命令不应触发。
- 拒绝相机权限、重试、切到其他 App 后返回、横竖屏切换，都不应崩溃。相机拒绝时 TAP 仍可使用。

预期日志：

```text
[CAMERA] Rear preview bound
[LANDMARKS] Model initialized (CPU / VIDEO)
[LANDMARKS] Hands: 1; points per hand: 21
```

关键点面板与预览分开显示，不是叠在相机画面上的校准标记。

## 4. CW / CCW

关键点稳定后，开启旋转识别。让食指尖相对掌心在相机画面平面内旋转；先尝试约 140–180 度、0.5–1.5 秒的平滑手腕旋转，每次结束停顿一下。

整体平移一只姿势不变的手去画圆，不会改变食指尖相对掌心的角度，因此可能不会触发。

预期顺时针：

```text
[GESTURE] ROTATE_CW
[COMMAND] CW
```

预期逆时针：

```text
[GESTURE] ROTATE_CCW
[COMMAND] CCW
```

手机 Last input 应同步显示 CW 或 CCW。方向相反时，勾选“Reverse rotation direction”。少量抖动不应产生命令；持续旋转不应反复触发；关闭识别后应不再产生相机命令，但音量 TAP 应继续工作。

没有树莓派时，同样会出现 `[BLE] Not connected; dropped: CW/CCW`，这是预期状态。

## 5. ADB 前台 App 识别（需要电脑）

安装 [Android 官方 Platform Tools](https://developer.android.com/tools/releases/platform-tools)，把包含 `adb.exe` 的文件夹加入 PATH。安装 Python 3.10+。

解压手机专用源码包，用 VS Code 打开里面的 `Inklite-Phone` 文件夹。从该目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m adb_control.app_monitor
```

打开微信与其他 App，预期日志随前台应用变化：

```text
[INKLITE] Foreground App: com.tencent.mm (user 0)
```

同一个 App 停留时不应重复打印。拔线应产生重试提示，程序继续运行；接回并授权后应恢复。这个模式不会停止应用。

## 6. 白名单、停止 App 和跳转

先完成相机授权；本次不需要开启 BLE。检查 `adb_control/whitelist.json`，加入你手机的必要应用包名（桌面、拨号、短信、设置、系统权限界面等）。默认 Inklite 包名/activity 与 APK 一致，不需要改。

在正常前台识别已通过后，按 Ctrl+C 停止监控，再运行：

```powershell
.\.venv\Scripts\python.exe -m adb_control.app_monitor --enforce
```

- 打开白名单 App：应保持运行。
- 打开一个没有未保存内容的非必要、非白名单 App：应被停止，并打开 Inklite。

预期：

```text
[INKLITE] Blocked App: <package>
[INKLITE] Force stopping...
[INKLITE] Opening Inklite...
```

按 Ctrl+C 停止限制。该功能来自电脑的授权 ADB，不是普通 Android App 自身获得了停止其他 App 的权限。

## 7. BLE 这次只做基本检查（可跳过）

可以按“Find and connect to Inklite Pi”，检查 Nearby Devices 权限提示、蓝牙开启提示和约 15 秒后的“未找到设备”信息。Android 8–11 还需定位权限/系统定位开关用于 BLE 扫描。

**没有接收端时无法验证 BLE 连接、写入成功或树莓派收到命令。** 不必按开发 BLE 测试按钮；它们在未连接时会禁用。手机本地 TAP/CW/CCW 识别不依赖这些按钮。

## 手机测试记录

| 项目 | 你记录的结果 |
| --- | --- |
| 安装、打开、无崩溃 | 待测 |
| 音量键 TAP、长按不重复 | 待测 |
| 后置相机、21 个关键点 | 待测 |
| CW / CCW 与方向校准 | 待测 |
| 小抖动、连续旋转与关闭识别 | 待测 |
| 相机拒绝、后台返回、屏幕旋转 | 待测 |
| ADB 前台 App 识别、断线恢复 | 待测 |
| 白名单允许、非白名单停止与跳转 | 待测 |

发生问题时，记录手机型号、Android 版本、失败步骤，并保留对应 Logcat/ADB 日志。当前不需要检测树莓派、SPI 或电子墨水屏。
