# Packaging inputs: roccat-aimo-app

## Canonical upstream and version

- Upstream: https://github.com/Goitonthefloor/roccat-aimo-app
- Package the latest stable release **v0.2.0** (commit `4f64990b638a284f902907e9dd9c627746d770e9`), not prerelease `v0.3.0-Testing`.
- Release artifact (there are no separately uploaded release assets):
  `https://github.com/Goitonthefloor/roccat-aimo-app/archive/refs/tags/v0.2.0.tar.gz`
- Verified SHA-256 of that artifact:
  `0033dcf52c09ea8cf6d9f5cf04456210d8bf4fcd651ad72fbdc26711ee895851`
- Extracted directory: `roccat-aimo-app-0.2.0`
- Versioning: Git tags are `v<semver>`; use `pkgver=0.2.0`, `pkgrel=1`. Do not use a VCS `pkgver()` for this release package.

## Project and build model

This is a Python application without `pyproject.toml`, `setup.py`, Makefile, CMake, Meson, Cargo, npm, or Go metadata. It is installed directly from its source files; there is no compilation or generated artifact.

- CLI/bridge: `src/roccat_aimo_bridge.py` -> `/usr/bin/roccat-aimo-cli`
- GUI module: `src/roccat_aimo_gui.py` -> `/usr/lib/roccat-aimo-app/`
- Internal RGB module: `src/roccat_rgb.py` -> `/usr/lib/roccat-aimo-app/`
- Test suite: stdlib `unittest` in `tests/`; run `python -m unittest discover -s tests` with `PYTHONPATH="$srcdir/$pkgname-$pkgver/src"`.

The tag's tests require the runtime `hid` module for one subprocess test. In an Arch clean chroot this is supplied by the package's `python-hidapi` dependency; no additional test-only Python framework is required.

## Dependencies

Runtime dependencies:

- `python`
- `python-hidapi` (the `hid` module and HID access)
- `python-gobject` (GI bindings)
- `gtk4` (Gtk 4 GI namespace)
- `libadwaita` (Adw GI namespace)

No build-time compiler, linker, generated-code tool, or third-party test framework is used. Therefore `makedepends=()` and `checkdepends=()` are appropriate. `optdepends=()` is also appropriate: the GUI dependencies are imported by the shipped GUI and must not be optional.

No vendored third-party libraries or submodules exist. `roccat_rgb.py` is upstream application code and must be installed with the CLI and GUI modules.

## Installable assets

- User systemd unit: `src/roccat-aimo-bridge.service` -> `/usr/lib/systemd/user/roccat-aimo-bridge.service`.
  Use this copy: its `ExecStart=/usr/bin/roccat-aimo-cli bridge` matches packaged paths. Do not package `etc/systemd/user/roccat-aimo-bridge.service`, which hard-codes `%h/.local/bin`.
- Desktop entry: `src/roccat-aimo.desktop` -> `/usr/share/applications/roccat-aimo.desktop`.
- Documentation: `README.md` -> `/usr/share/doc/roccat-aimo-app/README.md`.
- License: MIT `LICENSE` -> `/usr/share/licenses/roccat-aimo-app/LICENSE`.
- There is no man page.
- The desktop entry names `Icon=roccat-aimo`, but the v0.2.0 source archive contains no icon. Do not install a conditional nonexistent icon; either ship the package without an icon or add a real upstream icon in a later upstream release.

## Recommended PKGBUILD fields and functions

```bash
pkgname=roccat-aimo-app
pkgver=0.2.0
pkgrel=1
pkgdesc='Userspace bridge and GTK4 controller for Roccat AIMO devices'
arch=('any')
url='https://github.com/Goitonthefloor/roccat-aimo-app'
license=('MIT')
depends=('python' 'python-hidapi' 'python-gobject' 'gtk4' 'libadwaita')
makedepends=()
checkdepends=()
optdepends=()
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('0033dcf52c09ea8cf6d9f5cf04456210d8bf4fcd651ad72fbdc26711ee895851')
```

Use a no-op `prepare()` only if the task explicitly requires every standard function; none is needed. `build()` should be a no-op because there is nothing to build. `check()` runs the unittest command above. `package()` must install all three Python modules plus the service, desktop entry, documentation, and license listed above.

`arch=('any')` is correct despite CachyOS use: the shipped application is architecture-independent Python and contains no native compilation. No CachyOS-specific `CFLAGS`, `CXXFLAGS`, `RUSTFLAGS`, `GOFLAGS`, `-march`, or `-mtune` flags are applicable or safe to add. Using x86-64-v3/v4 would only falsely narrow a pure-Python package's compatibility.
