# AIMO-Effekte für die Linux-RGB-Software (roccat-aimo)

Priorisierte, durch Evidenz belegte Liste der AIMO-Effekte, die die
Linux-Software nachbilden soll. Nichts hier ist erfunden — jeder Effekt ist
entweder durch REA-Evidence aus der Roccat-Swarm-Analyse oder durch die
Eruption-Quellen belegt; ungesicherte Punkte sind explizit markiert.

## Evidenzquellen

| Quelle | Inhalt | Relevanz |
|---|---|---|
| `roccat-swarm-aimo-analysis.md` (REA-Doku, docs/) | Architektur von `AimoEffect.dll` (Gradienten-Engine), `aimo.dll` (Effekt-Steuerung), 10 Themes aus `aimo_color_theme.dat` | BELEGT (REA, Swarm v1.9482) |
| `swarm_extract/data/Swarm/aimo_color_theme.dat` (374 B) | Primärquelle: Header `00 00 00 0a 00 00 00 03` = 10 Themes, je 3 Farbstopps | BELEGT (REA, primär) |
| `eruption/.../roccat_kone_aimo.rs` | Kone-AIMO-Treiber: 11 LEDs (LED_0..LED_10), `send_led_map` via Report 0x0d (46-B-Report, RGBA×11 + Helligkeit) | BELEGT (Eruption) |
| `eruption/.../roccat_vulcan_1xx.rs` | Vulcan-100/12x-Treiber: 143 Keys, 6×21-Grid, Ctrl-If 1 + LED-If 3, `send_led_map` (448-B-Puffer, 7×64-B-Chunks), hardware-Wave-Command (auskommentiert) | BELEGT (Eruption) |
| `github/roccat-aimo-app/src/` | Ist-Stand der Linux-Software: `aimo_themes.py`, `set_vulcan_led_map`, `apply_aimo_theme`, CLI `aimo` | Ist-Stand |

## Grundprinzip der Umsetzung

**Alle Effekte = Software-gerenderte per-Key-LED-Map → `send_led_map`.**
Das ist genau der Weg, den Eruption für Kone und Vulcan geht: Die Effekte
werden auf einem Canvas berechnet und jede LED per HID-Feature-Report gesetzt.
Es gibt **keinen** "Ein-Modus-Command" für Wave/Breathing/Rainbow auf diesen
Geräten in Eruption — die Verhaltensmodi liegen in Software (Lua-Skripte:
`pulse.lua` = Atmen, `gradient.lua`/`afterhue.lua` = Farbzyklus, `stripes.lua`
= Welle), nicht im Gerät.

**Ausnahme (BELEGT, aber nicht empfohlen als Hauptweg):** der Vulcan-Treiber
enthält einen auskommentierten *hardware-Wave*-Befehl — Report `0x0d`
(443-B-Frame) mit zwei Geschwindigkeits-Bytes (`byte5`: 01 langsam / 06 mittel /
0b schnell; `byte441`: 1e / 23 / 28) sowie Report `0x13` (Modus-Byte). Eruption
ersetzt das bewusst durch Software-"custom effects" (0x13 mit `0x01`), weil der
Frame nicht dokumentiert ist und kein Richtungs-/Farbparameter bietet. → Wave
bevorzugt software-seitig.

### Geräte-Referenz (für Machbarkeitsspalten)

- **Kone AIMO** (Maus): **11 LEDs** (LED_0..LED_10), als Ring/Linie. Kein
  Raster. `send_led_map`: 46-B-Report `[0x0d, 0x2e, RGBA×11]`, Kanäle mit
  `brightness/100` skaliert.
- **Vulcan AIMO (100/12x)** (Tastatur, "144 Tasten"): **143 Keys**, Grid
  6 Reihen × 21 Spalten. Zwei HID-Interfaces (Ctrl=1, LED=3). `send_led_map`:
  448-B-Puffer, Header `[0xa1, 0x01, 0x01, 0xb4]`, Farben in 12er-Blöcken
  sortiert (`offset = ((i/12)*36) + (i%12)`, dann +12=Grün, +24=Blau),
  7 Chunks à 64 B je 65-B-Write auf das LED-Interface.

> Hinweis: Die frühere REA-Doku beschreibt das Vulcan-Chunking als
> "6 Chunks à 60 B, Header `[0xa1, cntr+1, 0x00, 0x00]`". Der aktuelle
> Eruption-Treiber verwendet 7×64 B mit Header `[0xa1,0x01,0x01,0xb4]`.
> Für die Implementierung (Task t_ae245e78) ist die **aktuelle Eruption-Variante**
> maßgeblich; die Formel `((i/12)*36)+(i%12)` ist in beiden identisch.

---

## Effektliste (priorisiert)

Evidenz-Status:
- **BELEGT (REA)** — direkt in Swarm-Binary/`.dat` nachgewiesen.
- **BELEGT (Eruption)** — in Eruption-Quellen als realisierbar nachgewiesen.
- **VERMUTET/UNGESICHERT** — software-seitig machbar, aber kein direkter
  Namenstreffer in den Swarm-Binaries; Klassifikation offen.

### E1 — AIMO-Theme-Gradient (statischer Farbverlauf) ★★★★★ TOP
- **Name im Swarm-Vokabular:** `aimo_effect/Swarm` bzw. `aimo_light_effect/Swarm`
  (AimoEffect.dll), Farbthemen aus `aimo_color_theme.dat` (10 Themes × 3 Stopps).
  Die REA-Architektur zeigt: **AIMO-Effekte sind Farbverläufe (QLinearGradient)**.
- **Parametrisierung:** Theme-ID (1–10) oder freie 3×RGB-Stopps; Richtung
  (horizontal `h` / vertikal `v`); optional Helligkeit.
- **Linux-Umsetzung:** per-Key-LED-Map, Farbverlauf über die LED-Positionen
  per Gradient-Interpolation (linear zwischen den 3 Stopps). **Bereits
  implementiert** in `aimo_themes.py` (10 Themes, `gradient_color()`) +
  `apply_aimo_theme()` + CLI `aimo <theme>`.
- **Machbarkeit:** Vulcan voll (143-er Grid, Richtung sinnvoll); Kone gut
  (Gradient über den 11-er Ring ≤ 1D).
- **Status:** BELEGT (REA). Das ist der "AIMO-Schmuckkern" und soll priorisiert
  bleiben. Deckt zugleich "Statische Farbe" ab, wenn alle Stopps gleich sind.

### E2 — Statische Einzelfarbe / "Static"
- **Name im Swarm-Vokabular:** kein eigener String gefunden; entspricht einem
  konstanten Gradienten (Spezialfall von E1) bzw. `set_vulcan_key_rgb` (Taste).
- **Parametrisierung:** 1×RGB (+ Helligkeit).
- **Linux-Umsetzung:** konstante per-Key-LED-Map via `send_led_map`; Einzeltasten
  bereits via Report 0x0B (`set_vulcan_key_rgb`).
- **Machbarkeit:** beide trivial.
- **Status:** BELEGT (Eruption-LED-Map-Mechanismus; trivialer Spezialfall von E1).

### E3 — Wave (Welle über die Tasten)
- **Name im Swarm-Vokabular:** "Wave" als Roccat-Marketingname bekannt; **kein
  String im Swarm-Binary** gefunden → Nomenklatur VERMUTET/UNGESICHERT.
- **Parametrisierung:** Farbpalette (aus E1-Theme oder Regenbogen), Geschwindigkeit,
  Richtung (über das Grid: horizontal/vertikal/diagonal).
- **Linux-Umsetzung:** Software — Wellenfunktion über die LED-Grid-Positionen,
  je Frame per `send_led_map`. (Alternativ hardware-Befehl 0x0d/0x13 des Vulcan,
  aber undokumentiert → nicht Hauptweg.)
- **Machbarkeit:** **Vulcan ideal** (6×21-Grid, Wellenrichtung optisch
  sinnvoll). **Kone: eingeschränkt** — nur 11 LEDs, eine "Welle" ist nur ein
  kurzer Verlaufs-Burst; nur als Effekt-Showelement sinnvoll, nicht als
  Standardmodus.
- **Status:** Hardware-Befehl BELEGT (Eruption vulcan_1xx.rs, auskommentiert);
  Software-Variante BELEGT (Eruption-scriptbasiert); Swarm-Namenstreffer fehlt.

### E4 — Breathing / Pulse (Atmen)
- **Name im Swarm-Vokabular:** kein String im Swarm-Binary; Software-Äquivalent
  in Eruption: `pulse.lua` → VERMUTET/UNGESICHERT für exakte Swarm-Entsprechung.
- **Parametrisierung:** Farbe (1) oder Farbzyklus (mehrere); Frequenz/Periode;
  Helligkeitsbereich (min–max).
- **Linux-Umsetzung:** Software — `send_led_map` je Frame, Helligkeit mit
  sinusförmiger Hüllkurve über der gewählten Basisfarbe/Gradienten animieren
  (tick-Loop im Daemon).
- **Machbarkeit:** **beide gut** (reine Helligkeitsmodulation, kaum
  Positionsabhängigkeit). Kone ideal (wenige LEDs).
- **Status:** BELEGT (Eruption pulse.lua) als realisierbar; Swarm-Bezug
  ungesichert.

### E5 — Rainbow / Color-Cycle (Farbzyklus)
- **Name im Swarm-Vokabular:** keine explizite "Rainbow"-String im Binary;
  Software-Äquivalent in Eruption: `gradient.lua`, `afterhue.lua`
  (Hue-Rotation). Bunte Themes bereits in `aimo_color_theme.dat`
  (z. B. Theme 6/9 = Blau/Gelb) → VERMUTET/UNGESICHERT für Swarm-Namenstreffer.
- **Parametrisierung:** Hue-Rotation, Geschwindigkeit, Sättigung; optional
  an ein E1-Theme gekoppelt.
- **Linux-Umsetzung:** Software — Hue über die Zeit rotieren, je Frame
  `send_led_map` (statisch über alle Tasten oder als wandernder Verlauf).
- **Machbarkeit:** Vulcan gut; Kone machbar (11 LEDs), aber wenig differenziert.
- **Status:** BELEGT (Eruption) als realisierbar; Swarm-Nomenklatur ungesichert.

---

## Priorisierung / Empfehlung für die Umsetzung (Child t_ae245e78)

Reihenfolge (Aufwand klein → groß, Wert hoch → niedrig):

1. **E1 AIMO-Theme-Gradient** — bereits vorhanden, ausbauen/unifizieren
   (Einheitliches Effekt-Modell auf `send_led_map`; beide Geräte).
2. **E2 Static** — via E1 (Stopps = gleich); Kleinigkeit.
3. **E4 Breathing** — einfacher Software-Tick-Effekt; gut auf Kone.
4. **E5 Color-Cycle** — Hue-Animation; moderate Komplexität.
5. **E3 Wave** — nur auf Vulcan attraktiv; als letztes. Kone: als optionaler
   Verlaufs-Burst markieren, nicht als Standardmodus empfohlen.

**Umsetzungs-Hinweise:**
- Ein gemeinsames Software-Rendering-Modul pro Frame erzeugen → `send_led_map`
  (deckt E3/E4/E5 und baut auf E1 auf). Kein neues Hardware-Protokoll nötig.
- Kone (11 LEDs, 46-B-Report 0x0d) und Vulcan (143 Keys, 448-B/7×64-B) brauchen
  je eigene `send_led_map`, aber **eine gemeinsame Effekt-Engine** über den
  gerätespezifischen LED-Indizes.
- Helligkeit als globaler Multiplikator (Eruption skaliert mit
  `brightness/100`) — in die Engine einbauen.

## Offen / Ungesichert (ehrlich markiert)
- Exakte Swarm-Namen für "Wave/Breathing/Rainbow" sind **nicht** im
  ausgewerteten Swarm-Binary belegt; das Binary belegt primär die
  **Gradienten-Themen** (E1). Die Modus-Namen stammen aus Roccat-Marketing /
  Eruption-Zuordnung.
- Der hardware-Wave-Befehl (0x0d/0x13) des Vulcan ist undokumentiert; nur als
  Experimentierfeld sinnvoll.
- Ein animiertes "AIMO-Smart-Glow" (Theme bewegt sich dynamisch) ist software
  machbar (= E5 auf E1-Palette), aber als eigenständiger Swarm-Modus nicht
  belegt → optional, nicht Teil des Kernumfangs.
