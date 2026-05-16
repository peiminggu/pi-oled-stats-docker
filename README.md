# Raspberry Pi OLED Status

Dockerized status display for a Raspberry Pi 5 NAS using a 4-pin I2C SSD1306 OLED module.

The app shows:

- Pi IP address
- CPU usage
- RAM usage
- Disk usage

It supports both `128x32` and `128x64` SSD1306 displays.

## Wiring

Connect the OLED module to the Raspberry Pi GPIO header:

| OLED pin | Raspberry Pi pin |
| --- | --- |
| VCC | 3.3V |
| GND | GND |
| SDA | GPIO 2, physical pin 3 |
| SCL | GPIO 3, physical pin 5 |

## Enable I2C on Raspberry Pi OS

Run:

```sh
sudo raspi-config
```

Then enable `Interface Options` -> `I2C`, reboot, and verify:

```sh
ls /dev/i2c-*
sudo apt-get update
sudo apt-get install -y i2c-tools
i2cdetect -y 1
```

Most SSD1306 modules appear at `0x3C`. Some appear at `0x3D`.

## Find the I2C Address

After I2C is enabled and the OLED is wired, scan bus `1`:

```sh
i2cdetect -y 1
```

Look for a detected value in the grid, such as `3c` or `3d`:

```text
     0 1 2 3 4 5 6 7 8 9 a b c d e f
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
```

If the scan shows `3c`, use:

```yaml
I2C_ADDRESS: "0x3C"
```

If it shows `3d`, use:

```yaml
I2C_ADDRESS: "0x3D"
```

If the scan does not show either address, confirm the OLED wiring, confirm I2C is enabled, and check that `/dev/i2c-1` exists:

```sh
ls /dev/i2c-*
```

## Configure the Display

Edit `docker-compose.yml` if needed:

```yaml
environment:
  DISPLAY_WIDTH: "128"
  DISPLAY_HEIGHT: "64"
  I2C_PORT: "1"
  I2C_ADDRESS: "0x3C"
  DISK_PATH: "/nas"
```

For a `128x32` display, set:

```yaml
DISPLAY_HEIGHT: "32"
```

If your display is detected at `0x3D`, set:

```yaml
I2C_ADDRESS: "0x3D"
```

## Run

Build and start:

```sh
docker compose up -d --build
```

Watch logs:

```sh
docker compose logs -f oled-status
```

Stop:

```sh
docker compose down
```

The service uses `restart: unless-stopped`, so it starts again automatically after reboot.

## Disk Usage

By default the app displays disk usage for `/nas`. If `/nas` does not exist inside the container, it falls back to `/`.

If your NAS storage is mounted somewhere else on the Pi, update both the volume and `DISK_PATH` in `docker-compose.yml`.

Example:

```yaml
volumes:
  - /mnt/storage:/nas:ro
environment:
  DISK_PATH: "/nas"
```

## Troubleshooting

If the display stays blank:

1. Confirm I2C is enabled with `ls /dev/i2c-*`.
2. Confirm the display address with `i2cdetect -y 1`.
3. Confirm `I2C_ADDRESS` matches the detected address.
4. Confirm Docker can access `/dev/i2c-1`.
5. Check logs with `docker compose logs -f oled-status`.

If Docker reports that `/nas` does not exist, create the mount directory or change the volume mapping in `docker-compose.yml`.
