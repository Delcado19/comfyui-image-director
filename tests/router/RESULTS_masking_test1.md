# Ergebnis: Erster Hard-Masking-Test (SetLatentNoiseMask) - Bleeding gelöst, Transfer noch offen

Codex-Design/-Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.
Nutzer-Freigabe ("dann masking") nach dem negativen Abschluss der
mechanismus-basierten Untersuchung (`RESULTS_sam3_spike_stage3.md`) - der
"Holzhammer"-Ansatz, ursprünglich vermieden ("wir bauen hier keinen
expliziten vton workflow!"), jetzt als letzte verbleibende Option
freigegeben.

## Setup

Anders als der Attention-Bias-Spike (versucht, das modell-interne Routing
zu beeinflussen - gescheitert), erzwingt dieser Ansatz Lokalität auf
**Sampler-/Kompositions-Ebene**: `SetLatentNoiseMask` (`nodes.py:1541`,
ComfyUI-Core-Node, kein Custom-Code) setzt eine Maske auf das Source-
Latent - der Sampler mischt bei jedem Denoising-Schritt außerhalb der
Maske das Original-Latent zurück, unabhängig davon, was das Modell intern
"will". SAM3-Maske ("the woman's dress") auf dem exakt gleichen skalierten
Quellbild wie üblich, per `MaskToImage` visuell verifiziert (weiß = Kleid-
Silhouette, korrekte Polarität, keine falsche Invertierung). Gleicher
bekannt-fehlerauslösender Prompt/Referenz/Seed wie in allen bisherigen
Tests dieser Session.

## Ergebnis

**Bleeding-Problem vollständig gelöst.** Himmel, Gebäude, Straße, Mülleimer,
Bierflasche - die gesamte Szene außerhalb der Maske ist pixelgenau wie das
Original, kein Blau-Tint, keine sichtbaren Artefakte an der Maskengrenze.
Der erste vollständig saubere Hintergrund dieser gesamten Session, nach
jedem vorherigen Ansatz (Prompt-Engineering, Gewichts-Skalierung,
Attention-Bias).

**Aber:** innerhalb der Maske bleibt das Kleid komplett schwarz - keine
Farbübertragung von der Referenz, trotz freiem Denoising innerhalb der
Maske (denoise=1.0, 8 Steps, cfg=2.5). Das entspricht Codex' vorab
benanntem Risiko "Inside region may still not recolor".

## Codex' Einschätzung und nächster Schritt

Vermuteter Grund: der verwendete Prompt beschreibt die Zielregion noch als
"black leather dress that needs to be changed" und die Referenz als
"solid blue **background**" - beide Formulierungen haben in dieser Session
bereits mehrfach falsche Signale erzeugt (siehe `RESULTS_ab_background_word.md`).
Mit gelöstem Bleeding-Risiko ist die ursprüngliche vorsichtige
"preserve everything"-Formulierung nicht mehr nötig - die Maske übernimmt
diese Aufgabe jetzt strukturell.

**Nächster Test (für die Folgesession):** vereinfachter Prompt ohne
Ausgangsfarben-Anker und ohne "background"-Wort:

> "Change only the masked dress to match the blue color and material of
> Reference Image #2. Keep everything outside the mask unchanged."

Gleicher Graph, gleiche Maske, gleicher Seed. Falls das Kleid weiterhin
schwarz bleibt: nächster Hebel ist nicht mehr der Prompt, sondern die
Sampling-Stärke (mehr Steps oder andere CFG).

## Test 2 (entscheidend): vereinfachter, maskenbewusster Prompt

Gleicher Graph, gleiche Maske, gleicher Seed (424242). Prompt ersetzt
durch Codex' Vorschlag - ohne Ausgangsfarben-Anker, ohne "background":

> "Change only the masked dress to match the blue color and material of
> Reference Image #2. Keep everything outside the mask unchanged."

**Ergebnis: Erfolg.** Das Kleid ist jetzt blau, Material glatt/satiniert
entsprechend der Referenz, alle Nieten des Original-Kleids verschwunden
(Materialwechsel, nicht nur Farbwechsel - wie im Prompt gefordert). Der
Rest der Szene bleibt weiterhin pixelgenau unverändert (Himmel, Gebäude,
Straße, Mülleimer, Bierflasche, Gesicht, Pose, Leggings, Stiefel, Tasche).
**Die erste erfolgreiche referenzbasierte lokale Farb-/Material-
übertragung dieser gesamten Session, ohne jedes Bleeding.**

Kleinere Randartefakte sichtbar: ein dünner Saum mit Resten des
Original-Kleids an den Seiten unterhalb der Hüfte, vermutlich weil die
SAM3-Maske dort etwas zu eng geschnitten war (kein Grow/Blur angewendet -
bewusst roher erster Test laut Codex: "first run should prove the
mechanism, not polish it").

## Codex' Bewertung (Zitat)

> Was jetzt belegt ist: SAM3-Maske + `SetLatentNoiseMask` löst die
> Lokalität hart. Vereinfachter maskenbezogener Prompt aktiviert die
> Referenzübertragung innerhalb der Maske. Szene außerhalb bleibt
> unverändert. Qwen kann den Referenzlook lokal übertragen, wenn die
> Region sampler-seitig begrenzt wird.
>
> Nicht überclaimen: n=1, nur diese Quelle/Referenz/Maskenregion,
> Randartefakte noch offen, noch keine allgemeine Router-Integration,
> Prompt muss mask-aware gebaut werden, nicht der alte Analyzer-`prompt`
> verbatim.

## Fazit

**Machbarkeitsnachweis für Fall 3 (referenzbasiertes lokales Umfärben)
erbracht - als gelöst zu betrachten, mit offenem Feinschliff.** Der
Kernmechanismus (SAM3-Maske → `SetLatentNoiseMask` → maskenbewusster
Prompt) funktioniert, ohne jedes Bleeding, mit echter Referenzbild-
basierter Material-/Farbübertragung. Nicht überclaimen: nur n=1, nur diese
eine Quell-/Referenzbild-/Maskenkombination getestet, Randartefakte noch
ungelöst (Mask-Grow/Blur als nächster Feinschliff-Schritt, nicht
angewendet), und es gibt noch keine Integration in den Router - der
Analyzer müsste den Prompt maskenbewusst bauen (nicht die bisherige freie
Prosa), und die SAM3-Maskenerzeugung müsste in den Router-Graphen
eingebaut werden. Diese Integrationsarbeit ist ein eigenständiger,
nicht-trivialer nächster Schritt, kein einfacher Rollout.
