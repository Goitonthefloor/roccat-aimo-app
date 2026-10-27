# AIMO-Modus: Auswertung des Reverse-Engineering-Runs

## Umfang und Quellen

- Primärer Run: Kanban `roccat-swarm-aimo/t_cc244cb8`, Versuch 7 vom 19.10.2026, Hermes-Session `@session:default/20261019_141306_5d3c21`; statische REA-/Ghidra-12.1.4-Analyse. Run-Protokoll und Evidence-Dateien: `~/.hermes/kanban/boards/roccat-swarm-aimo/workspaces/t_cc244cb8/findings/`. Persistenter Bericht: [AIMO_PROTOKOLL.md](AIMO_PROTOKOLL.md), insbesondere Abschnitte 2–4 und 8. Git-Historie: `07f89b1`, `e9787be`.
- Untersucht: Swarm 1.9482, `aimo.dll`, `AimoEffect.dll`, `ROCCAT_Swarm_Monitor.exe`, `HIDDLL.dll`; Installer-SHA256 `8d54e1e5af78deba984ae2451f7aa7c1e7e6a0f806ed0b8c28e44c6e1f012fa8` hier erneut geprüft. Farbdatei: `~/.hermes/attachments/swarm_extract/data/Swarm/aimo_color_theme.dat`.
- Evidenz: `aimo_overview.json` (`ev_d27f1ed24cd26e5949288e3d2faa4e5f0dabe8533d166c571f369e9f4e6df26b`), `str_wave.json` (`ev_39ff83e8` laut Bericht), `fn_create_ctrl.json`, `fn_ledmap.json`, `fn_start_effect.json`, `fn_hid_send.json`; Monitor-Tabellenadressen siehe [AIMO_PROTOKOLL.md](AIMO_PROTOKOLL.md#8-findings-ledger). Diese Ergebnisse sind statisch, keine Laufzeitbeobachtung der Swarm-Oberfläche.

## Befunde und Grenzen

`aimo.dll` enthält Effekt-Controller und RTTI-Namen von Effektklassen; `AimoEffect.dll` enthält u. a. Gradienten- und LED-Mapping-Logik; der Monitor enthält HID-bezogene Tabellen und Transportfunktionen. Shared-Memory-Namen umfassen `aimo_effect/Swarm`, `aimo_effect/Monitor` und `aimo_light_effect/Swarm`. Das stützt eine softwareseitige Effekt-/Farbverarbeitung, beweist aber nicht den vollständigen Datenfluss für jedes Gerät oder dass ausschließlich Softwareeffekte existieren. Der vorliegende Pseudocode `fn_start_effect_pseudo.txt` zeigt eine Lookup-/indirekte Aufrufstruktur, keine zugeordneten Effekt-IDs oder den vollständigen AIMO-Smart-Algorithmus.

Der ältere Bericht behauptet ein universell exaktes Protokoll, einen einzigen HID-Report und Theme 0 als AIMO-Signatur. Dafür reicht die statische Evidenz nicht aus: Report-Tabellen müssen jeweils einem konkreten Gerät und Kommunikationspfad zugeordnet werden; die bestehende Implementierung nutzt bei Vulcan mehrere Pakete. Eine Palette beweist weder Default noch Erscheinungsbild des adaptiven Modus. Keine dieser Aussagen als Verhaltensgarantie übernehmen.

## Konkrete Skill-/Fähigkeitenliste für die Nachbildung

„Skills“ bezeichnet hier **Implementierungsfähigkeiten/Effektfamilien**, keine nachgewiesenen ladbaren Swarm-Plugins. Die genannten RTTI-Namen sind statische Hinweise; ihre Existenz beweist weder UI-Verfügbarkeit noch eine Pflichtabhängigkeit des AIMO-Smart-Modus.

| Fähigkeit / Effekt | Evidenz bzw. vorhandener Projektbestand | Übernahme / Status |
|---|---|---|
| Geräte entdecken und Fähigkeiten pro VID/PID unterscheiden | `src/roccat_rgb.py`, `src/roccat_aimo_bridge.py` | Voraussetzung; nur validierte Gerätepfade auswählen. |
| LED-Positionen und Mapping je Gerät | REA `fn_ledmap.json`; `ledpositions`, `ledenumeration`; `src/aimo_effects.py` | Für räumliche Animation nötig; projektseitige Ersatzgeometrie nicht als Original-Layout ausgeben. |
| Farbthemen, Gradienten und Helligkeit | `aimo_color_theme.dat`, Qt-Gradienten; `src/aimo_themes.py` | Farbwerte vor Nutzung berichtigen/prüfen; Default und Regelung unbekannt. |
| Zeitbasierte Frame-Berechnung und sicherer Start/Stopp | Thread-RTTI in `str_wave.json`; `src/aimo_effects.py`, `src/roccat_aimo_gui.py` | Bestehende Engine wiederverwenden; exakte Taktung und Lebenszyklus von Smart unbekannt. |
| Wave | `wave_thread_c`, `khan_aimo_wave_effect_thread_c`; Projekt `wave` | Vorhandene Nachbildung, nicht als originalgetreu belegt. |
| Breathing | `breath_thread_c`, `breath2_thread_c`; Projekt `breathing` | Vorhandene Näherung; Kurven und Parameter unbekannt. |
| Heartbeat | `heartbeat_thread_c`, `heartbeat2_thread_c`, `kone_aimo_heartbeat_thread_c`; GUI-/RGB-Effekt `beat` | RTTI belegt Familie, keine Gleichsetzung mit Smart oder identischen Kurven. |
| Color-Cycle | `cycle_color_base_c`, `cycle_breathing_thread_c`, `cycle_fully_lit_thread_c`, `cycle_heartbeat_thread_c`; Projekt `colorcycle` | Vorhandene Näherung; Varianten nicht einzeln bestätigt. |
| Snake, Fade, Ripple, Blinking, Fully Lit, No Effect, Multi | `snake_effect_base_c`, `fade_thread_c`, `ripple_thread_c`, `blinking_thread_c`, `fully_lit_thread_c`, `no_effect_thread_c`, `multi_effect_thread_c` | Kandidaten aus Klasseninventar; weder vollständige Implementierung noch Abhängigkeit von Smart belegt. |
| Gerätespezifische Effekte | `kone_xp_photon_effect_thread_c`, `battery_indication_effect_thread_c` | Nur bei nachgewiesener Geräteunterstützung; keine universelle Voraussetzung. |
| Eingabereaktion, geräteübergreifende Synchronisierung und adaptive Auswahl | Kein belastbarer Ablauf im Run | Für originalgetreues Smart gesondert untersuchen; bestehendes `reactive` nicht als gleichwertig behaupten. |
| HID-Transport | Run-Bericht Referenzen 22, 16, 18; bestehende gerätespezifische `send_led_map`-Pfade | Je Modell prüfen; Reference-Nummern nicht als universelle HID-Report-IDs interpretieren. |

### Geräte- und Farbkonfiguration

Der Bericht nennt Reference 22 mit Usage Page `0xFF00`, Usage `0x01` und Tabellen `count=123/163`, außerdem Reference 16 mit ID `0x11` und Reference 18 mit Endpoint 4. Diese Angaben sind Tabellenbefunde, keine ausreichend verifizierten, universellen Kone-/Vulcan-Schreibrezepte. R/G/B-Offsets müssen pro Gerät, Kanal und vollständiger Tabelle geprüft werden; die im Run vorhandenen `findings/ref22_count*.txt` sind dort weiterhin separat gespeichert, aber nicht Teil dieses Repos. Der Run zeigte bei der 163er-Tabelle G/B nur bis Index 123; Vollständigkeit und Zuordnung deshalb offen.

Die Datei hat 374 Bytes und zehn Listen mit je drei 11-Byte-Farbdatensätzen; erste Farbstopps gemäß den Rohbytes: `(255,0,0)`, `(255,80,0)`, `(230,140,0)`. Die Dokumente [AIMO_PROTOKOLL.md](AIMO_PROTOKOLL.md#4-farb-layout--aimo-palette-aimo_color_themedat) und [roccat-swarm-aimo-analysis.md](roccat-swarm-aimo-analysis.md#aimo_color_themedat-farbthemen) widersprechen sich; `src/aimo_themes.py` entspricht Letzterem und beginnt stattdessen mit Weiß/Weiß/Beige. Vor Übernahme **alle** Farbwerte anhand eines überprüften Qt-Deserializers neu abgleichen; die Bezeichnung als Standard- oder Signaturtheme ist nicht belegt. `AimoBrightness` ist ein gefundener Konfigurationsname; Reichweite und konkrete Skalierung sind nicht nachgewiesen.

## Auslöser, Zustände und UI

**Original-Swarm:** Der statische Run belegt weder konkreten UI-Auslöser noch die Zustandsübergänge des Smart-Modus, dessen Interaktionsreaktionen, Persistenz, Fehlerbehandlung oder welche Controls dann deaktiviert sind. Der Fund `start_effect` und die Shared-Memory-Namen belegen keine konkrete Radio-Button-Semantik. Ein UI-Verhalten des Originals lässt sich aus diesen Ergebnissen nicht zuverlässig rekonstruieren.

**Anforderung an unsere UI, nicht als Originalbefund:** Die übergeordnete Karte `t_0342c0f2` verlangt einen Radio-Button: AIMO aktivieren und andere Schaltflächen deaktivieren. Für die nachgelagerte Implementierung bietet sich folgende explizite Zustandsbeschreibung an:

| Zustand | UI / erwarteter Übergang |
|---|---|
| Kein Gerät / Fehler | Aktivierung nicht als erfolgreich darstellen; bei fehlendem Gerät bzw. Fehler einen verständlichen Status anzeigen. |
| Manuell | Manuelle Effekte und Gerätesteuerung nutzbar; Aktivieren fordert den Start des AIMO-Modus an. |
| Start ausstehend | Konkurrierende Aktionen sperren; erst nach bestätigtem Start als aktiv darstellen. |
| AIMO aktiv | Radio-Button ausgewählt; konkurrierende Schaltflächen deaktiviert, Deaktivierung selbst bleibt möglich. Welche übrigen Bedienelemente gesperrt werden, ist Produktentscheidung, kein REA-Befund. |
| Stopp ausstehend | Konkurrierende Aktionen bis zur tatsächlichen Beendigung gesperrt; danach manuelle Kontrolle wiederherstellen. |
| Start-/Laufzeitfehler oder Geräteverlust | Effekt beenden bzw. Zustand zurücksetzen und Fehler anzeigen; keine aktive Anzeige ohne laufenden Effekt. |

Eine solche Steuerung und eine frei gewählte Animation sind **keine originalgetreue Rekonstruktion** des adaptiven AIMO-Algorithmus. Eine Annäherung muss im Produkt entsprechend gekennzeichnet werden.

## Offene Fragen / Annahmen

1. Welche konkreten Eingaben, Zustände, Zeitkonstanten und Zufalls-/Anpassungsregeln bestimmen Smart? Wie werden Geräte synchronisiert?
2. Wie sieht die Original-UI beim Aktivieren, Deaktivieren, Geräteverlust und Neustart tatsächlich aus? Welche Einstellungen bleiben verfügbar und persistent?
3. Welche Klassen sind tatsächlich Smart-Abhängigkeiten, welche lediglich andere auswählbare Effekte? Effekt-IDs und Parameter sind nicht extrahiert.
4. Welche Report-Tabelle, Paketgrenzen und Kanäle gehören konkret zu den unterstützten VID/PIDs? Originalhardware- und Mitschnittprüfung stehen aus.
5. Welcher Qt-Farbdecoder ist korrekt, und welches Theme wird tatsächlich standardmäßig genutzt? Beide vorhandenen Projektquellen widersprechen sich.
6. Wie verhält sich Swarm, wenn die Software endet, und laufen manche Effekte geräteintern weiter? Pauschale Negativaussagen vermeiden.

Für verlässliche Antworten sind gezielte statische Verfolgung und, sofern ausdrücklich freigegeben und in geeigneter Windows-Umgebung verfügbar, beobachtete Original-UI-/Gerätelaufzeit samt HID-Mitschnitt nötig. Dieser Bericht selbst führt weder Swarm noch Hardware aus.
