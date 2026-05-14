from __future__ import annotations

import logging
import os
import signal
import socket
import time
from dataclasses import dataclass

import psutil
from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s %(levelname)s %(message)s",
)


@dataclass(frozen=True)
class Settings:
    display_width: int = int(os.getenv("DISPLAY_WIDTH", "128"))
    display_height: int = int(os.getenv("DISPLAY_HEIGHT", "64"))
    i2c_port: int = int(os.getenv("I2C_PORT", "1"))
    i2c_address: int = int(os.getenv("I2C_ADDRESS", "0x3C"), 0)
    refresh_seconds: float = float(os.getenv("REFRESH_SECONDS", "2"))
    disk_path: str = os.getenv("DISK_PATH", "/nas")
    fallback_disk_path: str = os.getenv("FALLBACK_DISK_PATH", "/")
    font_path: str = os.getenv(
        "FONT_PATH",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    )


def get_font(path: str, size: int) -> ImageFont.ImageFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        logging.warning("Could not load font %s; using Pillow default font", path)
        return ImageFont.load_default()


def get_ip_address() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("8.8.8.8", 80))
            ip_address = sock.getsockname()[0]
            if ip_address and not ip_address.startswith("127."):
                return ip_address
    except OSError:
        pass

    for interface_addrs in psutil.net_if_addrs().values():
        for addr in interface_addrs:
            if addr.family == socket.AF_INET and not addr.address.startswith("127."):
                return addr.address

    return "No network"


def get_disk_usage(settings: Settings) -> tuple[str, float]:
    path = (
        settings.disk_path
        if os.path.exists(settings.disk_path)
        else settings.fallback_disk_path
    )
    try:
        return path, psutil.disk_usage(path).percent
    except OSError as exc:
        logging.warning("Could not read disk usage for %s: %s", path, exc)
        return path, 0.0


def read_metrics(settings: Settings) -> dict[str, str | float]:
    disk_path, disk_percent = get_disk_usage(settings)
    return {
        "ip": get_ip_address(),
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "disk": disk_percent,
        "disk_path": disk_path,
    }


def progress_bar(draw, x: int, y: int, width: int, height: int, percent: float) -> None:
    percent = max(0.0, min(100.0, percent))
    draw.rectangle((x, y, x + width, y + height), outline=255, fill=0)
    fill_width = int((width - 2) * (percent / 100.0))
    if fill_width > 0:
        draw.rectangle((x + 1, y + 1, x + 1 + fill_width, y + height - 1), fill=255)


def render_32px(device: ssd1306, font: ImageFont.ImageFont, metrics: dict[str, str | float]) -> None:
    with canvas(device) as draw:
        draw.text((0, 0), f"IP {metrics['ip']}", font=font, fill=255)
        draw.text((0, 8), f"CPU {metrics['cpu']:>5.1f}%", font=font, fill=255)
        draw.text((0, 16), f"RAM {metrics['ram']:>5.1f}%", font=font, fill=255)
        draw.text((0, 24), f"DSK {metrics['disk']:>5.1f}%", font=font, fill=255)


def render_64px(device: ssd1306, font: ImageFont.ImageFont, metrics: dict[str, str | float]) -> None:
    with canvas(device) as draw:
        draw.text((0, 0), f"IP {metrics['ip']}", font=font, fill=255)

        rows = (
            ("CPU", float(metrics["cpu"]), 14),
            ("RAM", float(metrics["ram"]), 30),
            ("DSK", float(metrics["disk"]), 46),
        )
        for label, percent, y in rows:
            draw.text((0, y), f"{label} {percent:>5.1f}%", font=font, fill=255)
            progress_bar(draw, 70, y + 2, 56, 8, percent)


def connect_display(settings: Settings) -> ssd1306:
    logging.info(
        "Opening SSD1306 display: %sx%s on /dev/i2c-%s at 0x%02X",
        settings.display_width,
        settings.display_height,
        settings.i2c_port,
        settings.i2c_address,
    )
    serial = i2c(port=settings.i2c_port, address=settings.i2c_address)
    return ssd1306(serial, width=settings.display_width, height=settings.display_height)


def run() -> None:
    settings = Settings()
    font_size = 8 if settings.display_height <= 32 else 10
    font = get_font(settings.font_path, font_size)
    keep_running = True

    def shutdown(_signum, _frame) -> None:
        nonlocal keep_running
        keep_running = False

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    display = None
    while keep_running:
        try:
            if display is None:
                display = connect_display(settings)
                logging.info("Display connected")

            metrics = read_metrics(settings)
            logging.debug("Metrics: %s", metrics)
            if settings.display_height <= 32:
                render_32px(display, font, metrics)
            else:
                render_64px(display, font, metrics)
            time.sleep(settings.refresh_seconds)
        except Exception:
            logging.exception("Display update failed; retrying in 5 seconds")
            display = None
            time.sleep(5)

    if display is not None:
        display.clear()


if __name__ == "__main__":
    run()
