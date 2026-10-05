# Qwen-Image-2.1 (NVFP4 community quant) - text-to-image smoke test

Smallest useful test before anything about native multi-reference editing:
does plain text-to-image generation work at all on this checkpoint set.

## Setup

- UNET: `diffusion_models\Qwen Image 2.1\qwenImage21Nvfp4Q4_nvfp4.safetensors`
  (3.91 GB, NVFP4+Q4, community quant from civitai.com/models/2957912,
  described by its own uploader as "Native Test" - not an official BFL/Qwen
  release)
- Text encoder: `text_encoders\Qwen Image 2.1\qwen3vl_8b_w4a8.safetensors`
  (6.31 GB, W4A8/ConvRot) - official Comfy-Org HuggingFace mirror
- VAE: `vae\Qwen Image 2.1\qwen_image_2.1_vae_bf16.safetensors` (0.68 GB) -
  official Comfy-Org HuggingFace mirror

Graph wiring verified against this install's live ComfyUI source
(`comfy/supported_models.py`, `comfy/sd.py`) and `/object_info`, not
guessed: `UNETLoader(weight_dtype="default")`, `CLIPLoader(type="qwen_image")`
(auto-detects Qwen-Image-2.1 vs. the original 2511 by inspecting the
checkpoint's TEModel - no separate "qwen_image21" dropdown entry exists),
`TextEncodeQwenImage21` (outputs positive/negative conditioning + a
pre-sized latent in one node - no `EmptyLatentImage` needed), `KSampler`.
No manual `ModelSamplingAuraFlow` node - `QwenImage21`'s `sampling_settings`
(shift=0.69) are auto-applied on load, unlike this project's existing Qwen
Image Edit 2511 graph. Sampler settings per the civitai uploader's own
tested starting point: Euler, 40 steps, CFG 1, Normal scheduler,
denoise=1.0. See `tests/router/ab_qwen_image21.py`.

## Result

Prompt: "A photo of a red bicycle leaning against a brick wall, golden hour
lighting, shallow depth of field." (seed 424242)

- `status_completed=true`, no `[ERROR]` log lines.
- `comfyui.log` confirms correct quantization handling: "Found quantization
  metadata version 1", "Detected mixed precision quantization", "Native
  ops: convrot_w4a4, asym_w4a8_int8, ..., nvfp4".
- **12.95s total wall time**, of which the 40-step sample itself took
  **9 seconds** (4.3 it/s) - dramatically faster than every other
  masked/edit-capable model tested this project so far (Flux.2 Dev:
  ~800s/28 steps; Klein distilled: ~20-25s/4 steps).
- Output image: sharp, photorealistic, correctly matches every stated
  prompt element (red bicycle, brick wall, golden-hour light direction,
  background falloff). Visually inspected, not assumed from a non-error
  exit code.

## Note on an odd log line

`comfyui.log` shows "Requested to load WanVAE" for this model's VAE, not a
Qwen-specific class name - not yet investigated whether this is just an
internal shared-architecture class name (Qwen-Image-2.1 reusing Wan's VAE
implementation) or something worth a closer look; the decoded image itself
was visually correct, so not treated as a defect here.

## What this does and does not establish

**Established**: basic text-to-image generation works correctly on this
specific NVFP4 community quant, is fast, and ComfyUI's native support for
the architecture (UNETLoader/CLIPLoader/TextEncodeQwenImage21) functions as
documented in source.

**Not yet established**: the actual capability this project cares about -
native multi-reference editing via `TextEncodeQwenImage21`'s `images` input
(up to 16 references, per live `/object_info`). That is the next test, not
this one. Also not established: image-edit mode (source image + instruction,
no separate reference), any comparison against Klein/Dev's masked-reference
mechanism, or whether this exact community UNET quant holds up as well as
an eventual official release would.
