# Roccat AIMO RGB

GTK4 / libadwaita RGB controller for Linux, with Bazzite as the primary installation target.
Supports Kone AIMO (`1e7d:2e27`, 11 LEDs), Vulcan 100 AIMO (`1e7d:307a`) and
Vulcan 120 AIMO (`1e7d:3098`, 144 LED slots). Other Roccat products are not supported.
Vulcan II (`1e7d:2f4e`) is identified as a keyboard, but its different RGB
protocol is not implemented yet. Its lighting controls remain disabled.
Unknown products use their USB model name when available.

## Bazzite: install and start

Run in Desktop Mode. Flatpak must already be available.

```bash
git clone https://github.com/Goitonthefloor/roccat-aimo-app.git
cd roccat-aimo-app
bash scripts/setup-bazzite.sh
flatpak run io.github.Goitonthefloor.roccat.aimo
```

The setup script installs the Builder Flatpak and the app for the current user.
It installs narrowly scoped udev rules in `/etc/udev/rules.d` with sudo. It does
not layer packages onto Bazzite or require a reboot. Reconnect the mouse and
keyboard after setup so the active desktop session receives access.
The GNOME 50 runtime and SDK are downloaded by the builder.

Flatpak's `--device=all` permission exposes HID and input devices, but does not
replace host permissions. The udev rules grant access only to the three supported
product IDs. Light by Push also needs access to the supported Vulcan input devices.
Do not run the GUI as root or make `/dev/input` world-writable. Other RGB controllers
(e.g. OpenRGB or Eruption) must not write to the same device at the same time.

The app runs in the desktop session. Gaming Mode and background operation across
session changes are not verified. Keep the window open for software effects.
Closing it stops the effect process; the final hardware color may remain.

## Lighting

- Static color, hex input, brightness, presets, and individual LED selection.
- Pulse and Breathe with speed from 0.25 to 4 times the base rate.
- Rainbow / Rainbow Flow: a moving spectrum through the device's LED order.
- Color wave and Color cycle; reverse direction for flow and wave effects.
- Beat: 30–240 BPM, multiplied by the Speed setting. This is a timed rhythm,
  not microphone or music synchronization.
- Light by Push (Vulcan only): a key-down event lights the **whole keyboard**,
  then fades it out. Speed controls decay. Releases and autorepeat do not retrigger.
  Individual key-to-LED mapping and per-key ripples are not implemented.

The UI shows an LED sequence preview, not a physical keyboard layout. Reactive
input is read only by the hardware worker; the UI does not simulate key presses.
Input events are neither recorded nor logged and the keyboard is not grabbed.

## CLI

```bash
# For Flatpak CLI commands, prepend:
# flatpak run --command=roccat-aimo-cli io.github.Goitonthefloor.roccat.aimo
roccat-aimo-cli list --json
roccat-aimo-cli rgb 255 0 80 --brightness 180 --index 0
roccat-aimo-cli rgb 0 255 0 --led 0 --index 0
roccat-aimo-cli effect rainbow-flow 255 255 255 --speed 1.5 --reverse --index 0
roccat-aimo-cli effect beat 120 40 255 --bpm 120 --speed 1 --index 0
roccat-aimo-cli effect reactive 0 180 255 --speed 1 --index 0
roccat-aimo-cli led 0 --index 0
```

Use the zero-based index returned by `list`. Stop an effect with Ctrl+C.
Individual LED updates preserve the app's last saved static map, not colors read
from the hardware or an ongoing animation. DPI changes are not implemented.

## Arch Linux

```bash
cd pkg/arch
makepkg -si
```

The package includes host udev rules. Reconnect devices after installation.
GTK >= 4.12 and libadwaita >= 1.4 are required.

## Run from source

Install Python 3.10+, Python hidapi (hidraw backend), PyGObject with Cairo,
GTK4 >= 4.12, and libadwaita >= 1.4 using your distribution's packages.
Install `etc/udev/70-roccat-aimo.rules` on the host as described above, then:

```bash
python3 src/roccat_aimo_bridge.py gui
```

The optional systemd bridge only tracks device discovery; it does not restore or
animate lighting. No background service is needed for the GUI.

## Verification

```bash
python3 -m unittest discover -s tests -v
# Linux GUI tests:
dbus-run-session -- xvfb-run -a python3 -m unittest discover -s tests -v
```

Tests use simulated HID reports and input events; they cannot certify hardware
behavior. GUI tests require a Linux display and GTK dependencies. The GitHub
workflow runs those tests on Ubuntu 24.04. A full Bazzite Flatpak build and real
Kone/Vulcan hardware smoke test are still required before calling this release
hardware-validated.

On Bazzite, check: GUI launch, discovery, static RGB, each effect, BPM and speed,
Light by Push while another window has focus, unplug/replug, device switching,
and closing the app while an effect is running.

## Protocol and build references

Existing Vulcan initialization reports originate from the MIT-licensed
[simonhuwiler/roccatvulcan](https://github.com/simonhuwiler/roccatvulcan).
Flatpak directory sources are relative to the manifest, as documented in
[Flatpak module sources](https://docs.flatpak.org/en/latest/module-sources.html).
The manifest therefore points at `../..` for this repository.

## License

MIT; see LICENSE.
