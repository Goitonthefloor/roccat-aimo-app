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

### Arch Linux

```bash
git clone https://github.com/Goitonthefloor/roccat-aimo-app.git
cd roccat-aimo-app
makepkg -si
```

Or manual:

```bash
pip install --user hidapi
cp src/roccat_aimo_bridge.py ~/.local/bin/roccat-aimo-cli
chmod +x ~/.local/bin/roccat-aimo-cli
systemctl --user enable --now roccat-aimo-bridge.service
```

### Flatpak

```bash
flatpak install io.github.Goitonthefloor.roccat.aimo
flatpak run io.github.Goitonthefloor.roccat.aimo
```

Or build locally:

```bash
flatpak-builder --force-clean build-dir pkg/flatpak/roccat-aimo.yml
flatpak remote-add --no-gpg-verify local-roccat repo
flatpak make-local repo build-dir/io.github.Goitonthefloor.roccat.aimo.flatpak
flatpak install local-roccat io.github.Goitonthefloor.roccat.aimo
```

### Bazzite

- Flatpak-Variante ist für Bazzite empfohlen.
- GUI über Flatpak sollte sowohl im Desktop als auch unter Gamescope starten.
- Falls du das systemd-User-Service verwenden willst, aktiviere es über den Terminal-Mode oder user-session.

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
