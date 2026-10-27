# Swarm-inspired Linux UI

Status: implementiert und zur visuellen Abnahme bereit. Basis: `main` 59f3bde; AIMO-Änderungen bis ead75c4 enthalten; eigener Branch `feat/swarm-inspired-ui`, zu Beginn sauber.

## Referenz
- Original-Screenshot der Kone-Aimo-Beleuchtung: https://bit-tech.net/media/image/2018/1/9ca3c0af-d91c-4b5e-98ee-4887f782b3ac.png (bit-tech, 2018). Per Vision geprüft: anthrazitfarbige, kompakte Oberfläche, cyanfarbene Unterstreichung aktiver Navigation, horizontale Geräte-Tabs, `// ILLUMINATION`, zweigeteilter Effekt-/Gerätebereich, fünf Profil-Slots und Aktionen am unteren Rand. Englische Beschriftung im Original; Linux-UI deutsch.
- Kontext: https://bit-tech.net/reviews/roccat-kone-aimo-review/2/ . Die lokale, entpackte Installer-Kopie `~/.hermes/attachments/swarm_extract/` enthält DLLs und Programmdateien, jedoch keine direkt extrahierten PNG/JPG-Bilddateien. Nur lesend gesichtet; keine Ausführung der Windows-Software.
- Ein älterer Imgur-Link aus einem Review lieferte nur ein 404-Bild und wurde verworfen.

## Umfang
GTK4/libadwaita beibehalten; dunkle Swarm-ähnliche Flächen und Cyan-Akzente, Geräteauswahl, Übersichts- und Beleuchtungsnavigation, AIMO-Kontrollen, Status und Profil-/Anwenden-Leiste. Nur unterstützte RGB-Funktionen zeigen; Offline-Zustand ausdrücklich kennzeichnen. Keine HID-/Backendänderung. Profile sind lokale Sitzungsvorlagen für Beleuchtungsparameter, **keine** Hardware- oder persistente Swarm-Profile.

## Fortschritt und Nachweis
- Gtk-Oberfläche im Branch `feat/swarm-inspired-ui`: Swarm-ähnlicher Header und Navigation, dunkle zweispaltige Beleuchtungsansicht mit Cyan-Akzenten, sichtbare AIMO-Radioauswahl, deutsche Beschriftung, Offline-Status und lokale Sitzungsslots mit explizit begrenztem Funktionsumfang.
- Xvfb-Screenshots (1280×900) visuell überprüft: `docs/screenshots/swarm-overview-offline.png` (echter CLI-Scan via Test-CLI mit leerer Liste), `docs/screenshots/swarm-lighting-demo.png` (simulierte Kone, im Header klar als Demo markiert), `docs/screenshots/swarm-lighting-controls-demo.png` (unterer, scrollbar erreichbarer Beleuchtungsbereich). Die beiden Demo-Bilder belegen **keine** Geräteverbindung; die Vollansicht ist scrollbar.
- `GTK_A11Y=none dbus-run-session -- xvfb-run -a /usr/bin/python3 -m unittest discover -s tests -v`: 56 Tests bestanden, Exit 0. Darunter GUI-Regressions-/Smoke-Tests für Navigation, Offline-Status, Sitzungsspeicher/Rückladen, Effekt-CLI und RGB-Anwenden per simuliertem CLI; bestehende AIMO-Radio-/Fehlerfälle bleiben grün.
- Reale Hardware nicht vorhanden/getestet; ein echter Geräte-Scan im lokalen Xvfb ohne simuliertes CLI meldet fehlendes `python-hidapi`. Die Test-CLI ist ausschließlich zur Screenshot-Erstellung und für Smoke-Tests eingesetzt. Xvfb meldete `libEGL DRI3` und `cairo.Context`-Converter-Warnungen ohne Testfehler.
- Kein Original-Windows-Swarm unter Linux ausgeführt; visuelle Annäherung, kein 1:1-Klon und keine Behauptung identischer AIMO-Algorithmen oder echter Hardwareprofile.
