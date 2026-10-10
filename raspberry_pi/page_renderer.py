"""Generate a real 1-bit frame from an immutable UI snapshot and page BMP assets."""
from PIL import Image, ImageDraw, ImageFont


def font(size):
    return ImageFont.load_default(size=max(10, int(size)))


def create_page_asset(page, size=(800, 480)):
    image = Image.new("1", size, 1)
    draw = ImageDraw.Draw(image)
    width, height = size
    # Sparse page-specific marks; title, navigation and live state are added by PageRenderer.
    cx, cy = int(width * 0.84), int(height * 0.40)
    radius = int(min(size) * 0.105)
    if page == "home":
        draw.rectangle((cx - 18, cy - radius, cx + 18, cy + radius), fill=0)
    elif page == "focus":
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=0, width=5)
        draw.ellipse((cx - 10, cy - 10, cx + 10, cy + 10), fill=0)
    elif page == "timer":
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=0, width=5)
        draw.line((cx, cy - radius + 12, cx, cy, cx + radius // 2, cy), fill=0, width=5)
    else:
        for i in range(3):
            x = cx - radius + i * radius
            draw.rectangle((x, cy - radius * (i + 1) // 3, x + radius // 2, cy + radius), fill=0)
    return image


class PageRenderer:
    def __init__(self, config):
        self.config = config
        self.assets = {}
        for page in config.pages:
            path = config.assets_path / (page + ".bmp")
            if not path.is_file():
                raise FileNotFoundError(f"Missing bitmap asset: {path}. Run python -m tools.generate_assets after changing PAGES.")
            with Image.open(path) as image:
                self.assets[page] = image.convert("1").resize((config.width, config.height), Image.Resampling.NEAREST)

    def render(self, state):
        image = self.assets[state.page].copy()
        draw = ImageDraw.Draw(image)
        width, height = image.size
        margin = int(width * 0.06)
        small = font(height * 0.040)
        body = font(height * 0.051)
        title = font(height * 0.16)
        text = state.page.replace("_", " ").upper()
        while draw.textlength(text, font=title) > width * 0.66 and title.size > 10:
            title = font(title.size - 2)
        draw.text((margin, height * 0.06), "INKLITE", font=font(height * 0.055), fill=0)
        draw.text((width * 0.70, height * 0.07), f"{state.index + 1} / {len(state.pages)}", font=small, fill=0)
        draw.line((margin, height * 0.16, width - margin, height * 0.16), fill=0, width=2)
        draw.text((margin, height * 0.24), text, font=title, fill=0)
        if state.page == "focus":
            detail = "Focus active" if state.focus_active else "Focus idle"
            hint = "TAP to toggle focus" if state.entered else "TAP to enter"
        elif state.page == "timer":
            detail = f"{state.timer_minutes_left} MIN  /  {state.timer_state.upper()}"
            hint = {"ready": "TAP to start", "running": "TAP to pause", "paused": "TAP to resume", "done": "TAP for a new timer"}[state.timer_state] if state.entered else "TAP to enter"
        elif state.page == "status":
            detail = f"Inputs: {state.received_count}   Last: {state.last_command}"
            hint = f"Confirmations: {state.confirmations}"
        else:
            detail = "Less noise. More room."
            hint = "TAP to confirm" if state.entered else "TAP to enter"
        draw.text((margin, height * 0.48), detail, font=body, fill=0)
        draw.text((margin, height * 0.57), hint, font=small, fill=0)
        mode = "ENTERED" if state.entered else "BROWSE"
        draw.text((margin, height * 0.69), f"{mode}  /  CW next  /  CCW {'return' if state.entered else 'previous'}", font=small, fill=0)
        tab_width = (width - margin * 2) / len(state.pages)
        y = int(height * 0.82)
        for i, page in enumerate(state.pages):
            x = int(margin + i * tab_width)
            tab_font = font(height * 0.038)
            label = page.replace("_", " ").upper()
            while draw.textlength(label, font=tab_font) > tab_width - 12 and tab_font.size > 10:
                tab_font = font(tab_font.size - 1)
            selected = i == state.index
            if selected:
                draw.rectangle((x, y, int(x + tab_width - 6), y + int(height * 0.085)), fill=0)
            draw.text((x + 8, y + 10), label, font=tab_font, fill=1 if selected else 0)
        return image
