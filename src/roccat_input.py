"""Read key-down events from the selected Roccat keyboard without grabbing it.

No text is decoded, stored or logged. Native evdev works on Wayland and X11.
"""
import os
import struct
import sys
from pathlib import Path

EVENT = struct.Struct("@llHHi")


def is_key_press(data: bytes) -> bool:
    return any(kind == 1 and value == 1
               for _, _, kind, code, value in EVENT.iter_unpack(data))


class KeyPressReader:
    def __init__(self, group):
        self.fds = []
        if not sys.platform.startswith("linux"):
            raise OSError("Light by Push needs Linux evdev")
        if not group.get("physical_id"):
            raise OSError("Cannot identify the selected keyboard's physical input device")
        try:
            for entry in Path("/sys/class/input").glob("event*"):
                device = entry / "device"
                try:
                    vendor = int((device / "id/vendor").read_text().strip(), 16)
                    product = int((device / "id/product").read_text().strip(), 16)
                except (OSError, ValueError):
                    continue
                if (vendor, product) != (group["vendor_id"], group["product_id"]):
                    continue
                identity = group.get("physical_id")
                if identity and identity not in [p.name for p in device.resolve().parents]:
                    serial = (device / "uniq").read_text().strip()
                    if serial != identity:
                        continue
                self.fds.append(os.open("/dev/input/" + entry.name, os.O_RDONLY | os.O_NONBLOCK))
            if not self.fds:
                raise OSError("No input interface for the selected Vulcan was found")
        except OSError as exc:
            self.close()
            raise OSError(f"Light by Push: {exc}. Install host udev rules, reconnect the keyboard, "
                          "and allow device access in Flatpak.") from exc

    def pressed(self):
        pressed = False
        for fd in self.fds:
            for _ in range(8):
                try:
                    data = os.read(fd, EVENT.size * 64)
                except BlockingIOError:
                    break
                if not data:
                    raise OSError("Keyboard disconnected")
                pressed = is_key_press(data) or pressed
        return pressed

    def close(self):
        for fd in self.fds:
            os.close(fd)
        self.fds.clear()
