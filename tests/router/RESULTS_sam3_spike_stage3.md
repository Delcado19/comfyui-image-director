# Ergebnis: SAM3-Attention-Hint-Spike, Stufe 3 (echter Query-Key-Bias) - NEGATIV

Codex-Design/-Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.
Aufbauend auf `RESULTS_sam3_spike_stage2.md` (bit-exakte Attention-
Reimplementierung, bestätigt).

## Setup

`QwenSam3AttnBiasProbe` erweitert Stufe 2s Reimplementierung um eine echte
additive `[Lq, Lk]`-Query-Key-Bias-Matrix am `attn_mask`-Argument von
`optimized_attention_masked` - der Stelle, für die Stufe 2 extra gebaut
wurde. SAM3 (`easy sam3ImageSegmentation`, Prompt `"the woman's dress"`)
liefert eine Pixelmaske auf dem exakt gleichen skalierten Quellbild, das
auch an `VAEEncode` geht. Downsampling auf das Token-Grid
(`h_len = (ceil(H/8)+1)//2`, analog `w_len`, VAE-Stride 8 × DiT-Patch-Size
2) - **Laufzeit-Sanity-Check eingebaut**: berechnetes Grid (`h_len*w_len`)
wird gegen den tatsächlichen `source_tokens`-Wert
(`seq_img - sum(reference_image_num_tokens)`) verglichen; bei Mismatch
wird die Bias-Anwendung übersprungen (fail-safe), statt eine falsch
ausgerichtete Maske zu verwenden.

**Grid-Check bestanden:** `source_tokens=4070` (aus `reference_image_num_tokens`)
== `h_len(74) * w_len(55) = 4070` (aus `source_width`/`source_height`) -
exakte Übereinstimmung, kein Fallback nötig. SAM3 erkannte 221/4070 Tokens
(~5,4%) als Kleid-Region - plausibel für eine Ganzkörperaufnahme.

Query-Zeilen = Quellbild-Tokens, gefiltert nach SAM3-Maske
(`inside_bias`); Key-Spalten = die Tokens von Referenzbild 2 (`image2`,
`reference_index=1`, gleiche Semantik wie in `RESULTS_ref_weight.md`
etabliert). Tokens außerhalb der Maske bekommen `outside_bias`
(Default 0.0 = unverändert).

## Tests (alle: bekannt-fehlerauslösender Prompt, Seed 424242)

| # | Blöcke | inside_bias | outside_bias | Ergebnis |
|---|---|---|---|---|
| 1 | [10] | +4.0 | 0.0 | Visuell nicht von Baseline unterscheidbar |
| 2 | [10] | +15.0 | -15.0 | Minimale Beleuchtungs-/Farbverschiebung im Hintergrund, Kleid schwarz |
| 3 | [8,16,24,32,40] | +8.0 | -2.0 | Szenen-Tint deutlich schwächer/natürlicher (wie beim reinen Gewichts-Sweep), Kleid schwarz |
| 4 (entscheidend) | [8,12,16,20,24,28,32,36,40] | +12.0 | 0.0 | **Tint-Rückgang verschwindet wieder** (bestätigt: Test 3s Effekt kam vom negativen `outside_bias`, nicht vom räumlichen Inside-Anteil), Kleid weiterhin vollständig schwarz |

Codex' vorab festgelegtes Stopp-Kriterium für Test 4: "Kleid beginnt
sichtbar Richtung Referenz zu wechseln" (PASS) vs. "Kleid bleibt schwarz"
(STOP). Ergebnis: Kleid bleibt schwarz.

## Codex' Bewertung (Zitat, gekürzt)

> Das Muster spricht eher für ein strukturelles Problem als für "nur noch
> ein bisschen tunen". [...] Die globale Blau-Anwendung hängt an
> Referenz-/Prompt-Signalstärke, aber das Modell hat in diesem Setup
> keinen stabilen Pfad "Referenzappearance -> Kleidregion". Der Bias
> reduziert den falschen Pfad, er erzeugt den richtigen nicht. [...] Wenn
> auch das Kleid schwarz bleibt: stoppe den Attention-Bias-Spike. Dann ist
> der Befund: "Qwen reference attention can be attenuated spatially/
> globally, but this patch did not create local attribute transfer."

## Fazit

**Der SAM3-Attention-Bias-Spike ist damit negativ abgeschlossen**, trotz
technisch einwandfreier Umsetzung (Hook bestätigt in Stufe 1, Reimplemen-
tierung bit-exakt in Stufe 2, Grid-Mapping in Stufe 3 exakt verifiziert,
kein einziger stiller Fehlschlag durch falsche Indizierung). Selbst ein
starker, räumlich sauber maskierter, rein positiver Bias über 9 mittlere/
späte Blöcke erzeugt keine lokale Farbübertragung vom Referenzbild auf das
Kleid. Das bestätigt und verschärft den bereits in `RESULTS_ref_weight.md`
gefundenen Befund: Qwen Image Edit 2511 hat in diesem Aufbau keinen
robusten "Referenzbild-Attribut -> Zielregion"-Pfad, den man durch
Attention-Umverteilung (egal ob global via Gewicht, oder jetzt räumlich
via Bias) freilegen könnte - das Problem liegt tiefer als reine
Attention-Routing-Lokalität.

Damit sind **alle identifizierten, mechanismus-basierten (nicht-Masking-
im-Sample-Pfad) Lösungsansätze für Fall 3 auf dem Qwen-Image-Edit-2511-Pfad
erschöpft**: Analyzer-Guidance, Negative-Prompt, deterministisches
Templating, Few-Shot/`temperature=0`, gewichtete Referenz-Attention
(global), räumlich selektive Referenz-Attention-Bias (dieser Spike). Auch
Flux.2 Dev (alle 4 Referenz-Verkettungsmodi, `RESULTS_flux2dev_capability.md`)
ist ausgeschlossen. Harte Masking/Region-Conditioning-Ansätze (echtes
Inpainting mit SAM3-Maske als Hard-Constraint im Sample-/Decode-Pfad,
nicht nur als Attention-Hinweis) bleiben der einzige noch nicht getestete
Mechanismus - explizit der "Holzhammer"-Ansatz, den der Nutzer ursprünglich
vermeiden wollte ("wir bauen hier keinen expliziten vton workflow!"), aber
nach Erschöpfung aller weicheren Alternativen die verbleibende Option.
