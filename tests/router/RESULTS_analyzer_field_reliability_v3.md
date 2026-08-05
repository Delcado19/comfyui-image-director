# Ergebnis: v3-Guidance-Nachtest für Fall 3 (`analyzer_field_reliability_v3.py`)

Codex-Design und -Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.
Follow-up zu `RESULTS_analyzer_field_reliability.md`'s 5/5-Fehlschlag
(`is_local_region: false`, `edits[0]` = "entire image"/"full image") unter
der aktuellen Baseline-`GUIDANCE`.

## Ausgangspunkt

Beim Wiederlesen von
`tests/schema/analyzer-json-structured/PROMPT_EXPERIMENT_2026-08-03.md`
(ein früheres, separates Experiment vom Vortag) fiel auf: dort wurde
bereits ein Fix für genau diese Fehlerklasse getestet - Schema-Feld-
Umsortierung (`is_local_region`/`images`/`edits`/`preserve` vor
`user_instruction`/`prompt`) plus explizite Formulierung ("nenne ein
konkretes Subjekt statt 'entire image', wenn eines existiert"). Das hat
damals für Ein-Referenz-Einzeleditfälle (`edit_reference_2image`) sauber
funktioniert, wurde aber verworfen, weil es bei einem 3-Bild-
Mehrfach-Edit-Fall eine neue Regression verursachte - nicht wegen eines
Problems im Ein-Referenz-Fall.

Da Fall 3 (Kleid-Umfärbung) genau die Form ist, für die der v3-Fix damals
funktionierte, wurde er hier gezielt (nur `reference_count<=1`, ohne den
3-Bild-Pfad anzufassen) auf Fall 3s echtem Foto/Referenzbild
nachgetestet - mit dem billigen Analyzer-only-Harness (kein `KSampler`).

## Setup

Gleiche 5 Seeds wie `RESULTS_analyzer_field_reliability.md`
(`99002`-`99006`), gleiche Bilder/Instruktion. Schema-Feldreihenfolge und
Wortlaut aus `runs_v3/edit_reference_2image.graph.json` übernommen,
generalisiert auf variable Instruktion (nicht mehr die alte
Formen-Testfixture) - unverändert nur für `reference_count<=1`.

## Ergebnis (5/5 Samples, konsistent)

| Feld | Baseline (`RESULTS_analyzer_field_reliability.md`) | v3 |
|---|---|---|
| `is_local_region` | `false` (5/5, falsch) | `false` (5/5, weiterhin falsch) |
| `edits[0].subject` | `"entire image"` (5/5, falsch) | `"woman's leather dress"` (5/5, **korrekt**) |
| `edits[0].region` | `"full image"` (5/5, falsch) | `"entire image"` (5/5, weiterhin falsch) |
| `prompt` enthält "background" | 2/5 | 0/5 (verbessert) |
| `preserve[]` | uneinheitlich formuliert | konsistent `["background"]` (5/5) |

**Teilverbesserung:** das konkrete Subjekt (`"woman's leather dress"`) wird
jetzt zuverlässig erkannt und benannt - vorher immer der Platzhalter. Aber
`is_local_region` und `region` folgen dieser Erkenntnis nicht - beide
bleiben in allen 5 Fällen falsch. Das Modell "weiß" also implizit, dass es
ein konkretes Subjekt gibt (steht im `subject`-Feld), propagiert das aber
nicht auf die verwandten Felder `is_local_region`/`region`.

## Codex' Bewertung (Zitat, gekürzt)

> No-go on another wording iteration. This is the same cross-field
> consistency wall [...] Do not adopt v3 into the router as-is. A
> half-fixed plan is dangerous because future downstream code will
> reasonably trust `is_local_region`; here it would gate the wrong way
> 5/5. [...] Recommended next step is not more prompt text; it is a
> deterministic post-processor/validator, scoped narrowly: if
> `edits[].subject` is specific and operation is local-ish, reject or
> correct `is_local_region=false`; if `subject != "entire image"` and
> `region` is a placeholder, reject or normalize `region` to `subject`.
> Prefer reject/re-request until correction is proven safe.

## Fazit

Weitere Wortlaut-Iteration wird **nicht** verfolgt (gleiche
Cross-Field-Konsistenz-Grenze wie beim 3-Bild-Fall im Vorexperiment). Die
v3-Guidance wird **nicht** in den Router übernommen - eine halb reparierte
Struktur (korrektes `subject`, aber falsches `is_local_region`/`region`)
ist riskanter als die dokumentierte Baseline-Einschränkung, falls künftiger
Code beginnt, `is_local_region` als verlässliches Boolean-Gate zu
behandeln.

Nächster von Codex vorgeschlagener Kandidat: ein deterministischer
Post-Processor/Validator (kein weiteres Prompting) - z. B. "wenn
`edits[].subject` spezifisch ist und `operation` lokal-artig ist, dann
`is_local_region=false` ablehnen/re-requesten; wenn `region` ein
Platzhalter ist, aber `subject` es nicht ist, `region` ablehnen/auf
`subject` normalisieren". Das ist ein Code-Eingriff in die Router-/
Validierungs-Pipeline (`validate_edit_plan()` bzw. eine neue Schicht
danach) - **nicht gestartet, erfordert eigene Nutzerfreigabe vor
Implementierung**, da es eine Verhaltensänderung an Produktionscode wäre.
