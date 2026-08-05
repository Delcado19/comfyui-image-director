# Implementierung: `validate_edit_plan(check_consistency=True)`

Joint-Entscheidung mit Codex (Thread `019fd14f-0515-7a91-958a-ce162f468ce2`),
Umsetzung nach expliziter Nutzerfreigabe.

## Scoping-Klärung vor der Implementierung

Vor dem Schreiben von Code wurde geklärt, ob ein "Validator" hier überhaupt
sinnvoll ist: der Render-Pfad (`build_router_graph.py`) konsumiert
ausschließlich `task`/`prompt` aus dem Analyzer-Plan - `is_local_region`,
`edits[]`, `images[].role`, `preserve[]` fließen aktuell **nirgends** in das
gerenderte Bild ein. Ein produktives Reject/Re-Request-Gate hätte also
aktuell keine Wirkung, und ComfyUI-Graphen sind DAGs ohne native
Retry-/Loop-Konstrukte - ein solches Gate würde entweder das
"ein Graph, ein Queue-Press"-Designprinzip brechen (externer
Python-Retry-Wrapper) oder in stiller Korrektur enden (widerspricht Codex'
Empfehlung, Korrektur erst nach Nachweis der Sicherheit einzusetzen).

**Entscheidung:** nur ein diagnostischer, wiederverwendbarer Baustein -
keine Graph-Verdrahtung, kein Reject/Re-Request, keine stille Korrektur.

## Änderung

`image_director/edit_plan_schema.py`: `validate_edit_plan()` bekommt einen
neuen, standardmäßig deaktivierten Parameter `check_consistency: bool =
False` (keyword-only, keine Signaturänderung für bestehende Aufrufer -
`check_json_plan.py`s bestehender Aufruf bleibt unverändert).

Bei `check_consistency=True` werden zwei zusätzliche Fehlerklassen erkannt
(beide rein diagnostisch, ändern nichts am gerenderten Ergebnis):
1. `edits[].subject` ist konkret (kein Platzhalter "entire image") + eine
   lokal-artige `operation` (`replace`/`remove`/`adjust`) + `reference_slots`
   vorhanden, ABER `is_local_region` ist `False`.
2. `edits[].subject` ist konkret, ABER `edits[].region` ist ein Platzhalter
   ("entire image"/"full image").

## Validierung

`tests/router/test_consistency_check.py` (assert-basiert, kein Framework):
- Reproduziert den echten Fehlerfall aus `AFRv3_results.json` (Seed 99002,
  `RESULTS_analyzer_field_reliability_v3.md`) - beide neuen Fehlerklassen
  werden korrekt erkannt.
- Bestätigt keine Regression: `check_consistency=False` (Default) verhält
  sich exakt wie vorher (keine Fehler für denselben Plan).
- Bestätigt keine Fehlalarme: ein konsistenter Plan (`is_local_region=True`,
  konkretes `region`) erzeugt bei `check_consistency=True` keine Fehler.

Lief erfolgreich: `python tests/router/test_consistency_check.py` -> `OK`.

## Status

Kein Aufrufer nutzt `check_consistency=True` in Produktionscode - der
Router (`build_router_graph.py`) bindet ihn nicht ein, da er die
betroffenen Felder ohnehin nicht konsumiert. Verfügbar für künftige
Nutzung, sobald `is_local_region`/`edits[]` tatsächlich in eine
Rendering-Entscheidung einfließen (z. B. Masking/Region-Conditioning) -
dann kann derselbe Check zu einem echten Gate werden, statt nur zu messen.
