# Roccat AIMO App

Userspace bridge for **Roccat Kone AIMO** and **Vulcan AIMO** on Linux.

- Detect supported Roccat devices via `hidapi`
- Basic control: DPI, LED, per-key RGB
- CLI: `roccat-aimo-cli`
- GTK4 GUI via `roccat-aimo-cli gui`
- systemd user service for boot
- Arch PKGBUILD included
- Flatpak manifest included

## Supported Devices

- Roccat Kone AIMO
- Roccat Vulcan AIMO family

## Install

### Flatpak (empfohlen, inkl. Bazzite)

Lokal bauen (Bazzite / Flatpak 1.18):
```bash
git clone https://github.com/Goitonthefloor/roccat-aimo-app.git temp
mv temp/.git roccat-aimo-app/.git
rm -rf temp
cd roccat-aimo-app

bash scripts/setup-bazzite.sh
# Reboot falls rpm-ostree Pakete gelayert wurden

# Alte fehlgeschlagene Build-Artefakte bereinigen
rm -rf build-dir repo io.github.Goitonthefloor.roccat.aimo.flatpak
flatpak remote-delete local-roccat || true

# Flatpak bauen + direkt installieren (ohne separates Repo)
flatpak-builder --force-clean --repo=repo build-dir pkg/flatpak/roccat-aimo.yml
flatpak install repo io.github.Goitonthefloor.roccat.aimo
```

> Hinweis: `scripts/setup-bazzite.sh` prüft ob `flatpak` und `flatpak-builder` vorhanden sind und installiert sie unter Bazzite via `rpm-ostree install` nach. Danach ist ein Reboot nötig, bevor `flatpak-builder` zur Verfügung steht.
> `flatpak install local-roccat ...` und `flatpak make-local` werden hier bewusst nicht verwendet, weil sie auf Flatpak 1.18 + unvollständigem lokalen Repo fehlschlagen.

### Arch Linux

```bash
git clone https://github.com/Goitonthefloor/roccat-aimo-app.git temp-roccat
if [ -d roccat-aimo-app ]; then
  mv temp-roccat/.git roccat-aimo-app/.git
  rm -rf temp-roccat
else
  mv temp-roccat roccat-aimo-app
fi
cd roccat-aimo-app/pkg/arch
makepkg -si
```

Oder manuell:
```bash
pip install --user hidapi PyGObject
cp src/roccat_aimo_bridge.py ~/.local/bin/roccat-aimo-cli
chmod +x ~/.local/bin/roccat-aimo-cli
mkdir -p ~/.local/lib/roccat-aimo-app
cp src/roccat_aimo_gui.py ~/.local/lib/roccat-aimo-app/roccat_aimo_gui.py
mkdir -p ~/.local/share/applications
cp src/roccat-aimo.desktop ~/.local/share/applications/roccat-aimo.desktop
systemctl --user enable --now roccat-aimo-bridge.service
```

### Bazzite-Hinweis

- Flatpak ist bevorzugt, weil Bazzite kein normales systemd-user-Session im Desktop/Gamescope bereitstellt.
- Falls du das systemd-user-Service trotzdem nutzen willst, aktiviere es im Terminal-Mode oder in einer `user-session`.

## Usage

### CLI

```bash
roccat-aimo-cli list
roccat-aimo-cli dpi 1600 1600
roccat-aimo-cli led 1 --brightness 255
roccat-aimo-cli rgb 0 0 255 0 0
roccat-aimo-cli poll
```

### AIMO-Effekte (software-gerenderte LED-Maps)

Alle Effekte werden pro Frame als per-key LED-Map berechnet und ueber das
geraetespezifische `send_led_map`-Protokoll (Eruption-Ansatz) uebertragen.
Belegt durch `EFFEKTE.md` (REA-Evidence + Eruption-Quellen).

```bash
roccat-aimo-cli effect-list

# E2 Static - konstante Einzelfarbe
roccat-aimo-cli effect static 255 0 0 --brightness 100

# E1 AIMO-Theme-Gradient (Theme-Name/-Index oder 'r,g,b;r,g,b;...')
roccat-aimo-cli effect gradient "AIMO 9" --direction h
roccat-aimo-cli effect gradient "255,0,0;0,255,0;0,0,255" --direction v

# E4 Breathing - Atmen (animiert, bis --duration oder Ctrl-C)
roccat-aimo-cli effect breathing 0 255 0 --min 10 --max 90 --period 2 --duration 0

# E5 Color-Cycle - Farbzyklus (Hue-Rotation)
roccat-aimo-cli effect colorcycle --period 3 --duration 0

# E3 Wave - Welle ueber das Grid (hue oder gradient)
roccat-aimo-cli effect wave --mode hue --direction h --period 2
roccat-aimo-cli effect wave --mode gradient --theme "AIMO 9" --direction d
```

Geraete: Vulcan AIMO (143 Keys, 6x21) und Kone AIMO (11 LEDs) werden anhand
der Produkt-ID automatisch erkannt. `--index` waehlt das Geraet (siehe `list`).

### GUI

```bash
roccat-aimo-cli gui
```

## Tests / Verifikation

Ohne echte Hardware lassen sich Effekt-Engine und Protokoll per Mock-HID
verifizieren (sendet LED-Maps, ohne ein Gerät zu brauchen):

```bash
python3 -m pytest tests/ -q          # 9 Unit-Tests (Render, Protokoll-Layout, Dispatch)
python3 tests/e2e_cli_mock.py        # 15 End-to-End-CLI-Checks gegen das AIMO-Paketformat
```

Die e2e-Checks prüfen die tatsächlich gesendeten Bytes gegen das erwartete
Eruption/REA-Format:

- **Vulcan AIMO** (143 LED): `effect static` → 7× 65-B-Output-Report,
  Header `[0xa1,0x01,0x01,0xb4]`
- **Kone AIMO** (11 LED): `effect static` → 1× 46-B-Feature-Report `[0x0d,0x2e, …]`
- `effect gradient|breathing|colorcycle|wave` laufen ohne Fehler durch
  (animierte Effekte rendern mehrere Frames, statische genau einen)

Auf einem Rechner mit angeschlossenem Roccat-Gerät ersetzen `list`/`effect`
die Mock-HID und schalten live:

```bash
roccat-aimo-cli list
roccat-aimo-cli effect static 255 0 0
roccat-aimo-cli effect gradient "AIMO 9" --direction h
roccat-aimo-cli effect breathing 0 255 0 --duration 5
```

## Build

```bash
python3 -m pip install --user build
makepkg -sf
```

## License

MIT
