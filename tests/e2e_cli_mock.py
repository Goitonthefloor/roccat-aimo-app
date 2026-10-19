"""End-to-end CLI verification with Mock-HID (keine echte Hardware noetig).

Treibt `roccat-aimo-cli` (build_parser/main) mit einem gefakten `hid`-Modul an
und prueft die tatsaechlich gesendeten HID-Writes gegen das erwartete
AIMO-Paketformat (aus Eruption/REA):
  - Vulcan AIMO:  143 LEDs -> set_vulcan_led_map -> 7x 65-B-Output-Reports,
                   Header [0xa1,0x01,0x01,0xb4]
  - Kone AIMO:    11 LEDs -> set_kone_led_map -> 1x 46-B-Feature-Report 0x0d
"""
import sys
import types
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

VULCAN_ENTRY = {"vendor_id": 0x1E7D, "product_id": 0x2E24, "path": "/dev/vulcan"}
KONE_ENTRY = {"vendor_id": 0x1E7D, "product_id": 0x2E27, "path": "/dev/kone"}


class Capturing:
    writes = []
    feature_reports = []

    @classmethod
    def reset(cls):
        cls.writes = []
        cls.feature_reports = []


class FakeHidDevice:
    def __init__(self):
        pass

    def open_path(self, path):
        self.path = path

    def open(self, *a):
        pass

    def close(self):
        pass

    def write(self, data):
        Capturing.writes.append(list(data))
        return len(data)

    def send_feature_report(self, data):
        Capturing.feature_reports.append(list(bytes(data)))
        return len(data)

    def read(self, n, timeout_ms=0):
        return []


def install_hid(entries):
    hid = types.ModuleType("hid")
    hid.enumerate = lambda: list(entries)
    hid.device = FakeHidDevice
    sys.modules["hid"] = hid


def run_cli(argv):
    import roccat_aimo_bridge as b
    old = sys.argv
    sys.argv = ["roccat-aimo-cli"] + argv
    try:
        rc = b.main()
    finally:
        sys.argv = old
    return rc


def expect(ok, msg):
    print(("PASS  " if ok else "FAIL  ") + msg)
    return ok


results = []

# --- 1. `list` erkennt Geraete ------------------------------------------------
install_hid([VULCAN_ENTRY, KONE_ENTRY])
Capturing.reset()
rc = run_cli(["list"])
results.append(expect(rc == 0, "list rc=0"))

# --- 2. Vulcan static -> 7x 65-B-Writes, Header 0xa1,0x01,0x01,0xb4 ----------
Capturing.reset()
rc = run_cli(["effect", "static", "255", "0", "0", "--index", "0"])
results.append(expect(rc == 0, "effect static vulcan rc=0"))
results.append(expect(len(Capturing.writes) == 7,
                       f"vulcan static: 7 writes, got {len(Capturing.writes)}"))
if Capturing.writes:
    first = Capturing.writes[0]
    results.append(expect(len(first) == 65, f"write len 65, got {len(first)}"))
    results.append(expect(first[0] == 0, f"report-id 0, got {first[0]}"))
    results.append(expect(first[1:5] == [0xA1, 0x01, 0x01, 0xB4],
                           f"header, got {first[1:5]}"))
    # LED0 = rot, sollte rot (255) an Puffer-Pos 5 liefern
    results.append(expect(first[5] == 255, f"LED0 R=255, got {first[5]}"))

# --- 3. Kone static -> 1x 46-B-Feature-Report 0x0d ---------------------------
Capturing.reset()
rc = run_cli(["effect", "static", "0", "255", "0", "--index", "1"])
results.append(expect(rc == 0, "effect static kone rc=0"))
results.append(expect(len(Capturing.feature_reports) == 1,
                       f"kone static: 1 feature report, got {len(Capturing.feature_reports)}"))
if Capturing.feature_reports:
    rep = Capturing.feature_reports[0]
    results.append(expect(len(rep) == 46, f"kone report len 46, got {len(rep)}"))
    results.append(expect(rep[0] == 0x0D and rep[1] == 0x2E,
                           f"header 0x0d,0x2e, got {rep[0]:#x},{rep[1]:#x}"))
    results.append(expect(rep[2] == 0 and rep[3] == 255 and rep[4] == 0,
                           f"LED0 G=255, got {rep[2:5]}"))

# --- 4. effect-list -----------------------------------------------------------
Capturing.reset()
rc = run_cli(["effect-list"])
results.append(expect(rc == 0, "effect-list rc=0"))

# --- 5. Animiere colorcycle (Kone) -> mehrere Frames --------------------------
Capturing.reset()
rc = run_cli(["effect", "colorcycle", "--index", "1",
              "--duration", "0.05", "--frame-interval", "0.01", "--period", "1.0"])
results.append(expect(rc == 0, "effect colorcycle kone rc=0"))
results.append(expect(len(Capturing.feature_reports) >= 2,
                       f"colorcycle: >=2 frames, got {len(Capturing.feature_reports)}"))

print("\n=== ERGEBNIS ===")
print(f"{sum(results)}/{len(results)} CLI-Checks bestanden")
sys.exit(0 if all(results) else 1)
