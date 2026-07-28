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

Binary Flatpak (wenn verfügbar):
```bash
flatpak install io.github.Goitonthefloor.roccat.aimo
flatpak run io.github.Goitonthefloor.roccat.aimo
```

Lokal bauen (Bazzite / Flatpak 1.18):
```bash
# 1) Clone
git clone https://github.com/Goitonthefloor/roccat-aimo-app.git
cd roccat-aimo-app

# 2) Voraussetzungen installieren
bash scripts/setup-bazzite.sh
# Reboot falls rpm-ostree Pakete gelayert wurden

# 3) Alte fehlgeschlagene Build-Artefakte bereinigen
rm -rf build-dir repo io.github.Goitonthefloor.roccat.aimo.flatpak
flatpak remote-delete local-roccat || true

# 4) Flatpak bauen + direkt installieren (ohne separates Repo)
flatpak-builder --force-clean --repo=repo build-dir pkg/flatpak/roccat-aimo.yml
flatpak install repo io.github.Goitonthefloor.roccat.aimo
```

> Hinweis: `scripts/setup-bazzite.sh` prüft ob `flatpak` und `flatpak-builder` vorhanden sind und installiert sie unter Bazzite via `rpm-ostree install` nach. Danach ist ein Reboot nötig, bevor `flatpak-builder` zur Verfügung steht.
> `flatpak install local-roccat ...` und `flatpak make-local` werden hier bewusst nicht verwendet, weil sie auf Flatpak 1.18 + unvollständigem lokalen Repo fehlschlagen.

### Arch Linux

```bash
git clone https://github.com/Goitonthefloor/roccat-aimo-app.git
cd roccat-aimo-app
makepkg -si
```

Or manual:
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

### GUI

```bash
roccat-aimo-cli gui
```

## Build

```bash
python3 -m pip install --user build
makepkg -sf
```

## License

MIT
