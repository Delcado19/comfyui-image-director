# Ergebnis: SAM3-Attention-Hint-Spike, Stufe 1 (Logging-Wrapper)

Codex-Design, Thread `019fd14f-0515-7a91-958a-ce162f468ce2`. Erster Schritt
des mehrstufigen Spikes nach Abschluss der Flux.2-Dev-Untersuchung
(`RESULTS_flux2dev_capability.md`) - Nutzer-Vorgabe: keine Änderung an der
ComfyUI-Installation, nur Custom-Node-Code.

## Setup

Neues Custom-Node-Paket `custom_nodes/sam3_attn_probe/` in diesem Dev-Repo,
per Windows-Junction (`New-Item -ItemType Junction`, keine Admin-Rechte für
echte Symlinks verfügbar) nach
`G:\ComfyUI-Easy-Install\ComfyUI\custom_nodes\sam3_attn_probe` verlinkt -
identisches Muster wie `comfyui-qwenvl-structured-gguf`. Der Node
`QwenBlockPatchLoggerProbe` registriert per offizieller, öffentlicher API
`ModelPatcher.set_model_patch_replace()` (`comfy/model_patcher.py:622`)
einen `patches_replace["dit"][("double_block", i)]`-Hook auf einem
geklonten Modell, loggt beim ersten Aufruf Tensor-Shapes/Keys (Konsole +
JSON-Datei, da kein Zugriff auf die Server-Konsole besteht) und reicht den
Aufruf unverändert an `original_block` weiter - kein Bias, keine SAM3-Maske,
reine Verifikation des Hook-Vertrags.

Testgraph (`sam3_spike_stage1_probe.py`): reproduziert `ab_ref_weight.py`s
bekannt-funktionierenden Qwen-Image-Edit-2511-Graphen (GGUF-UNet/CLIP,
bekannt-fehlerauslösender Prompt), Node zwischen `ModelSamplingAuraFlow`
und `KSampler` eingehängt statt `Flux2KleinRefLatentWeight`.

## Ergebnis

Erster Testlauf lieferte keine Logdatei - keine Fehlermeldung, aber auch
kein Log, trotz Code ohne bedingte Sprünge vor dem Schreibvorgang.
Diagnose-Schritt: sofortiger Registrierungs-Log direkt nach
`set_model_patch_replace()` hinzugefügt (statt nur beim Block-Aufruf) -
zeigte, dass die Log-Datei-Suche zuvor schlicht danebengegriffen hatte
(`find`-Timing-Problem), nicht dass der Hook fehlte. Nach ComfyUI-Neustart
(Custom-Node-Code wird nicht heiß neu geladen) liefen beide Log-Ebenen
sauber:

**Registrierung** (`last_registration_log.json`):
```json
{
  "model_class": "QwenImage",
  "diffusion_model_class": "QwenImageTransformer2DModel",
  "registered_dit_keys": ["('double_block', 0)"],
  "target_key_present": true
}
```

**Block-Aufruf** (`last_probe_log.json`, block_index=0):
```json
{
  "img_shape": [1, 12236, 3072],
  "txt_shape": [1, 444, 3072],
  "vec_shape": [2, 3072],
  "pe_shape": [1, 1, 12680, 64, 2, 2],
  "total_blocks": 60,
  "block_type": "double",
  "reference_image_num_tokens": [4070, 4096]
}
```

## Erkenntnisse für Stufe 2/3

- **Hook-Vertrag bestätigt** wie aus dem Quellcode gelesen (`args` = `img`/
  `txt`/`vec`/`pe`/`transformer_options`, `extra_args["original_block"]`
  als Callback) - keine Überraschung, aber jetzt empirisch verifiziert statt
  nur quellcode-gelesen.
- **`total_blocks = 60`** - deutlich mehr als die zuvor grob geschätzten
  "28+ Layer".
- **Günstiger als erwartet für die geplante Query-Maske:** auf Block-Ebene
  sind `img` und `txt` noch getrennte Tensoren (Verschmelzung zu
  `joint_query`/`joint_key`/`joint_value` passiert erst innerhalb des
  Blocks, in der Attention-Processor-Forward). `img` enthält bereits
  Quellbild- UND beide Referenzbild-Tokens verkettet
  (`reference_image_num_tokens=[4070, 4096]`), Quellbild-Tokens damit direkt
  berechenbar: `source_tokens = img.shape[1] - sum(reference_image_num_tokens)
  = 12236 - 8166 = 4070`, Indexbereich `[0, 4070)` in `img`. Kein Umweg über
  `img_slice` (das ist erst innerhalb der Attention-Processor-Forward
  gesetzt, auf Block-Ebene noch nicht sichtbar) nötig.

## Fazit

Stufe 1 bestanden. Der Hook funktioniert exakt wie geplant, ohne
Installations-Änderung. Nächster Schritt (Stufe 2, laut Codex 0,5-1,5 Tage):
eigene Attention-Reimplementierung auf diesem einen Block, noch OHNE Bias -
muss den Baseline-Output (kein sichtbarer Unterschied zum unveränderten
Modell) reproduzieren, bevor in Stufe 3 eine echte SAM3-Masken-basierte
Query-Key-Bias hinzukommt.
