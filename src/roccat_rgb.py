"""RGB reports for Roccat Kone AIMO and Vulcan AIMO.

Vulcan initialization reports are the software-color sequence from
Simon Huwiler's MIT-licensed roccatvulcan controller (2019):
https://github.com/simonhuwiler/roccatvulcan

Kone AIMO colors use the hidraw feature report published for Linux:
report 0x0d, header 0x0d 0x2e, then 11 LEDs as R,G,B,0x00.
"""

import math
from typing import List, Sequence, Tuple

Color = Tuple[int, int, int]

ROCCAT_VID = 0x1E7D
KONE_AIMO = 0x2E27
VULCAN_100_AIMO = 0x307A
VULCAN_120_AIMO = 0x3098
KONE_LED_COUNT = 11
VULCAN_KEY_COUNT = 144
VULCAN_CTRL_INTERFACE = 1
VULCAN_LED_INTERFACE = 3

KONE_LED_NAMES = (
    "Wheel",
    "Left strip top",
    "Left strip 2",
    "Left strip 3",
    "Left strip bottom",
    "Right strip top",
    "Right strip 2",
    "Right strip 3",
    "Right strip bottom",
    "Lower left",
    "Lower right",
)

PRODUCTS = (
    {"name": "Kone AIMO", "vendor": ROCCAT_VID, "product": KONE_AIMO, "kind": "kone"},
    {"name": "Vulcan 100 AIMO", "vendor": ROCCAT_VID, "product": VULCAN_100_AIMO, "kind": "vulcan"},
    {"name": "Vulcan 120 AIMO", "vendor": ROCCAT_VID, "product": VULCAN_120_AIMO, "kind": "vulcan"},
)

def kind_for_product(product_id: int) -> str:
    for item in PRODUCTS:
        if item["product"] == product_id:
            return item["kind"]
    return "unknown"

def product_name(product_id: int) -> str:
    for item in PRODUCTS:
        if item["product"] == product_id:
            return item["name"]
    return f"Unknown 0x{product_id:04x}"

def clamp_channel(value: int) -> int:
    return max(0, min(255, int(value)))

def scale_color(r: int, g: int, b: int, brightness: int = 255) -> Color:
    factor = clamp_channel(brightness) / 255
    return (
        int(round(clamp_channel(r) * factor)),
        int(round(clamp_channel(g) * factor)),
        int(round(clamp_channel(b) * factor)),
    )

def kone_color_report(colors: Sequence[Color]) -> bytes:
    """46-byte feature report: 0x0d, 0x2e, then 11 times R,G,B,0x00."""
    if len(colors) != KONE_LED_COUNT:
        raise ValueError(f"Kone AIMO expects {KONE_LED_COUNT} LED colors")
    msg = bytearray(46)
    msg[0] = 0x0D
    msg[1] = 0x2E
    for index, (red, green, blue) in enumerate(colors):
        base = 2 + index * 4
        msg[base] = clamp_channel(red)
        msg[base + 1] = clamp_channel(green)
        msg[base + 2] = clamp_channel(blue)
        msg[base + 3] = 0x00
    return bytes(msg)

KONE_INIT_REPORT = bytes([0x0E, 0x06, 0x01, 0x01, 0x00, 0xFF])

def vulcan_color_stream(colors: Sequence[Color]) -> bytes:
    """Header 0xa1 0x01 0x01 0xb4 plus 144 keys in groups of 12 (R, then G, then B)."""
    if len(colors) != VULCAN_KEY_COUNT:
        raise ValueError(f"Vulcan AIMO expects {VULCAN_KEY_COUNT} key colors")
    hw = bytearray(VULCAN_KEY_COUNT * 3)
    for index, (red, green, blue) in enumerate(colors):
        group = index // 12
        offset = (index % 12) + 36 * group
        hw[offset] = clamp_channel(red)
        hw[offset + 12] = clamp_channel(green)
        hw[offset + 24] = clamp_channel(blue)
    return bytes([0xA1, 0x01, 0x01, 0xB4]) + bytes(hw)

def vulcan_led_packets(colors: Sequence[Color]) -> List[bytes]:
    """Seven 65-byte interrupt writes. The first byte of each write is report 0x00."""
    stream = vulcan_color_stream(colors)
    packets = []
    for index in range(7):
        chunk = stream[index * 64:(index + 1) * 64]
        packets.append(bytes([0x00]) + chunk.ljust(64, b"\x00"))
    return packets

EFFECTS = ("pulse", "breathe", "rainbow")
EFFECT_FPS = 12
PULSE_PERIOD = 24
BREATHE_PERIOD = 72
RAINBOW_PERIOD = 96


def _phase(frame: int, period: int, speed: float) -> float:
    rate = max(0.25, min(4.0, float(speed)))
    return (frame * rate / period) % 1.0


def envelope_pulse(phase: float) -> float:
    """Sharp brightness peak once per cycle."""
    wave = 0.5 - 0.5 * math.cos(2 * math.pi * phase)
    return wave ** 6


def envelope_breathe(phase: float) -> float:
    """Smooth fade from dark to bright and back."""
    return 0.5 - 0.5 * math.cos(2 * math.pi * phase)


def hsv_to_rgb(hue: float, value: int) -> Color:
    hue = hue % 1.0
    sector = int(hue * 6) % 6
    fraction = hue * 6 - int(hue * 6)
    level = clamp_channel(value)
    drop = int(round(level * (1 - fraction)))
    rise = int(round(level * fraction))
    table = (
        (level, rise, 0),
        (drop, level, 0),
        (0, level, rise),
        (0, drop, level),
        (rise, 0, level),
        (level, 0, drop),
    )
    return table[sector]


def effect_colors(
    name: str,
    red: int,
    green: int,
    blue: int,
    brightness: int,
    frame: int,
    count: int,
    speed: float = 1.0,
) -> List[Color]:
    """One animation frame for every light on the device."""
    if name not in EFFECTS:
        raise ValueError(f"Unknown effect {name}")
    if count < 1:
        raise ValueError("Effect needs at least one light")
    if name == "rainbow":
        phase = _phase(frame, RAINBOW_PERIOD, speed)
        level = clamp_channel(brightness)
        return [hsv_to_rgb(phase + index / count, level) for index in range(count)]
    period = PULSE_PERIOD if name == "pulse" else BREATHE_PERIOD
    envelope = envelope_pulse if name == "pulse" else envelope_breathe
    amount = int(round(envelope(_phase(frame, period, speed)) * 255))
    peak = scale_color(red, green, blue, brightness)
    color = scale_color(peak[0], peak[1], peak[2], amount)
    return [color] * count


VULCAN_INIT_REPORTS = (
    bytes.fromhex("150001"),
    bytes.fromhex("05040004"),
    bytes.fromhex("075f003a00003b00003c00003d00003e00003f0000400000410000420000430000440000450000460000470000480000b30000b40000b50000b60000c20000c30000c00000c10000ce0000cf0000cc0000cd0000460000fc0000480000cd0e"),
    bytes.fromhex("0a0800fff1000202"),
    bytes.fromhex("0a0800fff1000202"),
    bytes.fromhex("0685003a29351e2b39e1e03b1f141a046400003d3c202108161de23e232215071b068b3f2400170a0919914041001c180b052c4226250c0d0e1011432a272d120f368a4445892e1333379046494c2f30343888474a4d31320087e6484b4e285250e5e7d2535f5c595100f1d154605d5a4f8e65d055615e5b62a4e4fc56578558630000c224"),
    bytes.fromhex("092b004900004a00004b00004c00004d00004e0000a400008e0000d00000d100000000000100000000cd04"),
    bytes.fromhex("0dbb0100060b054583cacacacacacaceced2ceced219191919191923232d23232de0e0e0e0e0e0e3e3e6e3e3e6d2d2d5d2d2d5d5d5d9d500d92d2d362d2d36363640360040e6e6e9e6e6e9e9e9ece900ecd9d9ddd9dddde0e0dde0e4e440404a404a4a53534a535d5dececefecefeff2f2eff2f5f5e4e4000000000000000000005d5d00000000000000000000f5f500000000000000000000e4e4e8e8e8e8e8ebebeb00eb5d5d67676767677070700070f5f5f8f8f8f8f8fbfbfb00fbebefefef00eff0f0edf0f000707a7a7a007a7a7a6f7a7a00fbfdfdfd00fdf8f8eaf8f800ededeaeded00edeaeaf6e7ea6f6f656f6f006f6565665a65eaeadceaea00eadcdc00cedceae7e5e7e5e5000000000000655a505a5050000000000000dccec0cec0c0000000000000e70000e2e2e2e2dfdfdfdfdf5a0000454545453b3b3b3b3bce0000b2b2b2b2a4a4a4a4a4dcdcdcdc00dadadadada00d730303030002626262626001c96969696008888888888007ad7d7d700d4d4d4d4d4d1d1d11c1c1c0011111111110606067a7a7a006c6c6c6c6c5e5e5e00000000000000000000000000000000000000000000000000000000000000000000000024cf"),
    bytes.fromhex("1308010000000000"),
)

