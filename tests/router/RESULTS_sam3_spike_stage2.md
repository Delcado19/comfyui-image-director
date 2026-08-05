# Ergebnis: SAM3-Attention-Hint-Spike, Stufe 2 (Attention-Reimplementierung, ohne Bias)

Codex-Design, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`. Zweiter Schritt
nach `RESULTS_sam3_spike_stage1.md` (Block-Replace-Hook bestätigt).

## Setup

`QwenBlockAttnReimplProbe` (`custom_nodes/sam3_attn_probe/__init__.py`)
ersetzt NICHT den ganzen Block (wie Stufe 1s Logging-Wrapper), sondern nur
`attn.forward` eines einzelnen `QwenImageTransformerBlock` - eine
handkopierte Reimplementierung von `Attention.forward()`
(`comfy/ldm/qwen_image/model.py:142-203`, ~60 Zeilen), Zeile für Zeile
identisch zum Original, bis auf den einen Punkt, an dem in Stufe 3 der
SAM3-Bias eingebaut wird (der `attn_mask`-Parameter von
`optimized_attention_masked`). Registrierung über
`ModelPatcher.add_object_patch()` (`comfy/model_patcher.py:684`) - die
offizielle, pro-Klon reversible Mechanik (`comfy.utils.set_attr` +
`object_patches_backup`), **kein** permanenter Monkeypatch des geteilten
`nn.Module` (wichtig, weil `ModelPatcher.clone()` denselben zugrunde
liegenden Torch-Modell-Objektverweis teilt, nicht kopiert - verifiziert via
`get_clone_model_override()`, Zeile 379-380).

## Test

Gleicher Graph/Prompt/Seed wie Stufe 1 (`ab_ref_weight.py`s bekannt-
fehlerauslösender Aufbau), zwei Varianten: `baseline` (kein Patch-Node im
Graph) vs. `10` (Reimplementierung auf Block 10, keine Bias-Logik aktiv).
Seed 424242 für beide.

## Ergebnis

PNG-Dateien byte-verschieden (unterschiedliche eingebettete
Workflow-Metadaten/Zeitstempel in den PNG-Chunks), aber
**Pixelwerte exakt identisch**: `numpy`-Diff über alle RGB-Kanäle, 1184×880
Pixel, **max diff = 0, mean diff = 0.0**. Die Reimplementierung ist
bit-exakt gegenüber dem unveränderten Original - kein sichtbarer, kein
messbarer Unterschied.

## Fazit

Stufe 2 bestanden. Die handkopierte Attention-Reimplementierung ist
korrekt und kann vertrauensvoll als Basis für Stufe 3 verwendet werden.
Nächster Schritt: an der Stelle, wo aktuell `attn_mask` (nur der Text-Mask-
Teil) an `optimized_attention_masked` übergeben wird, eine echte
Query-Key-Bias-Matrix einbauen - abgeleitet aus einer SAM3-Maske auf dem
Quellbild, gemappt auf den Quellbild-Token-Bereich (aus Stufe 1 bekannt:
`source_tokens = img.shape[1] - sum(reference_image_num_tokens)`, Indizes
`[0, source_tokens)` in `img`, entsprechend
`[seq_txt, seq_txt+source_tokens)` in `joint_query`/`joint_key`).
