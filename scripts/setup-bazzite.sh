#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
command -v flatpak >/dev/null || { echo "Flatpak is required." >&2; exit 1; }
# Bazzite has a read-only system image. Use the Builder Flatpak, no layering/reboot.
flatpak remote-add --user --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo
flatpak install --user flathub org.flatpak.Builder
sudo install -Dm644 etc/udev/70-roccat-aimo.rules /etc/udev/rules.d/70-roccat-aimo.rules
sudo udevadm control --reload-rules
echo "Reconnect your Roccat devices after setup so session permissions take effect."
flatpak run org.flatpak.Builder --user --install --install-deps-from=flathub --force-clean build-dir pkg/flatpak/roccat-aimo.yml
echo "Start: flatpak run io.github.Goitonthefloor.roccat.aimo"
