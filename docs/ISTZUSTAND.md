# ISTZUSTAND — Linux-RGB-Software (roccat-aimo + eruption)

Bestandsaufnahme vom 19.10.2026. Grundlage für die Anpassungskarten, damit auf dem
aktuellen Stand aufgesetzt wird und nichts doppelt gebaut wird.

---

## 1. Quellen & Repos

| Quelle | Pfad | Zustand |
|--------|------|---------|
| Hauptrepo | `/home/gregerr/github/roccat-aimo-app` | aktiv, git-History bis `07f89b1` (Rocket-Swarm-REA-Analyse) |
| Verwaistes Repo | `/home/gregerr/github/roccat-aimo` | nur `.github/`, kein Code — **verwaist, ignorieren** |
| Installiertes CLI | `/home/gregerr/.local/bin/roccat-aimo-cli` | **veraltet** (233 Zeilen, siehe §6) |
| Referenz-Protokoll | `/mnt/truenas_hermes_swap/gregerr/archive/_archive_2026-07-31/temp-roccat/eruption/` | freie Rust-RGB-Software, fertige Roccat-Treiber |

### Hauptrepo-Inhalt (`roccat-aimo-app`)
- `src/roccat_aimo_bridge.py` — 393 Zeilen, CLI + Bridge-Logik
- `src/roccat_aimo_gui.py` — 342 Zeilen, GTK4/Adwaita-GUI
- `src/aimo_themes.py` — 71 Zeilen, 10 AIMO-Gradient-Themes + Interpolation
- `src/roccat-aimo-bridge.service` — systemd-user-Unit (ExecStart `/usr/bin/roccat-aimo-cli bridge`)
- `src/roccat-aimo.desktop` — Desktop-Eintrag
- `docs/roccat-swarm-aimo-analysis.md` — REA-Analyse von Rocket Swarm (AimoEffect.dll, aimo.dll, aimo_color_theme.dat)
- `pkg/arch/PKGBUILD`, `pkg/flatpak/roccat-aimo.yml`, `etc/systemd/user/roccat-aimo-service.service`, `scripts/setup-bazzite.sh`

---

## 2. Unterstützte Roccat-Geräte (VendorID/ProductID)

### In `roccat-aimo-app` (PRODUCTS-Liste, `ROCCAT_VID = 0x1E7D`)
| Gerät | ProductID | Anmerkung |
|-------|-----------|-----------|
| Kone AIMO | `0x2E27` | Maus |
| Vulcan AIMO | `0x2E24` | Tastatur |
| Vulcan 120 AIMO | `0x2E26` | Tastatur |
| Vulcan TKL AIMO | `0x2E2A` | Tastatur |

> **Achtung Diskrepanz:** Diese Vulcan-IDs (`0x2E24/0x2E26/0x2E2A`) tauchen in
> eruption **nicht** auf. Eruption nutzt andere IDs (siehe unten). Die bridge.py-IDs
> sind vermutlich aus Rocket-Swarm-Daten übernommen und müssen gegen echte Hardware
> verifiziert werden.

### In eruption (`eruption-hwutil/src/hwdevices/mod.rs`)
| Gerät | ProductID | Treiber |
|-------|-----------|---------|
| Vulcan 1xx | `0x3098`, `0x307A` | `roccat_vulcan_1xx.rs` (voll unterstützt) |
| Vulcan Pro | `0x30F7` | `roccat_vulcan_pro.rs` (WIP) |
| Vulcan TKL | `0x2FEE` | `roccat_vulcan_tkl.rs` (WIP) |
| Vulcan Pro TKL | `0x311A` | `roccat_vulcan_pro_tkl.rs` (WIP) |
| Magma | `0x3124` | `roccat_magma.rs` (WIP) |
| Kone AIMO | `0x2E27` | `roccat_kone_aimo.rs` (80%) |
| Kone AIMO Remastered | `0x2E2C` | `roccat_kone_aimo_remastered.rs` |
| Kova AIMO | `0x2CF1`, `0x2CF3` | `roccat_kova_aimo.rs` |
| Kain 100 AIMO | `0x2D00` | `roccat_kain_100.rs` |
| Kain 2xx AIMO | `0x2D60`, `0x2D5F` | `roccat_kain_2xx.rs` |
| Kone XP | `0x2C8B` | `roccat_kone_xp.rs` |
| Kone Pro / Pro Air | `0x2C88` / `0x2C8E`, `0x2C92` | `roccat_kone_pro*.rs` |
| Kone Pure Ultra | `0x2DD2` | `roccat_kone_pure_ultra.rs` |
| Burst Pro | `0x2DE1` | `roccat_burst_pro.rs` |
| Kone XTD | `0x2E22` | `roccat_kone_xtd.rs` |
| Kova 2016 | `0x2CEE/0x2CEF/0x2CF0` | `roccat_kova_2016.rs` |
| Nyth | `0x2E7C`, `0x2E7D` | `roccat_nyth.rs` |
| Aimo Pad Wide | `0x343B` | `roccat_aimo_pad.rs` |
| Elo 7.1 Air | `0x3A37` | `roccat_elo_71_air.rs` |

**Gemeinsame Geräte (beide):** nur **Kone AIMO `0x2E27`**. Die Vulcan-IDs
überlappen nicht — das ist ein offener Punkt für die Anpassung.

---

## 3. RGB-Fähigkeiten in `roccat-aimo-app`

### Vorhanden (bridge.py + aimo_themes.py)
- **Per-Key-RGB (Vulcan):** `set_vulcan_key_rgb(dev, row, col, r, g, b)` — einzelne Taste via Report `0x04`, Payload `[0x0B, row, col, r, g, b]`. Row 0–5, Col 0–20.
- **Komplette LED-Map (Vulcan, 144 Tasten):** `set_vulcan_led_map(led_map)` — 6 Chunks à 60 Bytes, je 64-Byte-Report. Farben in Blöcken von 12 Tasten, Farbteile sortiert (erst alle R, dann G, dann B). Header erster Chunk `[0xA1, 0x01, 0x80, 0x01]`, weitere `[0xA1, cntr+1, 0x00, 0x00]`.
- **AIMO-Gradient-Themes:** `apply_aimo_theme(theme, direction)` — 10 Themes aus `aimo_themes.py`, je 3 Farbstopps, linear interpoliert über die Tastatur (horizontal `h` / vertikal `v`). Themes: AIMO 1–10 (aus Rocket-Swarm `aimo_color_theme.dat` rekonstruiert).
- **Kone LED:** `set_kone_aimo_led(enabled, brightness)` — Report `0x04`, Payload `[0x07, state, brightness]`.
- **Kone DPI:** `set_kone_aimo_dpi(x, y)` — Report `0x04`, Payload `[0x03, 0x04, x_hi, x_lo, y_hi, y_lo]`, Bereich 100–16000.

### CLI-Kommandos (Repo-Stand)
`list`, `dpi`, `led`, `rgb`, `aimo <theme> [--direction h|v]`, `poll`, `gui`, `bridge`.

### GUI (GTK4/Adwaita)
- Geräteliste (Refresh), DPI-Steuerung, LED-Schalter + Helligkeit, Per-Key-RGB (Row/Col/R/G/B), AIMO-Theme-Auswahl (Dropdown) + Richtung.
- GUI ruft das CLI per `subprocess` auf (kein direkter HID-Zugriff).

### NICHT vorhanden (Lücken)
- **Keine animierten Effekte/Modes** (Wave, Breathing, Reactive, Ripple, Spectrum-Cycle, Starlight …). Nur statische Farben/Gradienten.
- **Keine Hardware-Effekt-Modi** (eruption kennt z.B. Hardware-Wave via Report `0x0d` mit Speed-Bytes, Custom-Effects via `0x13`).
- **Keine Init-Sequenz** vor dem Schreiben (eruption macht eine 10-Schritt-Init für Vulcan, 3-Schritt für Kone).
- **Keine Zonen-Steuerung auf der Kone** (eruption: 10 RGBA-Zonen via Feature-Report `0x0d`, 46 Bytes).
- **Kein Profile-/Slot-Handling** (eruption: FN+F1–F4 Slots, Makros M1–M6).

---

## 4. AIMO-Protokoll: bridge.py vs. eruption

### Gemeinsamkeiten
- Beide nutzen `hidapi` und schreiben die Vulcan-LED-Map in 64-Byte-Blöcken mit
  `0xA1`-Header, Farben sortiert (R-Block, G-Block, B-Block), Offset-Formel
  `((i/12)*36) + (i%12)`.

### Unterschiede (wichtig für die Anpassung)
| Aspekt | bridge.py | eruption |
|--------|-----------|----------|
| Report-Typ | `dev.write([0x00] + payload)` (Output-Report) | `send_feature_report` (Feature-Report) für Init/Control; `led_dev.write` für LED-Map |
| Init-Sequenz | **keine** | Vulcan: 10 Schritte (`0x0f` query, `0x15`, `0x05`, `0x07`, `0x0a`, `0x0b`, `0x06`, `0x09`, `0x0d`, `0x13`); Kone: 3 Schritte (`0x04`, `0x0e`, `0x0d`) |
| LED-Map-Header (1. Chunk) | `[0xA1, 0x01, 0x80, 0x01]` | `[0xA1, 0x01, 0x01, 0xB4]` |
| LED-Map-Header (weitere) | `[0xA1, cntr+1, 0x00, 0x00]` | (eruption schreibt 65-Byte-Buffer, `tmp[0]=0`, `tmp[1..65]=64B`) |
| Kone LED | Report `0x04` `[0x07, state, brightness]` | Feature-Report `0x0d` (46 Bytes, 10 Zonen) |
| Kone DPI | Report `0x04` `[0x03, 0x04, x, y]` | (eruption: über Profile-Switching) |
| Hardware-Effekte | **keine** | Wave (`0x0d`, Speed-Bytes 5 & 441), Custom (`0x13`) |

> **Kritischer Punkt:** Der LED-Map-Header der bridge.py (`0x80, 0x01`) weicht vom
> eruption-Header (`0x01, 0xB4`) ab. Das ist ein Kandidat für einen echten Bug —
> muss gegen Hardware verifiziert werden, bevor Effekte darauf aufgesetzt werden.

---

## 5. Lücken für „RGB im AIMO-Stil"

1. **Animierte Effekte fehlen komplett** — nur statische Gradienten. AIMO-Stil
   (Rocket Swarm) nutzt `QLinearGradient`/`QGradient` als Effekt-Engine; die
   bridge.py interpoliert nur einmal statisch.
2. **Keine Hardware-Effekt-Modi** (Wave/Speed, Custom-Effects) — eruption hat die
   Report-Struktur (`0x0d`, `0x13`) bereits implementiert, bridge.py nicht.
3. **Keine Init-Sequenz** — eruption initialisiert das Gerät vor dem Schreiben;
   bridge.py schreibt direkt. Ohne Init kann die LED-Map evtl. nicht greifen.
4. **LED-Map-Header-Diskrepanz** (`0x80,0x01` vs `0x01,0xB4`) — unverifiziert.
5. **Kone nur LED an/aus + DPI** — keine Zonen-/Effektsteuerung (eruption: 10 Zonen).
6. **Vulcan-IDs unverifiziert** — bridge.py-IDs (`0x2E24/0x2E26/0x2E2A`) decken
   sich nicht mit eruption (`0x3098/0x307A` etc.).

---

## 6. Installierbarkeit / Startbarkeit

### Installiertes CLI (`~/.local/bin/roccat-aimo-cli`)
- **Veraltet:** 233 Zeilen, nur `list/dpi/led/rgb/poll`. **Fehlt** gegenüber dem
  Repo-Stand: `aimo`, `gui`, `bridge`, `set_vulcan_led_map`, `apply_aimo_theme`.
- Importiert kein `aimo_themes`. Muss neu installiert werden, um den aktuellen
  Stand zu nutzen.

### README-Dokumentation
- **Flatpak (Bazzite):** `scripts/setup-bazzite.sh` + `flatpak-builder` (README §Install).
- **Arch:** `makepkg -si` in `pkg/arch`.
- **Manuell:** `pip install --user hidapi PyGObject`, CLI nach `~/.local/bin`, GUI nach `~/.local/lib/roccat-aimo-app`, systemd-Unit aktivieren.

### Probleme (Packaging-Bugs)
1. **PKGBUILD kaputt:** `package()` installiert `src/roccat_rgb.py` — **Datei existiert nicht** (nur bridge.py, gui.py, aimo_themes.py). `makepkg` schlägt fehl.
2. **PKGBUILD `check()`:** läuft `python -m unittest discover -s tests` — **kein `tests/`-Verzeichnis vorhanden**. `makepkg` schlägt im Check fehl.
3. **PKGBUILD/Flatpak installieren `aimo_themes.py` NICHT** — aber bridge.py und gui.py importieren es. `aimo`-Kommando und Theme-Dropdown würden zur Laufzeit mit `ImportError` brechen.
4. **Zwei systemd-Units, eine kaputt:**
   - `src/roccat-aimo-bridge.service` → ExecStart `/usr/bin/roccat-aimo-cli bridge` (korrekt).
   - `etc/systemd/user/roccat-aimo-service.service` → ExecStart `%h/.local/bin/roccat-aimo-service` — **Binary existiert nicht** (heißt `roccat-aimo-cli`).
5. **Flatpak `finish-args`:** `--device=all` (HID-Zugriff), Wayland/X11 — ok, aber `aimo_themes.py` fehlt (siehe 3).

### Fazit Installierbarkeit
- **Lokal startbar:** ja, manuell (pip + Dateien kopieren), aber das installierte
  CLI ist veraltet.
- **Flatpak/Arch:** **nicht sauber baubar** wegen fehlender `roccat_rgb.py`,
  fehlendem `tests/` und fehlendem `aimo_themes.py` im Paket.

---

## 7. Empfohlene nächste Schritte (für Anpassungskarten)

1. **Init-Sequenz ergänzen** (aus eruption übernehmen: Vulcan 10-Schritt, Kone 3-Schritt) — Voraussetzung für zuverlässige LED-Map.
2. **LED-Map-Header verifizieren/fixen** (`0x80,0x01` vs eruption `0x01,0xB4`).
3. **Vulcan-IDs gegen echte Hardware prüfen** (bridge.py-IDs vs eruption-IDs).
4. **Animierte Effekte** (Wave, Breathing, Reactive, Spectrum) als Software-Renderer auf `set_vulcan_led_map` aufsetzen — AIMO-Stil.
5. **Kone-Zonen-Steuerung** (10 Zonen, Feature-Report `0x0d`) ergänzen.
6. **Packaging reparieren:** `roccat_rgb.py`-Referenz entfernen, `aimo_themes.py` ins Paket, `tests/` anlegen oder `check()` fixen, doppelte systemd-Unit bereinigen.
7. **Installiertes CLI neu ausrollen** (aktueller Repo-Stand mit `aimo`/`gui`/`bridge`).
