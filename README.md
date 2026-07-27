# Roccat AIMO App

Userspace bridge for Roccat Kone AIMO and Vulcan AIMO on Linux.

- Detect devices via `hidapi`
- Basic control: DPI, LED brightness/state, Vulcan per-key RGB
- CLI: `roccat-aimo-cli`
- systemd user service for boot
- Arch PKGBUILD + Flatpak manifest included

## Install

### Arch
```bash
sudo pacman -U PKGBUILD
```

### Flatpak
```bash
flatpak install io.github.Goitonthefloor.roccat.aimo.flatpak
```

### Manual
```bash
pip install hidapi
cp src/roccat_aimo_bridge.py ~/.local/bin/roccat-aimo-cli
systemctl --user enable --now roccat-aimo-bridge.service
```

## Usage

```bash
sudo roccat-aimo-cli list
sudo roccat-aimo-cli dpi 1600 1600
sudo roccat-aimo-cli led 1 --brightness 255
sudo roccat-aimo-cli rgb 0 0 255 0 0
sudo roccat-aimo-cli poll
```

## License

MIT
