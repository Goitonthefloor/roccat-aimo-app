# Testprotokoll — Verifikation AIMO-Effekte

- Task: `[VERIFIKATION] AIMO-Effekte testen + dokumentieren` (t_d1e08c04)
- Datum: 2026-10-19
- Hash: Commit `3ad05e` (auf Basis `b0b87f7`, Implementierung)
- Umgebung: Headless-Hermes-VM (kein echtes Roccat-Hardware-Gerät angeschlossen)
- Ergebnis: **BESTANDEN** — 9 Unit-Tests + 15/15 CLI-e2e-Checks grün

## Prüfpunkte

| # | Prüfpunkt | Status | Nachweis |
|---|-----------|--------|----------|
| 1 | Python-Syntax/Lint (`ruff` + `py_compile`) | ✅ | `ruff check src tests` → 0 Fehler; `py_compile` aller `src/*.py` OK |
| 2 | CLI `list` & Effekt-Befehle ohne Fehler | ✅ | `e2e_cli_mock.py`: 15/15, alle 5 Effekte + `list` + `effect-list` rc=0 |
| 3 | Echt-Hardware live | ⏭️ | Nicht verfügbar (headless VM). Ersatz: Mock-HID (Punkt 4) |
| 4 | Mock-HID gegen AIMO-Paketformat (REA/Eruption) | ✅ | Vulcan 143 LED: 7×65-B, Header `0xa1 0x01 0x01 0xb4`; Kone 11 LED: 1×46-B Feature-Report `0x0d 0x2e` (siehe unten) |
| 5 | GUI-Effektauswahl ohne Crash | ✅* | Code-Pfad statisch verifiziert; `import gi`-Bug gefixt (PyGObject/GTK4 nur auf Desktop lauffähig, hier headless nicht importierbar) |
| 6 | Dokumentation README | ✅ | README „Tests / Verifikation“ + Effekte-Abschnitt vorhanden |

\* Punkt 5: GTK4 kann headless nicht gestartet werden. Die GUI baut pro Effekt
einen `roccat-aimo-cli`-Befehl und ruft ihn als Subprozess auf — genau dieser
CLI-Pfad ist in Punkt 4 e2e-verifiziert. Zudem wurde der beim Implementieren
übersehene `import gi`-Crash behoben (vorher: `gi.require_version()` ohne
`import gi` → NameError beim Start der GUI).

## In dieser Verifikation behobene Bugs

1. **CLI `effect static`/`gradient` → AttributeError.**
   `handle_effect` las `args.period`, `args.duration`, `args.frame_interval`
   bedingungslos aus; diese Args existieren aber nur bei animierten Effekten
   (`_common(..., animated=True)`). Statische Effekte crashten beim Dispatch.
   Fix: `getattr(args, ..., default)` mit den Defaults von `run_effect`.
   (Die bestehenden 9 Unit-Tests riefen `run_effect` direkt auf und deckten
   den CLI-Dispatch-Pfad nicht ab.)
2. **GUI startete nicht (`gi` undefiniert).** `roccat_aimo_gui.py` rief
   `gi.require_version("Gtk","4.0")` vor `import gi` → NameError. `import gi`
   ergänzt.
3. **Lint-Säuberung:** ungenutzte Imports entfernt (bridge `handle_effect`:
   `EFFECT_HELP`, `backend_for`; Testdatei: `pytest`, `KONE_NUM_LEDS`). ruff
   komplett grün.

## Leere/verwaiste Arbeitsbaum-Änderungen

Beim Start der Verifikation lagen im Arbeitsbaum unkommittete, beschädigte
Edits (u. a. `from aimo_effects import STATIC_EFFECTS,CTS` — Syntaxfehler, aus
der abgestürzten Vor-Run-Runde). Diese wurden verworfen (Stash gelöscht);
komitteter Stand `b0b87f7` ist die saubere Implementierung.

## Protokoll-Checks im Detail (e2e_cli_mock.py)

```
list rc=0                                                  PASS
effect static vulcan rc=0 → 7 writes                        PASS
  je write len 65, report-id 0, Header [0xa1,0x01,0x01,0xb4] PASS
  LED0 Rot=255 an Byte 5                                    PASS
effect static kone rc=0 → 1 Feature-Report                  PASS
  len 46, Header [0x0d,0x2e], LED0 Grün=255                 PASS
effect-list rc=0 (5 Effekte)                                PASS
effect colorcycle kone rc=0 → ≥2 Frames (6)                 PASS
effect gradient vulcan/kone rc=0                            PASS
effect breathing kone (anim) rc=0                           PASS
effect wave vulcan (anim) rc=0                              PASS

Unit-Tests: 9 passed (Render-Shapes/Range, Brightness-Skalierung,
Vulcan-LED-Map-Layout, Kone-LED-Map, run_effect-Dispatch, effect_list)
```

## Artefakte

- `tests/e2e_cli_mock.py` — wiederholbarer End-to-End-CLI-Check (Mock-HID)
- Befehle zur Reproduktion: siehe README „Tests / Verifikation“
