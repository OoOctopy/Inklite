# Inklite 实机检测：从这里开始

代码已完成到 Phase 14。你需要最后确认手机、BLE 和屏幕在真实硬件上都能正常运行；软件测试不等于实机验收。

## 1. 手机安装

完整源码内已包含 `apk/Inklite-1.0.0-prototype-debug.apk`；下面的安装命令在 `apk` 文件夹中运行。

连接手机，开启 USB 调试并允许电脑访问。电脑装好 ADB 后，在最终 APK 所在目录运行：

```powershell
adb devices -l
adb install -r Inklite-1.0.0-prototype-debug.apk
adb shell am start -n com.inklite.app/.MainActivity
adb logcat -s Inklite
```

允许相机权限。先不勾选旋转识别，确认后置预览和 21 个关键点正常；再开启 CW/CCW。如果方向相反，勾选方向反转。音量键可选上、下或两个键，长按应只产生一次 TAP。

## 2. 电脑上的 ADB 限制

用 VS Code 打开源码中的 `Inklite-System-Prototype` 文件夹。从仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m adb_control.app_monitor
```

打开微信和其他 App，确认终端显示正确包名。然后编辑 `adb_control/whitelist.json`，加入你手机实际使用的拨号、短信、桌面、设置等必要应用。先完成相机和蓝牙授权，再启用限制：

```powershell
.\.venv\Scripts\python.exe -m adb_control.app_monitor --enforce
```

白名单外 App 应被停止并打开 Inklite。默认跳转配置已经与 APK 一致。多个设备时加 `--serial 手机序列号`。详细步骤见 [Windows 测试](windows-testing.md)。

## 3. 树莓派安装与 BLE

把完整源码放到 Raspberry Pi 4，在仓库根目录安装：

```bash
sudo apt update
sudo apt install -y bluez python3-venv python3-pip python3-gpiozero python3-spidev python3-lgpio
sudo raspi-config nonint do_spi 0
sudo systemctl enable --now bluetooth
sudo bluetoothctl power on
python3 -m venv --system-site-packages .venv
.venv/bin/python -m pip install -r raspberry_pi/requirements.txt
```

先跑完整的本地模拟，不需要手机或屏幕：

```bash
.venv/bin/python -m raspberry_pi.ble_receiver --dry-run
```

`work/mock_display/current.png` 会显示最后的界面。然后运行真实 BLE、模拟屏幕：

```bash
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display mock
```

在手机点击“Find and connect to Inklite Pi”，允许蓝牙权限。Android 8–11 还要允许定位并开启系统定位服务以便扫描，应用不读取位置。连接成功后先按开发测试面板的 TAP/CW/CCW，确认树莓派能收到，再试音量键和旋转手势。

## 4. 微雪 3.97 黑白屏

已匹配 `epd3in97` 官方驱动，分辨率为 800×480，驱动文件已随源码提供。先停掉上一步的程序，断电接好 HAT/线缆；引脚见 [树莓派与屏幕指南](raspberry-pi-setup.md)。

先单测屏幕：

```bash
sudo .venv/bin/python -m raspberry_pi.display_controller --mode hardware --page home
```

确认 Home 页面正常后，再运行完整链路：

```bash
sudo .venv/bin/python -m raspberry_pi.ble_receiver --display hardware
```

按键/手势应让树莓派界面和屏幕变化。全刷有延迟；快速输入时软件会保留最新界面，避免阻塞 BLE。不要同时运行两个控制屏幕的进程。

## 5. 页面操作

- CW：下一页。
- CCW：已进入页面时返回；否则上一页。
- TAP：第一次进入，再次确认。
- Focus：进入后 TAP 切换本地专注指示；电脑白名单控制独立运行。
- Timer：进入后 TAP 开始，之后暂停/继续；默认 25 分钟，显示按分钟更新。
- Status：显示实际收到的命令和确认次数。

验收完在 [硬件检查表](hardware-acceptance.md) 记录结果。遇到问题，保留手机 Logcat 和树莓派终端的对应日志，便于定位相机、BLE、状态或屏幕哪一段出错。
