# Waveshare 3.97-inch black/white driver

These are unchanged manufacturer files from the official [Waveshare e-Paper repository](https://github.com/waveshareteam/e-Paper/tree/86aa9932f471a50157cf02fafadc2c1b4a965449/E-paper_Separate_Program/3in97_e-Paper/RaspberryPi_JetsonNano/python/lib/waveshare_epd).

The selected hardware is the [3.97-inch black/white SPI e-Paper HAT+](https://www.waveshare.com/wiki/3.97inch_e-Paper_HAT%2B_Manual), 800×480. The `(G)` four-color variant uses a different driver and is not selected here.

`provenance.json` records the upstream commit, file URLs and SHA-256 values. Manufacturer authorization notices remain in the original files. Inklite calls `EPD.init`, `getbuffer`, `display` and `sleep`. The adapter subclasses only `ReadBusy` to add a timeout for a disconnected/miswired screen; it does not replace register commands, SPI transport, pixel packing or refresh logic.

`epdconfig.py` uses `gpiozero` and `spidev` on Raspberry Pi. Install those through Raspberry Pi OS packages and use a venv with `--system-site-packages`. Hardware imports are never needed for mock rendering.
