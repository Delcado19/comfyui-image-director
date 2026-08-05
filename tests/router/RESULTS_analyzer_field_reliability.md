# Ergebnis: Analyzer-Feld-Zuverlässigkeit (`analyzer_field_reliability.py`)

Codex-Design und -Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.

Ausgangsfrage: Nachdem zwei Prompt-Level-Fixversuche für das
"background"-Wort-Bleeding gescheitert sind (Analyzer-Guidance-Klausel,
Negative-Prompt - siehe `RESULTS_ab_background_word.md` und
`RESULTS_ab_negative_prompt.md`), war der nächste vorgeschlagene Kandidat:
den an `TextEncodeQwenImageEditPlus` übergebenen Text deterministisch aus
den strukturierten Feldern `edits[]`/`preserve[]` zu bauen, statt den
freien `prompt`-Text des Analyzers direkt zu verwenden - in der Annahme,
dass die kurzen, strukturierten Feld-Strings zuverlässiger/kontrollierbarer
formuliert sind als freie Prosa.

Vor der Implementierung: gemeinsam mit Codex ein reiner Analyzer-Test
entworfen (kein `KSampler`, keine Bildgenerierung - nur die strukturierte
JSON-Ausgabe wird geprüft), um diese Annahme zu validieren, bevor Aufwand in
den Umbau des Prompt-Pfads gesteckt wird.

## Setup

Gleiche Fall-3-Instruktion/Bilder wie in `RESULTS_content_quality.md`:
`IMG_7148.jpg` + `imgdir_test_ref2.png`, Instruktion "Change the color of
the woman's leather dress to match the color shown in the reference image."
`n=5`, Seeds `99002`-`99006`, aktuelle `GUIDANCE`, aktuelles Schema
(`reference_count=1`). Nur `QwenVLStructuredGGUF` + `PreviewAny` - kein
Bild-Branch.

## Ergebnis (5/5 Samples)

| Seed | `is_local_region` | `edits[0].subject`/`.region` | `prompt` enthält "background" |
|---|---|---|---|
| 99002 | `false` | `"entire image"` / `"full image"` | nein |
| 99003 | `false` | `"entire image"` / `"full image"` | ja |
| 99004 | `false` | `"entire image"` / `"full image"` | ja |
| 99005 | `false` | `"entire image"` / `"full image"` | nein |
| 99006 | `false` | `"entire image"` / `"full image"` | nein |

- `task`: in allen 5 korrekt `"edit"`.
- `is_local_region`: in **5/5 falsch** (`false` statt `true` - dies ist ein
  lokaler Kleid-Farbwechsel, keine Ganzbild-Transformation).
- `edits[]`: in **5/5** exakt ein Eintrag mit `subject: "entire image"`,
  `region: "full image"` - genau die von Codex als Fehlschlag definierten
  Platzhalter-Scene-Wörter, konsistent über alle Seeds.
- `prompt`-Feld: enthält "background" in 2/5 (bekannte Nichtdeterminismus,
  siehe `RESULTS_ab_background_word.md`) - in den anderen 3/5 eine
  brauchbare, nicht scene-lastige Formulierung.
- `preserve[]`: enthält "background" in 4/5 (einmal als längere
  beschreibende Phrase). Laut Codex' Vorgabe **nicht** als Fehlschlag
  gewertet - "preserve: background" ist eine plausible Anweisung ("Hintergrund
  beibehalten"), kein Symptom des Bleeding-Fehlers.

## Codex' Bewertung (Zitat, gekürzt)

> Deterministic prompt construction from current schema fields is a no-go.
> The fields it would trust are wrong 5/5: `is_local_region=false`,
> `subject="entire image"`, `region="full image"`. Building on that would
> encode the failure more deterministically. [...] One important nuance:
> the free-text `prompt` is flawed but sometimes usable; the structured
> fields are currently not reliable enough to replace it.

## Fazit

Die strukturierten Felder (`is_local_region`, `edits[].subject`/`.region`)
sind für diesen Fall **nicht zuverlässiger**, sondern **durchgängig
falsch** - schlechter als der freie `prompt`-Text, der zumindest in 3/5
Fällen brauchbar war. Die deterministische Prompt-Konstruktion aus
Schema-Feldern wird **nicht implementiert** - der Kandidat wurde vor der
Implementierung getestet und verworfen, nicht nach einem gescheiterten
Bauversuch.

Damit gelten Prompt-/Schema-Feld-Level-Mitigationen für dieses Fehlerbild
(mit der aktuellen `GUIDANCE` und dem aktuellen Schema) als ausgeschöpft.
Nächste sinnvolle Kandidaten (beide nicht gestartet, keiner erwiesen):
- Masking/Region-Conditioning für Garment-Edits (strukturelle Änderung am
  Render-Graphen).
- Ein eigenständiges Analyzer-Qualitätsprojekt, das `is_local_region`- und
  Platzhalter-Overuse-Fehlklassifikation ursächlich behebt, bevor diese
  Felder überhaupt als Render-Eingabe taugen.

Beide sind größere, eigene Entscheidungen und nicht in diesem Test
validiert - hier wird nur festgehalten, dass der kleinere/billigere
Kandidat (Templating) geprüft und verworfen wurde.
