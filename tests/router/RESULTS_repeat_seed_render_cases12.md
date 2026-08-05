# Render-Level-Repeat-Seed-Test für Fall 1 & 2 (`repeat_seed_render_cases12.py`)

Schließt den zuletzt noch offenen Teil von
`RESULTS_repeat_seed_cases12.md` ("No render-level (KSampler) repeat-seed
pass done yet"). Voller Router-Durchlauf (`build_router_graph.build()`,
echter Analyzer + echtes Rendering), `n=3` pro Fall (kleiner als der
Analyzer-only-Test bei n=5, da hier jeder Lauf ein volles UNet/VAE-Laden +
KSampler-Durchlauf ist, nicht ein billiger Analyzer-only-Call).

Gleiche Instruktionen wie `RESULTS_content_quality.md`/
`RESULTS_repeat_seed_cases12.md`, gleiches Quellfoto `IMG_7148.jpg`.

## Fall 1 — lokale Objektentfernung, n=3

Seeds `71001-71003` (Render), `91001-91003` (Analyzer).

**Alle 3/3: PASS.** Die Bierflasche ist in allen drei Läufen sauber vom
Mülleimer entfernt, Frau/Pose/Kleidung/restliche Szene identisch erhalten.
Keine Varianz zwischen den Seeds beobachtet - visuell praktisch
ununterscheidbar von den drei Läufen.

## Fall 2 — globales Restyling, n=3

Seeds `72001-72003` (Render), `92001-92003` (Analyzer).

**Alle 3/3: PASS.** Warmer, verblasster Vintage-Ton konsistent über alle
drei Läufe angewendet, Person/Pose/Komposition erhalten. Das Filmkorn ist
in allen drei Läufen ähnlich subtil ausgeprägt (kein starkes Korn, aber
konsistent zwischen den Läufen - keine Reliability-Auffälligkeit, sondern
ein durchgängiges, mildes Ergebnis dieses Sampler-/Step-Setups).

## Fazit

Beide Fälle sind jetzt sowohl auf JSON-Plan-Ebene (n=5,
`RESULTS_repeat_seed_cases12.md`) als auch auf Render-Ebene (n=3) getestet
und **vollständig stabil**. Der lang offene "n=1 per case, no repeat-seed
screen"-Punkt aus `RESULTS_content_quality.md` gilt für Fall 1 und 2 damit
als geschlossen. Fall 3 (Referenz-basierte Umfärbung) bleibt der einzige
Fall mit einem bekannten, ungelösten visuellen Fehlerbild (siehe
`RESULTS_ab_background_word.md`, `RESULTS_ab_negative_prompt.md`,
`RESULTS_analyzer_field_reliability*.md`).
