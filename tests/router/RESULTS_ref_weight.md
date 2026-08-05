# Ergebnis: Gewichtete Referenz-Attention als Masking-Alternative (`ab_ref_weight.py`)

Codex-Design und -Auswertung, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`.
Antwort auf die Nutzerfrage
"gibt es Alternativen zum Masking?" für Fall 3s ungelöstes Bleeding, nach
Ablehnung eines ersten Vorschlags (Referenzbild in Text umwandeln - vom
Nutzer zu Recht verworfen, da das dem Bild-basierten Kernprinzip des
Projekts widerspricht).

## Entdeckung: ein echter, technisch kompatibler Mechanismus

Gezielte Recherche in den installierten Custom-Nodes
(`G:\ComfyUI-Easy-Install\ComfyUI\custom_nodes`) statt nur "gibt es
nicht" anzunehmen. Gefunden: `ComfyUI-Flux2Klein-Enhancer` enthält
`Flux2KleinRefLatentWeight` (u. a.), das die Attention-K/V-Werte eines
bestimmten Referenzbild-Token-Bereichs über `model.set_model_attn1_patch()`
skaliert.

**Per Quellcode verifiziert (nicht angenommen):** trotz des
Flux2/Klein-Namens ist der Mechanismus für Qwen Image Edit 2511
technisch kompatibel:
- `comfy/ldm/qwen_image/model.py:497` setzt
  `transformer_options["reference_image_num_tokens"]` - genau der
  Schlüssel, den der Node ausliest.
- `comfy/ldm/qwen_image/model.py:183-187` ruft `attn1_patch`-Funktionen
  mit `(joint_query, joint_key, joint_value, extra_options=...)` auf -
  exakt die vom Node erwartete Signatur.
- `comfy_extras/nodes_qwen.py:74-105`: `TextEncodeQwenImageEditPlus`
  baut `reference_latents` aus `[image1, image2, image3]` in dieser
  Reihenfolge - **Index 0 = `image1` (Quellbild), Index 1 = `image2`
  (die eigentliche Referenz)**. Vor dem Test geklärt, nicht angenommen.

## Smoke-Test

Bekannt fehlerauslösender Positive-Prompt (`RESULTS_ab_background_word.md`s
"with background"-Variante), gleicher Seed/Bilder, `reference_index=1`.
Sweep: Baseline (kein Patch) -> Gewicht `0.7` -> `0.5` -> `0.2`.

| Variante | Szenen-Tint | Kleid umgefärbt? |
|---|---|---|
| Baseline (kein Patch) | stark, gesättigt blau über gesamte Szene | Nein (schwarz) |
| Gewicht 0.7 | sichtbar schwächer | Nein (schwarz) |
| Gewicht 0.5 | nochmals schwächer, Himmel wirkt wieder natürlicher | Nein (schwarz) |
| Gewicht 0.2 | am schwächsten, Straße/Gebäude nahezu natürliche Farbe | Nein (schwarz) |

**Der Mechanismus wirkt real und monoton** - der falsche Ganzbild-Tint
lässt sich gezielt abschwächen. **Aber das Kleid färbt sich in keiner
der vier Varianten um.** Bei sinkendem Gewicht verschwindet einfach die
komplette Referenzwirkung gleichmäßig - der (falsche) globale Effekt
schwächt sich ab, der (richtige) lokale Effekt am Kleid setzt nie ein.

## Codex' Bewertung (Zitat, gekürzt)

> `Flux2KleinRefLatentWeight` is technically compatible with Qwen Image
> Edit. Lower weights monotonically reduce the wrong global tint. It
> never produces the desired dress recolor. Therefore it controls
> reference influence magnitude, not edit locality. [...] For Qwen Image
> Edit 2511 on this graph, [masking/region-conditioning] is now the only
> mechanism-level locality lever left.

Der Spatial-Fade-Modus des gleichen Node-Pakets (`Flux2KleinRefLatentController`)
wurde bewusst **nicht** zusätzlich getestet: er würde nur beeinflussen,
welcher Teil des *Referenzbilds* gewichtet wird - bei einer flachen
Farbfläche als Referenz gibt es dort keine nutzbare räumliche Struktur,
und er sagt Qwen ohnehin nicht, *wo im Quellbild* editiert werden soll.

## Fazit

Ein echter, technisch verifizierter, nicht-Masking-Mechanismus wurde
gefunden, getestet und **eindeutig widerlegt** als Lösung für Fall 3:
er steuert die *Stärke* des Referenzeinflusses, nicht dessen *Ziel*. Damit
sind für diesen konkreten Qwen-Image-Edit-2511-Pfad alle identifizierten
Nicht-Masking-Hebel (Analyzer-Guidance, Negative-Prompt, deterministisches
Templating, Few-Shot/`temperature=0`, gewichtete Referenz-Attention)
geprüft und verworfen.

Verbleibende, nicht getestete Alternativen (laut Codex, andere Kategorie
als reine Qwen-Graph-Anpassung):
- Fotografische/materialbasierte statt Flat-Color-Referenz (noch offen,
  günstigster nächster Test).
- Wechsel auf einen anderen referenz-fähigen Modellzweig (z. B.
  Flux2/Klein) - ein Modellwechsel, keine Qwen-Anpassung.
- Crop/Edit/Stitch um das Kleid herum - faktisch eine Form von
  Region-Control, auch wenn nicht semantisches Masking im engeren Sinn.

Für den aktuellen Qwen-Image-Edit-2511-Pfad gilt: Masking/
Region-Conditioning ist der einzige verbleibende Mechanismus-Level-Hebel
für das Lokalitätsproblem.
