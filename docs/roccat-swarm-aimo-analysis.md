# Rocket Swarm AIMO-Analyse (REA)

Analyse von `ROCCAT_Swarm_1.9482.0.0` (NSIS-Installer, extrahiert nach
`~/.hermes/cache/scratch/roccat-swarm/extracted/`).

## Ziel
Verstehen, wie Roccat AIMO-Effekte funktionieren, um die Linux-RGB-Software
(`roccat-aimo-app`) anzupassen und RGB im AIMO-Stil nutzbar zu machen.

## Architektur (REA, Ghidra 12.1.4)

### AimoEffect.dll (Qt5-Effekt-Engine)
- Exportiert `create_aimo_effect(int param_1)` und `release_aimo_effect()`.
- `param_1 == 1` → Effekt `aimo_light_effect/Swarm`, sonst `aimo_light_effect/Monitor`.
- Erzeugt ein Singleton-Objekt (0x94 Bytes) via Konstruktor `FUN_6e3d87f0`.
- Nutzt Qt5 `QLinearGradient`, `QGradient`, `QColor`, `QBrush` → **AIMO-Effekte
  sind Farbverläufe (Gradienten)**.

### aimo.dll (Effekt-/Protokoll-Steuerung)
- Exportiert `create_aimo_effect_ctrl` / `release_aimo_effect_ctrl`.
- Lädt `aimo_color_theme.dat` (Farbthemen).
- Kern: `aimo_effect_ctrl_c::start_effect(aimo_device_i *f_device)`.
- Lädt `AimoEffect.dll` dynamisch (`create_aimo_effect`).
- Strings: `aimo_effect/Swarm`, `aimo_effect/Monitor`.

### aimo_color_theme.dat (Farbthemen)
- 10 Themes, je **3 Farbstopps** (Gradient).
- Farben 16-bit pro Kanal (0xffff = 255), 8-bit = Wert >> 8.

| Theme | Stopp 1 | Stopp 2 | Stopp 3 |
|-------|---------|---------|---------|
| 1 | #ffffff | #ffffff | #e6e68c |
| 2 | #000000 | #4b4b4b | #969696 |
| 3 | #5a5a13 | #9d9d14 | #afaf0d |
| 4 | #c5c50b | #f1f17f | #d0d001 |
| 5 | #f6f6ff | #f9f9c2 | #f5f568 |
| 6 | #c8c8ff | #6464ff | #0000ff |
| 7 | #0000ff | #0000ff | #f5f54c |
| 8 | #f6f67e | #f9f9c2 | #000000 |
| 9 | #00007f | #0000ff | #f4f400 |
| 10 | #f4f400 | #f4f400 | #f6f678 |

## HID-Protokoll (Vulcan, aus Eruption-Projekt)
- Init-Sequenz: `send_ctrl_report(0x0d)` → `0x0e` → `0x11`.
- `send_led_map(led_map)`: setzt alle 144 Tasten.
  - Farben in Blöcken von 12 Tasten (2 Spalten), Farbteile sortiert (erst alle R, dann G, dann B).
  - `offset = ((i/12)*36) + (i%12)`, `buffer[offset]=r`, `buffer[offset+12]=g`, `buffer[offset+24]=b`.
  - 6 Chunks à 60 Bytes, je 64-Byte-Report mit Header `[0xa1, cntr+1, 0x00, 0x00]`
    (erster: `[0xa1, 0x01, 0x80, 0x01]`), über das LED-Interface (Interface 3).

## Bestehende Linux-Software (roccat-aimo-app)
- `roccat_aimo_bridge.py`: CLI `list/dpi/led/rgb/poll/bridge`.
  - `set_vulcan_key_rgb`: einzelne Taste via Report 0x04, `[0x0B, row, col, r, g, b]`.
- `roccat_aimo_gui.py`: GTK4-GUI mit DPI/LED/RGB-Steuerung.
- **Kein AIMO-Effekt-Support** (nur einzelne Taste RGB).

## Implementierungsplan
1. `aimo_themes.py`: 10 AIMO-Themes als Python-Daten + Gradient-Interpolation.
2. Bridge: `aimo` CLI-Kommando → Farbverlauf über alle Tasten (send_led_map).
3. GUI: AIMO-Theme-Auswahl.
