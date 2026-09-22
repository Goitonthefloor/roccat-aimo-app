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

- Roccat Kone AIMO (`1e7d:2e27`), 11 LEDs
- Roccat Vulcan 100 AIMO (`1e7d:307a`) and Vulcan 120 AIMO (`1e7d:3098`), 144 keys

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
> Das Manifest nutzt die GNOME-Runtime, damit GTK4, libadwaita und Python-HID dabei sind.
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
mkdir -p ~/.local/share/applications ~/.config/systemd/user
cp src/roccat-aimo.desktop ~/.local/share/applications/roccat-aimo.desktop
cp etc/systemd/user/roccat-aimo-bridge.service ~/.config/systemd/user/roccat-aimo-bridge.service
systemctl --user daemon-reload
systemctl --user enable --now roccat-aimo-bridge.service
```

### Bazzite-Hinweis

- Flatpak ist bevorzugt, weil Bazzite kein normales systemd-user-Session im Desktop/Gamescope bereitstellt.
- Falls du das systemd-user-Service trotzdem nutzen willst, aktiviere es im Terminal-Mode oder in einer `user-session`.

## Usage

### CLI

`list` prints a zero-based index. Pass that index to the other commands with `--index`.

`rgb` paints a Kone AIMO (11 LEDs) or Vulcan 100/120 AIMO (144 keys). `--led` changes one light and leaves the others as they were.

```bash
roccat-aimo-cli list
roccat-aimo-cli list --json
roccat-aimo-cli rgb 255 0 0 --index 0
roccat-aimo-cli rgb 0 255 0 --led 0 --brightness 180 --index 0
roccat-aimo-cli effect breathe 255 0 0 --index 0
roccat-aimo-cli effect rainbow 255 255 255 --speed 1 --index 0
roccat-aimo-cli led 0 --index 0
roccat-aimo-cli poll --index 0
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
