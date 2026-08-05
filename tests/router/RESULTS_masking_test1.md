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

## Fazit

Erster echter, strukturell wirksamer Fortschritt dieser gesamten Session
für Fall 3: das Lokalitätsproblem (Bleeding) ist gelöst. Die verbleibende
offene Frage ist reine Prompt-/Sampling-Feinabstimmung innerhalb der jetzt
korrekt isolierten Region, kein Architektur- oder Mechanismus-Problem mehr.
