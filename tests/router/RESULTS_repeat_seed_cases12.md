# Repeat-Seed-Zuverlässigkeit für Fall 1 & 2 (`analyzer_field_reliability_cases12.py`)

Schließt einen lang offenen Punkt aus `RESULTS_content_quality.md` ("n=1
per case - no repeat-seed screen") - zumindest für die strukturierte
JSON-Ebene (Analyzer-only, kein `KSampler`, keine Bildgenerierung; visuelle
Zuverlässigkeit bei n>1 bleibt weiterhin ungetestet, siehe "Nicht
abgedeckt" unten).

Gleiche Seeds (`99002`-`99006`) wie die Fall-3-Tests dieser Session, gleiche
Analyzer-Gewichte/Guidance/Schema wie der Router (`build_router_graph.py`,
`reference_count=0` für beide Fälle - keine Referenzbilder).

## Fall 1 — lokale Objektentfernung ("Remove the beer bottle...")

n=5, alle Seeds:
- `task`: `"edit"` (5/5, korrekt)
- `is_local_region`: `true` (5/5, korrekt) - **zuverlässig**, nicht nur ein
  n=1-Zufallstreffer aus `RESULTS_content_quality.md`.
- `edits[0]`: `{"subject": "entire image", "region": "full image",
  "operation": "remove"}` (5/5) - **weiterhin falsch**, reproduziert das
  bereits bei n=1 dokumentierte Platzhalter-Overuse-Muster konsistent über
  5 Seeds. Kein Ausreißer, sondern ein systematischer Fehler.
- Neue `check_consistency=True`-Prüfung: **keine** neuen Fehler (korrekt so
  - das Subjekt selbst ist hier der Platzhalter, nicht "konkret, aber
  region/is_local_region widersprechen" - eine andere, bereits bekannte
  Fehlerklasse, die der neue Check absichtlich nicht doppelt zählt).

## Fall 2 — globales Restyling ("Restyle the entire photo as vintage 1970s...")

n=5, alle Seeds:
- `task`: `"edit"` (5/5, korrekt)
- `is_local_region`: `false` (5/5, korrekt - dies ist ein
  Ganzbild-Restyle, "false" ist hier die richtige Antwort)
- `edits[0]`: `{"subject": "entire image", "region": "full image",
  "operation": "restyle"}` (5/5) - hier ist "entire image"/"full image"
  die **korrekte** Verwendung laut Schema-Design (kein spezifischeres
  Subjekt existiert bei einem Ganzbild-Stiltransfer).
- Neue `check_consistency`-Prüfung: keine Fehler (korrekt, vollständig
  konsistenter Fall).

**Fall 2 ist bei n=5 vollständig stabil und fehlerfrei.**

## Fazit

- Fall 2 (globales Restyling) ist strukturell zuverlässig - kein
  Repeat-Seed-Risiko gefunden.
- Fall 1 (lokale Entfernung) ist bei `is_local_region` zuverlässig, aber
  bei `edits[].subject`/`.region` **systematisch** falsch (5/5, nicht nur
  n=1) - bestätigt, dass das Platzhalter-Overuse-Problem kein Einzelfall
  ist. Da der Render-Pfad diese Felder nicht konsumiert, hat das (wie bei
  Fall 3 dokumentiert) keinen Effekt auf das sichtbare Ergebnis - Fall 1
  bestand den visuellen Test bei n=1 trotzdem.
- Die neue Konsistenzprüfung (`RESULTS_consistency_check.md`) erzeugt bei
  keinem der beiden Fälle einen Fehlalarm - sie ist korrekt auf die
  spezifische "Subjekt konkret, aber Feld widerspricht"-Inkonsistenz
  begrenzt und vermischt sich nicht mit dem separaten
  Platzhalter-Kollaps-Muster.

## Nicht abgedeckt

Dies ist weiterhin nur die JSON-Planebene, kein visueller Repeat-Seed-Test
(kein `KSampler` gelaufen). Ob die *gerenderten Bilder* für Fall 1/2 bei
n>1 ebenso zuverlässig bleiben, ist weiterhin offen - das würde einen
vollen Render-Durchlauf pro Seed erfordern (teurer, nicht in diesem
Billig-Test enthalten).
