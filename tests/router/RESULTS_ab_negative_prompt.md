# Ergebnis: Negative-Prompt A/B-Test (`ab_negative_prompt.py`)

Codex-Design, Thread `019fcb5f-8503-7641-85a0-f7a74b1b7659` (Vorschlag) und
`019fd14f-0515-7a91-958a-ce162f468ce2` (Auswertung, da der erste Thread
sitzungsübergreifend nicht mehr auffindbar war).

Ausgangspunkt: `edit_cond_neg` in `build_router_graph.py` ist im Router
IMMER ein leerer String (`StringSubstring(edit_prompt_str, 0, 0)`) - ungenutzt.
Frage: Kann ein echter, handgeschriebener Negative-Prompt beim
reference-basierten Farbtransfer (Fall 3) das bestätigte "background"-Wort-
Bleeding (`RESULTS_ab_background_word.md`) unterdrücken, nachdem der Fix über
die Analyzer-Formulierung (Guidance-Klausel) bereits gescheitert ist?

Setup (beide Phasen): Quellbild `IMG_7148.jpg`, Referenzbild
`imgdir_test_ref2.png`, Seed `424242`, Qwen Image Edit 2511, `cfg 2.5`,
`CFGNorm strength 1.0`, 8 Steps, Analyzer umgangen (`PrimitiveString` statt
`GetTextFromJson`, gleiches Muster wie `ab_background_word.py`).

Negative-Prompt-Varianten:
- `empty`: `""`
- `handwritten`: `"background, sky, buildings, pavement, environment, skin, hair, pose, face"`

## Phase 1: Non-Regression (guter Positive-Prompt)

Positive-Prompt fix auf die bestätigt gute Formulierung (ohne "background"):
`"...which appears as a solid blue. The rest should remain unchanged."`

| Variante | Datei | Ergebnis |
|---|---|---|
| `empty` | `ImageDirector_ABneg_00001_.png` | Kleid korrekt blau, Szene unverändert - PASS |
| `handwritten` | `ImageDirector_ABneg_00002_.png` | Kleid korrekt blau, Szene unverändert - PASS |

Beide Bilder sind visuell nicht unterscheidbar. Ergebnis: der handgeschriebene
Negative-Prompt verursacht keine Regression auf dem bereits funktionierenden
Fall. Er sagt nichts darüber aus, ob er im tatsächlichen Fehlerfall hilft.

## Phase 2: Rescue-Test (schlechter Positive-Prompt)

Positive-Prompt auf die bestätigt fehlerauslösende Formulierung (mit
"background") gesetzt:
`"...which appears as a solid blue background. The rest should remain unchanged."`

| Variante | Datei | Ergebnis |
|---|---|---|
| `empty` | `ImageDirector_ABneg_00003_.png` | Kleid bleibt SCHWARZ (nicht umgefärbt), gesamte Szene blau getönt - FAIL |
| `handwritten` | `ImageDirector_ABneg_00004_.png` | Kleid bleibt SCHWARZ (nicht umgefärbt), gesamte Szene blau getönt - FAIL |

Auch hier: kein sichtbarer Unterschied zwischen leerem und handgeschriebenem
Negative-Prompt. Beide scheitern identisch, und sogar deutlicher als der
ursprüngliche reine Ganzbild-Tint (hier bleibt zusätzlich das Kleid
unverändert schwarz statt sich einzufärben).

## Codex' Bewertung (Zitat, gekürzt)

> This closes the negative-prompt mitigation avenue for this specific failure
> mode. [...] the tested handwritten negative prompt, under Qwen Image Edit
> 2511 / cfg 2.5 / CFGNorm 1.0, did not rescue the confirmed `background`-word
> bleed. Do not generalize to all negative prompts or all CFG/settings.
>
> I'd document prompt-level mitigations as exhausted for now. [...] Next real
> candidate should be structural: prompt construction that does not pass
> analyzer prose verbatim, masking/region-conditioning, or consuming
> structured fields like `is_local_region`, `edits[]`, and `preserve[]`. Of
> those, the smallest next candidate is probably deterministic prompt
> construction from schema fields, because masking is a bigger workflow
> change.

## Fazit

Zwei unabhängige Fix-Versuche für das "background"-Wort-Bleeding sind
gescheitert:
1. Analyzer-Guidance-Klausel (steuert die Formulierung nicht zuverlässig,
   revertiert - siehe `RESULTS_ab_background_word.md`).
2. Negative-Prompt-Unterdrückung (dieser Test - unterdrückt das Bleeding
   nicht, bei diesem Setup/CFG).

Prompt-Level-Mitigationen für diesen Fehlerfall gelten damit als vorläufig
ausgeschöpft. Nächster sinnvoller Kandidat (nicht gestartet, erfordert
eigene gemeinsame Entscheidung): deterministische Prompt-Konstruktion aus den
bereits vorhandenen, aber vom Router aktuell ignorierten Schema-Feldern
(`is_local_region`, `edits[]`, `preserve[]`) statt der freien Analyzer-Prosa.
Masking/Region-Conditioning wäre der größere, aufwändigere nächste Schritt.

Diese Aussage gilt eng für dieses Setup (dieses Bild-/Referenzpaar, dieser
Seed, `cfg 2.5`, `CFGNorm 1.0`, diese Negative-Prompt-Wortliste) - keine
generelle Aussage über Negative-Prompts bei Qwen Image Edit 2511.
