#!/usr/bin/env bash
set -euo pipefail

missing=()
command -v flatpak-builder >/dev/null 2>&1 || missing+=("flatpak-builder")
command -v flatpak >/dev/null 2>&1 || missing+=("flatpak")

if [ ${#missing[@]} -eq 0 ]; then
  echo "flatpak and flatpak-builder are already installed."
  exit 0
fi

echo "Missing: ${missing[*]}"
if command -v rpm-ostree >/dev/null 2>&1; then
  echo "Detected rpm-ostree (Bazzite). Layering packages requires a reboot."
  sudo rpm-ostree install "${missing[@]}"
  echo "Done. Bitte reboot einmal durchführen, dann weiter mit dem Flatpak-Build."
elif command -v dnf >/dev/null 2>&1; then
  echo "Detected dnf."
  sudo dnf install -y "${missing[@]}"
elif command -v apt >/dev/null 2>&1; then
  echo "Detected apt."
  sudo apt update && sudo apt install -y "${missing[@]}"
else
  echo "Kein bekannter Paketmanager gefunden. Bitte manuell installieren: ${missing[*]}"
  exit 1
fi
