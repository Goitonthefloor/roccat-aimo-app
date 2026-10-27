# AIMO-Modus – Testprotokoll (2026-10-27)

Getesteter Stand: `wt/t_a338da1a` auf Basis von `6be1a5f`; GTK4/Adwaita unter Xvfb, simuliertes Kone-AIMO-Gerät und CLI-/HID-Testdoubles. **Kein Original-Swarm und keine echte Roccat-Hardware ausgeführt.** Dies ist eine nachgebildete AIMO-Signatur-Wave, keine nachgewiesene Kopie des adaptiven Swarm-Smart-Modus (siehe [REA-Befund](aimo_reverse_engineering.md)).

## Ausführung

```sh
GTK_A11Y=none dbus-run-session -- xvfb-run -a /usr/bin/python3 -m unittest discover -s tests -v
```

Ergebnis: **53 Tests, OK**, Laufzeit 2,417 s. `git diff --check` ohne Befund. GUI-Testlauf separat: **9 Tests, OK** (2,127 s). Unter Xvfb erscheinen ein `libEGL`-DRI3-Hinweis und zwei `cairo.Context`-Converter-Meldungen beim bestehenden Preview-Test; die Tests enden trotzdem erfolgreich. Das sind nicht als behoben behauptete Umgebungs-/Rendering-Meldungen.

## Prüffälle

| Prüffall | Methode | Ergebnis |
| --- | --- | --- |
| Einzel-Button einschalten, sichtbarer Zustand und CLI-Aufruf | GTK-Test betätigt `clicked`; prüft aktiv, Beschriftung, Gradient-/Wave-Argumente und Signaturtheme | Bestanden |
| Einzel-Button ausschalten | GTK-Test betätigt `clicked` erneut; Modus inaktiv | Bestanden |
| Radio-Auswahl „AIMO-Modus (komplett)“ | GTK-Test prüft echte gruppierte `Gtk.CheckButton`-Auswahl „Manuell“/„AIMO“; alle manuellen Widgets einschließlich Einzel-Button gesperrt | Bestanden |
| Zurück auf „Manuell“ | GTK-Test aktiviert die manuelle Radio-Auswahl, überprüft AIMO-Stopp und Freigabe der Widgets | Bestanden |
| Fehlende CLI beim Start | Simulierter Startfehler: AIMO nicht aktiv, Radio zurück auf „Manuell“, Buttons frei, Fehlermeldung statt Erfolg | Bestanden (Fehler im Review-Fix behoben) |
| Prozessende/Geräteverlust | Fake-CLI beendet sich mit Fehler; Polling gibt Radio/Widgets frei und meldet `device lost` | Bestanden (Fehler im Review-Fix behoben) |
| Erwartete Fähigkeiten/Farben | `test_aimo_mode`: Signaturstopps `(255,0,0);(255,80,0);(230,140,0)`, `aimo_cli_args`, Preview für Kone/Vulcan und `available_skills()`-Inventar geprüft | Bestanden |
| GUI → CLI → HID | Bridge-Test mit simuliertem Kone; Wave-Gradient schreibt 46-Byte-HID-Report mit rotem ersten Pixel | Bestanden, **nur simulierte HID-Hardware** |
| Andere Modi | GTK-Test prüft Sperrung aller manuellen Widgets; `start_effect()` beendet AIMO vor dem Start eines anderen Effekts (Codepfad) | UI-Sperrung bestanden; keine echte Hardwareprüfung |

`available_skills()` ist eine dokumentierte Inventarliste, **kein dynamisches Laden aller Effektfamilien**: Im AIMO-Modus läuft tatsächlich die vorhandene `render_wave`-/`aimo-effect wave --mode gradient`-Pipeline mit den Signaturstopps. Andere Effekte werden im Radio-Modus nicht parallel gestartet; die manuellen Steuerelemente sind deaktiviert.

## Grenzen / Review

- Originaltreue, adaptive Reaktionen, Synchronisation mit Swarm und LED-Farben auf echter Hardware sind nicht belegt. Hardware-Abnahme muss separat an angeschlossenem Kone/Vulcan erfolgen.
- Die in `docs/screenshots/` vorhandenen AIMO-Bilder wurden **vor** der Umstellung vom Switch auf echte Radio-Auswahl erzeugt und zeigen nicht den hier getesteten UI-Stand; für visuelle Freigabe neue Screenshots aufnehmen.
- Startfehler lässt sich ohne echte CLI per `ROCCAT_AIMO_CLI=/nonexistent/roccat-aimo-cli` reproduzieren; GUI darf den Master danach nicht fälschlich aktiv anzeigen.
