# Ergebnis: Few-Shot + v3 Pre-Screen und Regressionscheck

Codex-Design und -Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.
Follow-up zu `RESULTS_analyzer_field_reliability_v3.md`'s Teilverbesserung
(Subjekt korrekt, aber `is_local_region`/`region` weiterhin falsch, 5/5).
Testet die beiden von `PROMPT_EXPERIMENT_2026-08-03.md` genannten, aber nie
ausprobierten Kandidaten: `temperature=0` und Few-Shot-Beispiele.

## Vorabtest: `temperature=0`, n=1 (Sanity-Check)

Baseline-Guidance, `temperature=0` statt `0.1`. Ergebnis: **identisch** zum
5/5-Fehlschlag bei `temperature=0.1` (`is_local_region: false`, Platzhalter
`edits[]`). Bestätigt: der Fehler ist ein stabiler Modell-Modus, kein
Sampling-Rauschen - `temperature=0` ist damit kein Fix, nur eine
Bestätigung dieser Hypothese.

## Few-Shot + v3-Schema für Fall 3 (`analyzer_field_reliability_fewshot.py`)

Ein konkretes Beispiel (analoger, aber nicht identischer Fall - Jacke statt
Kleid, andere Farbe/Person, Codex' Design) in die v3-Guidance eingefügt.
n=15 (Seeds `99002`-`99016`, kombiniert aus drei 5er-Batches).

| Feld | Ergebnis |
|---|---|
| `edits[0].subject`/`.region` | **15/15 korrekt** (z. B. "woman's leather dress"/"dress" - kein Platzhalter mehr) |
| `is_local_region` | **11/15 korrekt** (~73 %), falsch bei Seeds 99003, 99007, 99012, 99014 - auch dort `subject`/`region` weiterhin korrekt |
| `reference_slots` | 15/15 korrekt |

Deutliche Verbesserung gegenüber v3 allein (0/5 bei `region`,
0/5 bei `is_local_region`).

## Regressionscheck Fall 1 & 2 mit derselben Few-Shot-Guidance (n=3 je Fall)

`analyzer_field_reliability_fewshot_cases12.py`, gleiche Seeds
(`99002`-`99004`) wie der frühere Baseline-Test.

- **Fall 2 (globales Restyling):** 3/3 weiterhin vollständig korrekt, keine
  Regression.
- **Fall 1 (lokale Objektentfernung):** `edits[0].subject`/`.region` wurden
  jetzt spezifisch ("beer bottle on trash can"/"trash_can_top" statt
  Platzhalter - eine Verbesserung als Nebeneffekt), ABER `is_local_region`
  kippte auf **falsch in 2/3** (Seeds 99002, 99004), nur bei 99003 korrekt.
  Das ist eine **echte Regression**: unter der Baseline-Guidance war Fall 1s
  `is_local_region` 5/5 korrekt (`RESULTS_repeat_seed_cases12.md`).

## Codex' Bewertung (Zitat, gekürzt)

> No-go on adoption. This is useful evidence, but not production guidance.
> It improves subject/region, but damages is_local_region on a case that
> baseline already handled. [...] Treat [the case-1 regression] as more
> evidence that is_local_region is prompt-sensitive and not stable enough
> to use raw. [...] Few-shot+v3 is strong for subject/region specificity.
> It is not reliable for is_local_region. It regresses at least one
> previously passing local case. Therefore raw analyzer fields still need
> deterministic consistency validation before any downstream use. If you
> build anything next, build the validator/checker only, not another
> prompt iteration.

## Fazit

Few-Shot + v3 wird **nicht** in den Router übernommen - dokumentiert als
geprüft, aber verworfen. Mitnahme:
- `subject`/`region`-Spezifität lässt sich durch Few-Shot-Beispiele
  deutlich verbessern (case-übergreifend, auch als Nebeneffekt bei Fall 1).
- `is_local_region` bleibt **prompt-sensitiv und instabil** - eine
  Formulierung, die einem lokalen Fall hilft, kann einem anderen lokalen
  Fall schaden. Das ist keine neue, gesondert zu untersuchende Ursache,
  sondern eine weitere Bestätigung der bereits dokumentierten
  Cross-Field-Instabilität.
- Damit ist die Prompt-Engineering-Linie für dieses Feld ausgeschöpft: kein
  weiterer Wortlaut-/Few-Shot-Versuch geplant. Der bereits gebaute,
  diagnostische Validator (`RESULTS_consistency_check.md`) bleibt der
  richtige Baustein für jede künftige Nutzung dieser Felder - nicht mehr
  Prompting.
