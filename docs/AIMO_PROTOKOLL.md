# AIMO-Farb-/Effektprotokoll der Roccat Swarm-Software

Extrahiert per REA (Ghidra 12.1.4) aus `ROCCAT Swarm_v19482.exe` (NSIS-Installer, entpackt nach
`/home/gregerr/.hermes/attachments/swarm_extract/`). Analyse-Binaries: `aimo.dll`, `AimoEffect.dll`,
`ROCCAT_Swarm_Monitor.exe`, `HIDDLL.dll`. SHA256 des Installers: `8d54e1e5af78deba984ae2451f7aa7c1e7e6a0f806ed0b8c28e44c6e1f012fa8`.

---

## 1. Architektur-Überblick

Swarm trennt die AIMO-Logik in drei Schichten:

| Schicht | Binary | Rolle |
|---|---|---|
| Effekt-Controller | `aimo.dll` | Effekt-Threads (wave/breath/heartbeat/cycle/...), IPC via QSharedMemory |
| Effekt-Engine | `AimoEffect.dll` | Rendert per-Key-LED-Maps, lädt `ledpositions`/`ledenumeration`, `SendKeyMapping` |
| Geräte-/HID-Schicht | `ROCCAT_Swarm_Monitor.exe` | Baut die HID-Reporte, sendet via `hid_send_feature_report`/`hid_write`/`hid_set_output_report` |
| HID-Abstraktion | `HIDDLL.dll` | Wrapper um Windows HID-API (`HidD_SetFeature`, `HidD_GetFeature`, `ReadFile`/`WriteFile`) |

**Kernprinzip:** Swarm rendert die Effekte **software-seitig als per-Key-LED-Map** und sendet die komplette
Farbmatrix als einen HID-Report an das Gerät. Es gibt **keine** geräteinterne Effekt-Engine, die Swarm nur
parametrisiert — die Effekt-Threads in `aimo.dll` berechnen die RGB-Werte pro Key und schreiben sie in die
LED-Map. Das ist exakt der Ansatz, den die Linux-Software (Eruption/roccat-aimo) bereits nutzt
(`send_led_map`).

---

## 2. HID-Report-Struktur (das eigentliche Protokoll)

Die Report-Struktur ist in der Monitor.exe als INI-Tabellen eingebettet (Defaults) und wird zur Laufzeit aus
`config/<device>/rgb_backlight_table.ini` bzw. `rgb_led_mapping.ini` geladen. Drei Report-Typen:

### 2.1 Reference 22 — Set Backlight LED PWM Data (Usage Page 0xFF00, Usage 0x01)
**Der Haupt-Report für die per-Key-RGB-Beleuchtung der Vulcan-Tastaturen.**

- Report-Header: **Usage Page 0xFF00, Usage 0x01** (Vendor-Defined HID)
- Enthält die komplette LED-Map: pro Key 3 Report-Positionen (R, G, B)
- Zwei Varianten: `count=123` (Vulcan) und `count=163` (Vulcan Pro / Full-Size)
- Report-Positionen sind **nicht sequenziell** — die Tabelle mappt Key-Index → Report-Byte-Offset

Beispiel (Vulcan, count=123, R-Kanal):
```
1_r = 10    2_r = 43    3_r = 68    4_r = 83    5_r = 98    6_r = 132
7_r = 153   8_r = 171   9_r = 189   10_r = 211  11_r = 229  12_r = 247
13_r = 253  14_r = 269  15_r = 281  16_r = 296  17_r = 378  18_r = 388
19_r = 391  20_r = -1   21_r = -1   22_r = 13   23_r = 28   24_r = 46
...
```
- `-1` = Key hat keine LED (z.B. 20/21 = nicht vorhandene Tasten)
- G- und B-Kanäle haben eigene Tabellen (Offset +1/+2 pro Key, aber nicht immer — die Tabellen sind
  explizit, nicht abgeleitet)
- Die vollständigen Tabellen liegen in `findings/ref22_count123.txt` und `findings/ref22_count163.txt`

### 2.2 Reference 16 — Backlight Setting (ID 0x11)
- **Feature-Report-ID: 0x11**
- `count=5` — für Geräte mit wenigen Zonen (Mäuse, kleine Tastaturen)
- Report-Positionen: `1_r=9, 2_r=10, 3_r=11, 4_r=12, 5_r=13`, `1_g=14...`, `1_b=19...`
- Wird für "UI set custom color to Backlight settings" genutzt

### 2.3 Reference 18 — Set Backlight LED PWM Data (Endpoint 4)
- **Output-Report über Endpoint 4** (Interrupt-Out)
- `count=5`, Positionen: `1_r=3, 2_r=4, 3_r=5, 4_r=6, 5_r=7`, `1_g=8...`, `1_b=13...`
- PWM-Daten für Geräte, die über den Interrupt-Endpoint statt Feature-Report angesteuert werden

### 2.4 HID-Transport
Die Monitor.exe nutzt vier HID-Pfade (Strings bestätigt):
- `hid_send_feature_report` → `HidD_SetFeature` (Feature-Report, z.B. ID 0x11)
- `hid_get_feature_report` → `HidD_GetFeature`
- `hid_set_output_report` → `HidD_SetOutputReport`
- `hid_write` → `WriteFile` (Interrupt-Out, Endpoint 4)

---

## 3. Effekt-Architektur (aimo.dll)

Die Effekte sind C++-Thread-Klassen (RTTI-Namen in `.rdata`). Jede Klasse rendert einen Effekt in die
per-Key-LED-Map:

| Effekt | RTTI-Klasse | Anmerkung |
|---|---|---|
| Wave | `wave_thread_c`, `khan_aimo_wave_effect_thread_c` | Laufende Welle über die Tasten |
| Breathing | `breath_thread_c`, `breath2_thread_c` | Pulsierendes Auf-/Abdunkeln |
| Heartbeat | `heartbeat_thread_c`, `heartbeat2_thread_c`, `kone_aimo_heartbeat_thread_c`, `heartbeat2_out_thread_c` | Herzschlag-Puls |
| Color-Cycle | `cycle_color_base_c`, `cycle_breathing_thread_c`, `cycle_fully_lit_thread_c`, `cycle_heartbeat_thread_c` | Farbwechsel |
| Snake | `snake_thread_c`, `snake2_thread_c`, `snake_effect_base_c` | Schlange über die Tasten |
| Fade | `fade_thread_c` | Sanfter Farbübergang |
| Ripple | `ripple_thread_c` | Welle von einem Punkt |
| Blinking | `blinking_thread_c` | Blinken |
| Fully Lit | `fully_lit_thread_c` | Alle Tasten statisch |
| No Effect | `no_effect_thread_c`, `aimo_no_thread_c` | Aus |
| Multi | `multi_effect_thread_c` | Kombination mehrerer Effekte |
| Gerätespezifisch | `kone_xp_photon_effect_thread_c`, `kone_xp_air_photon_effect_thread_c`, `battery_indication_effect_thread_c` | Maus-/Batterie-Effekte |

**Effekt-Parameter:** Die Effekt-Threads haben `init_group_data(aimo_device_i *f_dev, int f_group_id)` und
`start_thread(aimo_device_i *f_dev, int f_group_id)`. Die Parameter (Farben, Geschwindigkeit, Gruppen) werden
pro Geräte-Gruppe gesetzt. Die Effekt-IDs werden über einen Dispatcher (`start_effect`) an die Thread-Objekte
weitergeleitet.

**IPC:** `aimo.dll` und `AimoEffect.dll` kommunizieren über `QSharedMemory` (`aimo_effect/Swarm`,
`aimo_effect/Monitor`, `aimo_light_effect/Swarm`). Der Controller (`create_aimo_effect_ctrl`) richtet den
Shared-Memory ein.

---

## 4. Farb-Layout / AIMO-Palette (aimo_color_theme.dat)

Die Datei `data/Swarm/aimo_color_theme.dat` (374 Bytes) enthält **10 Themes × 3 Farben** (Big-Endian-Header,
16-Bit RGB, 8-Bit = hohes Byte). Struktur: `0000 000a` (10 Themes), pro Theme `0000 0003` (3 Farben), jede
Farbe 11 Bytes `01 ff ff R_lo R_hi G_lo G_hi B_lo B_hi 00 00`.

| Theme | Farbe 1 | Farbe 2 | Farbe 3 | Beschreibung |
|---|---|---|---|---|
| 0 | (255,0,0) Rot | (255,80,0) Orange | (230,140,0) Gelb | **AIMO-Signatur** (Rot→Orange→Gelb) |
| 1 | (0,0,255) Blau | (75,75,255) | (150,150,255) | Blau-Verlauf |
| 2 | (90,19,255) | (157,20,255) | (175,13,219) | Violett |
| 3 | (197,11,220) | (241,127,255) | (208,1,87) | Magenta/Rosa |
| 4 | (246,255,57) | (249,194,0) | (245,104,0) | Gelb→Orange |
| 5 | (200,255,0) | (100,255,5) | (0,255,10) | Grün-Verlauf |
| 6 | (0,255,0) | (0,255,50) | (0,255,100) | Grün |
| 7 | (245,76,108) | (246,126,71) | (249,194,0) | Rot→Orange |
| 8 | (0,0,255) | (0,127,152) | (0,255,50) | Blau→Türkis→Grün |
| 9 | (244,0,107) | (244,0,0) | (246,120,165) | Pink/Rot |

**Theme 0 (Rot→Orange→Gelb) ist die AIMO-Signaturfarbe** — das ist der "AIMO-Smart"-Look, den die
Linux-Software als Standard übernehmen sollte.

---

## 5. Geräte-Konfiguration (AimoEffect.dll)

Die Effekt-Engine lädt pro Gerät:
- `ledpositions` — die LED-Positionen (Koordinaten-Matrix)
- `ledenumeration` — die LED-Aufzählung (welche Keys welche LEDs haben)
- `brightness` — Helligkeit
- Gerätetypen: `mouse`, `headset`, `keyboard` (in der LED-Map-Konfiguration)

Die Konfigurationsdateien (zur Laufzeit geladen):
- `config/vulcan/rgb_led_mapping.ini`, `config/vulcan/led_mapping.ini`
- `config/vulcan_pro/full_size/rgb_backlight_table.ini`, `rgb_led_mapping.ini`
- `config/vulcan_pro/tkl/rgb_backlight_table.ini`, `rgb_led_mapping.ini`
- `config/core_kb/membrane|mechanical|magma_mini/rgb_backlight_table.ini`, `rgb_led_mapping.ini`
- `config/vulcan2_max|mk|mini|mini_air/backlight_red_table.ini`

---

## 6. Abgrenzung: per-Key vs. Zone vs. global

- **per-Key-RGB** (Vulcan-Tastaturen): Reference 22 (Usage Page 0xFF00) — komplette LED-Map, jeder Key hat
  eigene R/G/B-Report-Positionen. Das ist der Hauptpfad für AIMO-Tastaturen.
- **Zone/Mode-Level** (Mäuse, kleine Geräte): Reference 16 (ID 0x11, count=5) und Reference 18 (Endpoint 4,
  count=5) — wenige Zonen, die als "Keys" in der Tabelle behandelt werden.
- **Global**: `AimoBrightness` (Helligkeit) und `aimo_color_theme.dat` (Themes) gelten geräteübergreifend.

---

## 7. Empfehlung für die Linux-Software

Die Linux-Software (roccat-aimo + Eruption) kann das AIMO-Protokoll wie folgt nachbilden:

1. **Effekte software-rendern** (wie Swarm): Wave, Breathing, Heartbeat, Color-Cycle, Snake, Fade, Ripple,
   Blinking, Fully-Lit, No-Effect — alle als per-Key-LED-Map berechnen.
2. **Report bauen** nach Reference 22 (Usage Page 0xFF00, Usage 0x01): die LED-Map in die Report-Positionen
   aus `rgb_backlight_table.ini` schreiben (count=123 für Vulcan, count=163 für Vulcan Pro).
3. **Senden** via HID Feature-Report (ID 0x11 für Zonen-Geräte) oder Interrupt-Out (Endpoint 4) — je nach
   Gerät. Für Vulcan-Tastaturen ist der per-Key-Report (Reference 22) der richtige Weg.
4. **AIMO-Signaturfarbe** als Standard-Theme: Rot→Orange→Gelb (Theme 0 aus aimo_color_theme.dat).
5. **Helligkeit** global via `AimoBrightness` anwenden.

**Wichtig:** Die Report-Positionen sind gerätespezifisch und müssen aus den `rgb_backlight_table.ini`-Dateien
des jeweiligen Geräts übernommen werden — sie sind nicht universell. Die vollständigen Tabellen für Vulcan
(count=123) und Vulcan Pro (count=163) sind in `findings/ref22_count123.txt` und `findings/ref22_count163.txt`
hinterlegt.

---

## 8. Findings-Ledger

| # | Evidence | Erkenntnis |
|---|---|---|
| 1 | `aimo_overview.json` (ev_d27f1ed2) | aimo.dll: PE x86, 762 Prozeduren, 647 Strings |
| 2 | `str_wave.json` (ev_39ff83e8) | RTTI-Klassennamen der Effekt-Threads in aimo.dll |
| 3 | `aimo_color_theme.dat` (dekodiert) | 10 Themes × 3 Farben, 16-Bit RGB, Theme 0 = AIMO-Signatur |
| 4 | `aimeffect_overview.json` | AimoEffect.dll: per-Key-LED-Map (ledpositions/ledenumeration/SendKeyMapping) |
| 5 | `monitor_overview.json` | Monitor.exe: 6608 Prozeduren, HID-Report-Referenzen |
| 6 | Report-Tabellen (VA 0x89c92c, 0x8a8d8f, 0x8a4a3f, 0x8a58f6) | Reference 22: count=123/163, per-Key-Report-Positionen |
| 7 | Report-Tabellen (VA 0x8a338f, 0x8a3807) | Reference 16 (ID 0x11) und Reference 18 (Endpoint 4), count=5 |
| 8 | HIDDLL.dll-Exports | HT_ReadUSB/HT_WriteUSB/HT_SetFeature/HT_GetFeature |
| 9 | `fn_create_ctrl.json` | create_aimo_effect_ctrl: QSharedMemory-IPC (aimo_effect/Swarm, /Monitor) |
| 10 | `fn_ledmap.json` | AimoEffect.dll: LED-Map-Parser (Gerätetypen mouse/headset/keyboard) |
| 11 | `fn_start_effect.json` | aimo.dll: start_effect-Dispatcher (Effekt-ID → Thread-Objekt) |
