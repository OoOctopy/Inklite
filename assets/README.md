# Monochrome display assets

`home.bmp`, `focus.bmp`, `timer.bmp` and `status.bmp` are real 800×480, 1-bit BMP files. They contain sparse page-specific graphics. `PageRenderer` loads them, resizes/converts them as needed and adds the actual page title, mode, focus/timer state and command counters.

After editing `PAGES`, `WIDTH` or `HEIGHT` in the Pi config, regenerate assets from the repository root:

```text
python -m tools.generate_assets
```

The bundled assets match the confirmed Waveshare 3.97-inch black/white screen. Custom page identifiers are supported; enter/confirm still works for those pages. Page-specific actions for `focus` and `timer` are implemented in `ui_state.py`.
