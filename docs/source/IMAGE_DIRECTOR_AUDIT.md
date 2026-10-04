# Image Director — Technical Audit

Required output of "First Codex Assignment" (§34,
`COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`). No files were
modified to produce this audit.

**Scan basis:** `G:\ComfyUI-Easy-Install\comfyui_scan\` — all four files read
and cross-checked (`comfyui_summary.json`, `custom_nodes.json`, `models.json`,
`report.txt`), scan timestamp **2026-07-31 19:16:54**. `report.txt` and
`models.json` agree exactly (135/135 entries); GPU/VRAM is not in the scan
output (confirmed by reading `report.txt` directly) and was instead checked
live via `nvidia-smi`. This scan supersedes the 2026-07-30 13:57:06 scan the
handover doc was written against — see §4 for the delta.

---

## 1. Core system (verified live + via scan)

```text
ComfyUI root:   G:\ComfyUI-Easy-Install\ComfyUI
Commit:         322122449c9d2ba8b8df1bb517364527dd0615f1 (32212244), v0.29.2
Python:         3.12.13
GPU:            NVIDIA GeForce RTX 5080
VRAM:           16303 MiB (~16 GB)
```

**Stale as of 2026-10-03 (caught during a documentation audit, 2026-10-04):**
the project was inactive 2026-08-10 through ~2026-10-03, during which ComfyUI
was upgraded past this commit. Current state per `G:\ComfyUI-Easy-Install\
comfyui_scan\` (scan timestamp 2026-10-03 18:45:42, cross-checked live via
`/system_stats`): **commit `6b747c04`, v0.38.0**. Python version and GPU/VRAM
are unchanged. See `PROJECT_RULES.md`'s "Environment drift after a ~2-month
pause" entry (2026-10-03) for the full model-path/custom-node delta this
version jump caused - do not treat this section's commit/version as current.

The handover's `a8c44f9b` is stale — one ComfyUI update happened between the
2026-07-30 scan and now. Re-verified live via `git log -1` and `nvidia-smi`,
matches the fresh scan exactly.

---

## 2. Relevant custom nodes — node classes actually present

| Pack | Role | Relevant classes |
|---|---|---|
| `ComfyUI-QwenVL` | Layer A (vision/orchestration) | `AILab_QwenVL`, `AILab_QwenVL_Advanced`, `AILab_QwenVL_GGUF`, `AILab_QwenVL_GGUF_Advanced`, `AILab_QwenVL_GGUF_PromptEnhancer` — has native GGUF loaders, no extra loader pack needed for the VLM side |
| `ComfyUI-GGUF` | UNet/CLIP loading | `UnetLoaderGGUF`, `UnetLoaderGGUFAdvanced`, `CLIPLoaderGGUF`, `DualCLIPLoaderGGUF` — GGUF loader infrastructure is present for `Qwen-Image-Edit-2509-Q4_K_M.gguf`; **not** proof it initializes/infers correctly (§6.4 corrected) |
| `ComfyUI-Flux2Klein-Enhancer` | Multi-reference / identity (candidate) | `Flux2KleinRefLatentController`, `Flux2KleinRefLatentWeight`, `Flux2KleinMaskRefController`, `Flux2KleinTextEnhancer`, `Flux2KleinTextRefBalance`, `Flux2KleinColorAnchor`, `Flux2KleinDetailController`, `IdentityFeatureTransfer(Advanced/Final/V3)`, `IdentityGuidance` — see §6, largely a dead end on the FLUX.2 Klein path |
| `rgthree-comfy` | Router layer | `RgthreeAnySwitch`, `RgthreeContextSwitch`, `RgthreeContextSwitchBig` — usable switch/router primitives, already installed |
| `comfyui-logic` | Router layer | `IfExecute`, `IfExecuteNode`, `Compare`, `Bool` — usable for conditional branch execution |
| `cg-use-everywhere` | Wiring reduction | `AnythingEverywhere*` — broadcasts values across the graph; not a router/switch, just reduces link clutter |
| `comfyui-image-saver` | Reproducibility | `ImageSaverMetadata`, `ImageSaverPipe`, `EditImageSaverPipe` — embeds standard `extra_pnginfo`/`prompt` PNG metadata (verified via `grep` on `nodes.py`, not just class names) plus explicit A1111-style structured fields (model, sampler, steps, CFG, seed, ...) and an optional separate workflow-JSON export |
| `save-image-organized` | Reproducibility | `SaveImageClean` — also verified via `grep`: embeds the same standard `extra_pnginfo`/`prompt` PNG metadata (`PngImagePlugin.PngInfo`), so full workflow reproducibility is equally intact. Its focus is organized file/folder naming, not explicit structured parameter fields |
| `comfyui-prompt-reader-node` | Reproducibility (read side) | `ImageDataReader`, `ComfyUI` format parser — can read back embedded metadata for debugging |

**§26 recommendation:** both installed save nodes preserve full workflow
reproducibility (confirmed by reading the actual embedding code, not inferred
from class names). `comfyui-image-saver` additionally exposes the explicit
human-readable parameter fields §26 lists (model, sampler, scheduler, steps,
CFG, seed, ...), which is closer to that section's intent — use it for
Version-1 if per-run parameter fields matter, or `save-image-organized` if
folder/filename organization matters more. Not a correctness distinction,
a workflow-preference one.

---

## 3. Dirty custom-node repos (unchanged since 2026-07-30)

```text
ComfyUI-Flux2Klein-Enhancer           bdbd930  main
comfyui-google-gemini-outfit-caption  b478534  main
ComfyUI-Krea2T-Enhancer               50422e3  main
ComfyUI-PuLID-Flux-Enhanced           edcb3af  main
ComfyUI-QwenVL                        fcd1ada  main
comfyui-rmbg                          d740251  main
wlsh_nodes                            9780746  main
```

Identical commit hashes to the handover's §12 list — no drift in the last 24 h.
Do not pull/reset these (per project rule, unverified local changes may exist).

One scanner data-quality note: `CustomNodeCount: 59` includes a bogus
`__pycache__` directory entry (`IsGitRepo: false`, 0 Python files) — the real
custom-node-pack count is **58**, not 59.

---

## 4. Model inventory delta since the 2026-07-30 scan

Total model files: **135** (was 148 in the handover baseline). Net change is
not a simple count — real churn happened:

### Removed since 2026-07-30

```text
diffusion_models\Flux.2 klein\darkBeast_dbkBlitzV15.safetensors
unet\Flux.2 klein\unstableRevolutionF2K_AlphaF2K4BQ80.gguf
unet\Z-Image Base\easonZimageturboRealistic_baseV3-Q4_K_M.gguf
unet\Z-Image Base\juggernautZ_v10ByRundiffusion-Q6_K.gguf
ipadapter\ip-adapter-faceid-plusv2_sdxl_lora.safetensors   (LoRA half only —
                                                              the .bin model
                                                              half remains)
vae\pig_flux_vae_fp32-f16.gguf
```

### Added since 2026-07-30 — not mentioned anywhere in the handover

```text
diffusion_models\Flux.2 Dev\flux2-dev-nvfp4-mixed.safetensors   (21.2 GB)
text_encoders\Flux.2 Dev\mistral_3_small_flux2_fp4_mixed.safetensors  (11.4 GB)
```

**Stale as of 2026-10-03 (caught during a documentation audit, 2026-10-04):**
neither of these two files exists anymore. The current scan
(`G:\ComfyUI-Easy-Install\comfyui_scan\`, 2026-10-03) shows Flux.2 Dev's UNet
replaced by **`unet\Flux.2 Dev\flux2_dev-Q4_K_M.gguf`** (GGUF, 17.9 GB, a
different quantization format entirely) and its text encoder replaced by
**`text_encoders\Flux.2 Dev\mistral_3_small_flux2_nvfp4_mixed.safetensors`**
(10.0 GB, also a different file - note the name is close but not identical:
`nvfp4` here vs. this section's `fp4`). Any capability conclusion drawn
against the old NVFP4 checkpoint below does **not** automatically transfer to
today's GGUF checkpoint - this exact confusion was independently caught again
during the 2026-10-04 Flux.2 Dev masking work; see
`tests/router/RESULTS_flux2dev_masking_test1.md`'s "GGUF note" and
`tests/router/RESULTS_flux2dev_capability.md` for what was actually validated
against which checkpoint.

**This is the most important delta.** A full FLUX.2 Dev branch (unet + its own
Mistral-3-small text encoder) now exists and is not mentioned anywhere in the
handover's routing table (§17/§22) — Codex needs to know it's there before
designing the T2I branch.

**Corrected (2026-07-31 review):** the original version of this section added
the file sizes (21.2 GB + 11.4 GB = 32.6 GB) and concluded the model is
"likely not runnable at all." That arithmetic is not a VRAM proof — disk size
is not simultaneously-resident VRAM. ComfyUI can offload the text encoder to
CPU after encoding, load the unet separately, and stream/offload the VAE;
actual peak VRAM depends on the runtime loading strategy, not the sum of file
sizes. The correct statement: **FLUX.2 Dev is installed, but its actual VRAM
footprint on the RTX 5080 must be measured, not inferred from file size.**

There is a real, more specific unknown worth flagging instead of the size
arithmetic: checked against the installed official templates
(`...\comfyui_workflow_templates_json\templates\image_flux2.json` and
`image_flux2_fp8.json`), the **officially templated FLUX.2 Dev path uses**
`flux2_dev_fp8mixed.safetensors` **+** `mistral_3_small_flux2_bf16.safetensors`
**or** `..._fp8.safetensors`. The installed files are a different, more
aggressive quantization — `flux2-dev-nvfp4-mixed.safetensors` +
`mistral_3_small_flux2_fp4_mixed.safetensors` (NVFP4) — which is off that
tested path. NVFP4 weights have been reported in other FLUX.2/Wan-class
workflows to sometimes get internally upcast on load on Blackwell hardware,
which would use substantially more VRAM than the on-disk NVFP4 size suggests.
**Verify whether the installed NVFP4 path stays native or gets
upcast/offloaded before routing anything to it.** A matching `Flux.2 Dev`
workflow folder already exists under `user\default\workflows\Flux.2 Dev\`
(1 workflow file — see §5); check what that workflow actually does before
assuming the installed NVFP4 checkpoint is the intended runtime path.

### Renamed / reorganized directories

```text
vae\Flux.1 Kontext\        -> vae\Flux.1 & Z-Image\   (ae.safetensors)
vae\Flux.2 klein\          -> vae\Flux.2\              (flux2-vae.safetensors)
```

The `Flux.1 Kontext` VAE folder no longer exists under that name — even the
orphaned leftover VAE the handover flagged (§6) has now been relabeled away
from "Kontext". This reinforces the handover's own conclusion: **treat FLUX.1
Kontext as fully retired**, not just "unlisted". The `Flux.2 klein` → `Flux.2`
VAE rename is consistent with the new FLUX.2 Dev model sharing the same VAE
architecture as FLUX.2 Klein.

### Confirmed unchanged / stable

- `Qwen-Image-Edit-2509-Q4_K_M.gguf` (12.168 GB) + both Qwen2.5-VL-7B text
  encoders — present, unchanged.
- Z-Image Turbo GGUF unets (`eventHorizon_zitV10-Q5_K_M`,
  `zEpicrealism_turboV1Fp8-Q5_K_M`) — present, unchanged.
- SAM3, RMBG-2.0, segformer_b2_clothes, vitmatte, body_segment — full
  segmentation stack intact.
- PuLID (`pulid_flux_v0.9.1.safetensors`), InsightFace (`antelopev2`,
  `buffalo_l`) — intact.
- No Krea model file — Krea 2 remains a dead branch (handover's assessment
  still holds).
- The Qwen3-VL vision-only GGUF pair (`Qwen3VL-4B-Instruct-Q4_K_M.gguf` +
  mmproj) the handover listed under `LLM\GGUF\...` does **not** appear in this
  scan's `models.json` — confirmed as a genuine deletion, not a scanner blind
  spot: `models\LLM\` exists on disk (`find` verified it directly) but is
  **completely empty** (0 files). The scanner's model list simply doesn't walk
  `LLM\` at all (a real gap in the scan tool, worth fixing separately), but
  that gap doesn't matter here — the files are gone either way. **Do not plan
  Layer A around the Qwen3-VL-4B path; only the Qwen2.5-VL-7B GGUF pair under
  `text_encoders\Qwen Image Edit 2509\` is confirmed present.**

---

## 5. Existing workflows relevant to the Image Director scope

```text
Qwen             1 workflow
Flux.2 klein     5 workflows
Flux.2 Dev       1 workflow   (new branch, see §4)
Z-Image Turbo    6 workflows
SDXL 1.0         7 workflows
Wan 2.2          3 workflows  (out of Version-1 scope per handover §11)
VTON             15 workflows + experiment notes  <-- directly relevant, see below
wip              8 workflows, none Image-Director-related
```

### VTON folder is existing prior art for the handover's own Test Case A

`user\default\workflows\VTON\` already contains an iterated (v10→v15)
implementation of exactly §19 "Test Case A — Clothing replacement"
(image_1 = person, image_2 = garment reference, replace only one region,
preserve identity/pose/background). Relevant prior findings the handover
doesn't cite and Codex should not re-derive from scratch:

- `Flux.2 Klein 9B\workflow_notes\EXPERIMENT_2026-06-14_Flux2Klein-Enhancer_RefControl.md`:
  static-analysis proof that `ComfyUI-Flux2Klein-Enhancer` is a **silent
  no-op on the FLUX.2 Klein path** — `comfy/ldm/lens/model.py` never calls the
  `attn1_patch`/`attn1_output_patch` hooks the pack registers. The pack only
  has effect on the **Qwen Image Edit** path (`qwen_image/model.py` does call
  these hooks). This directly qualifies the handover's §21 "Candidate route:
  FLUX.2 Klein + multi-reference latent / ref controller" — that specific
  combination does not work; the same enhancer pack routed through Qwen Image
  Edit does.
- `CONTINUE_VTON_v15.md`: a v15 workflow file was found with a broken
  `latent_image` link (dangling link, `KSampler.latent_image` unconnected) —
  attributed to editing the workflow in the ComfyUI GUI without a restart
  after installing a new custom-node pack. Relevant lesson for Codex: **always
  restart ComfyUI after cloning a new custom-node pack**, and re-verify
  workflow JSON structurally after any live-GUI edit session, before assuming
  a file is clean.

**Added 2026-07-31 review — complementary finding, kills the enhancer-on-Klein
route cleanly:** FLUX.2 Klein already ships an **official native** multi-image
edit template that needs no third-party pack at all —
`...\comfyui_workflow_templates_json\templates\image_flux2_klein_9b_kv_image_edit.json`
(also `image_flux2_klein_image_edit_9b_base.json` /
`_9b_distilled.json`). It runs entirely on ComfyUI core nodes: `UNETLoader`,
`CLIPLoader`, `VAELoader`, `CLIPTextEncode`, `VAEEncode`, chained
`ReferenceLatent` (2 in this template, one per `LoadImage`), `CFGGuider`,
`SamplerCustomAdvanced`. No `ComfyUI-Flux2Klein-Enhancer` node anywhere in the
graph. Combined with the no-op finding above, this means: **do not reach for
the enhancer pack on a FLUX.2 Klein path at all** — start from the native
template's own reference/edit mechanism, and only ask whether an enhancer adds
anything *after* that's been tried and found wanting. (One naming trap: the
native template also uses a node called `FluxKVCache` —
`comfy_extras\nodes_flux.py`, a **core ComfyUI** node for KV-caching across a
multi-step edit. It is unrelated to `ComfyUI-Flux2Klein-Enhancer`'s k/v
attention-scaling despite the similar "KV" naming — don't conflate the two.)

---

## 6. Direct answers to handover §33 questions

1. **Existing relevant workflows:** see §5 above — Qwen/FLUX.2 Klein/FLUX.2 Dev/
   Z-Image/SDXL all have workflow files already; VTON is the most mature and
   directly overlaps Test Case A.
2. **`ComfyUI-QwenVL` node classes:** `AILab_QwenVL`, `AILab_QwenVL_Advanced`,
   `AILab_QwenVL_GGUF`, `AILab_QwenVL_GGUF_Advanced`,
   `AILab_QwenVL_GGUF_PromptEnhancer`, `AILab_QwenVL_PromptEnhancer` (§2).
3. **`ComfyUI-Flux2Klein-Enhancer` node classes:** listed in §2. Functionally
   proven to only affect the Qwen Image Edit path, not FLUX.2 Klein (§5) — and
   FLUX.2 Klein already has an official native multi-reference edit template
   that doesn't need it at all (§5, 2026-07-31 addendum). Don't reach for this
   pack on a Klein path; try the native template first.
4. **Can `Qwen-Image-Edit-2509-Q4_K_M.gguf` load via installed `ComfyUI-GGUF`?**
   **Corrected (2026-07-31 review):** the original "yes" here overstated the
   evidence. `UnetLoaderGGUF`/`UnetLoaderGGUFAdvanced` classes being present
   (§2) only proves GGUF loader infrastructure exists — it does not prove this
   specific checkpoint initializes and infers correctly. Checked directly
   against the installed official templates
   (`python_embeded\Lib\site-packages\comfyui_workflow_templates_json\templates\image_qwen_image_edit_2509.json`):
   the **officially templated path uses FP8 safetensors**
   (`qwen_image_edit_2509_fp8_e4m3fn.safetensors` unet +
   `qwen_2.5_vl_7b_fp8_scaled.safetensors` CLIP), not GGUF. The Q4_K_M GGUF
   pair installed on this machine is off that tested path. Correct framing:
   **GGUF loader infrastructure is present; runtime compatibility of
   `Qwen-Image-Edit-2509-Q4_K_M.gguf` must be confirmed by a smoke test.** A
   new loader pack is probably not needed, but don't skip the test.
5. **Best identity-preservation path:** not determined by this audit (needs a
   live A/B test, not inventory inspection) — both `PuLID-Flux-Enhanced` and
   `IPAdapter_plus` (FaceID PlusV2) are installed and loadable; the
   Flux2Klein-Enhancer identity nodes (`IdentityFeatureTransfer*`) are
   VRAM-expensive per the handover's own §11 note and share the same
   Qwen-only-effective limitation as the ref controller.
6. **Can SAM3/clothes segmentation provide masks without extra deps?** Yes —
   `sam3.safetensors`, `segformer_b2_clothes`, `RMBG-2.0`, and
   `deeplabv3p-resnet50-human.onnx` are all installed and already used in the
   VTON workflows (§5).
7. **Router/switch nodes from `rgthree-comfy`:** `RgthreeAnySwitch`,
   `RgthreeContextSwitch`, `RgthreeContextSwitchBig` (§2). `comfyui-logic`
   additionally provides `IfExecute`/`IfExecuteNode`/`Compare` for conditional
   branch logic. `cg-use-everywhere` is not a router — it's a
   wiring-broadcast tool, don't use it for the task-routing layer.
8. **Save node with sufficient metadata:** `comfyui-image-saver`
   (`ImageSaverMetadata`) — see §2.
9. **Reusable generation/editing branches in current workflows:** VTON's
   Qwen-Image-Edit-based clothing-replacement chain is the closest existing
   reusable branch for Test Case A.
10. **Broken/deprecated/incompatible nodes:** none found broken outright in
    this pass. `Flux2Klein-Enhancer` is functionally dead weight on the FLUX.2
    Klein path specifically (not broken — silently ineffective). Full
    import/runtime health (ComfyUI startup log) was not checked in this audit
    pass and should be before Phase 3.

---

## 7. Likely blockers for Version 1

- **FLUX.2 Klein multi-reference via Flux2Klein-Enhancer does not work as
  designed** (§5/§6.3) — if §21 (Test Case C) is attempted, route the
  reference-boosting through Qwen Image Edit instead, or skip the enhancer
  pack for that branch entirely.
- **16 GB VRAM ceiling on an RTX 5080** with a 12.2 GB Qwen Image Edit unet
  alone (plus text encoder + VAE + any LoRA stack) leaves little headroom for
  stacking identity-preservation nodes (PuLID/IPAdapter/IdentityFeatureTransfer)
  in the same pass — smoke-test single-node VRAM cost before full-stack runs,
  as the VTON experiment notes already did.
- **FLUX.2 Dev (new since 2026-07-30) has an unmeasured VRAM footprint on this
  16 GB card** — file size (32.6 GB combined) is not a VRAM proof either way;
  actual footprint depends on ComfyUI's offload behavior and must be measured.
  The bigger specific risk: the installed weights are NVFP4
  (`flux2-dev-nvfp4-mixed.safetensors` +
  `mistral_3_small_flux2_fp4_mixed.safetensors`), while the officially
  templated FLUX.2 Dev path uses FP8 (§4) — NVFP4 has reported upcast-on-load
  issues on Blackwell in other FLUX.2/Wan-class workflows. Measure before
  routing anything to it; do not default the "high-quality generation" branch
  to it without that check.
- **Krea 2 has no installed model** — not a usable branch yet, matches
  handover's own assessment.
- **Qwen3-VL-4B vision model is confirmed absent**, not just unverified
  (§4 — `models\LLM\` exists but is empty). Only the Qwen2.5-VL-7B GGUF pair
  is confirmed present for the Layer A vision role.
- **No `IMAGE_DIRECTOR_AUDIT.md` or router implementation existed before this
  file** — Phases 2–8 of the handover's plan (§32) have not started; only the
  Qwen-Image-Edit editing branch (via VTON) has real prior art.

---

## 8. Proposed Version-1 implementation order (superseded by §9)

Original phase plan, adopted from the handover's §32 and adjusted for what
was proven at the time. **Superseded 2026-07-31 — see §9 for the current,
smaller plan.** Kept here for history; Phase 6's original text speculated
about checking whether FLUX.2 Dev calls the same `attn1_patch` hooks as Klein
— that speculation is now moot, since §5/§9 establish the native-template
route makes the enhancer pack unnecessary on FLUX.2 entirely, Dev or Klein.

```text
Phase 1 (this audit)     - done, this file
Phase 2                  - QwenVL structured-plan adapter
Phase 3                  - router (generation vs. Qwen-edit branch only)
Phase 4                  - clothing-replacement test case via VTON's chain
Phase 5                  - identity preservation A/B (PuLID vs. IPAdapter)
Phase 6                  - FLUX.2 multi-reference branch (originally: check
                            attn1_patch hooks on Dev — superseded, see §9)
Phase 7                  - refinement/upscale + comfyui-image-saver metadata
Phase 8                  - benchmark/tune
```

---

## 9. Revised V1 architecture (2026-07-31 review)

The 2026-07-31 review of this audit produced a materially smaller and cleaner
V1 than §8/the original handover — smaller because two things §8 treated as
open questions turned out to have direct answers once checked against the
installed official templates (§4, §5): FLUX.2 Klein doesn't need the enhancer
pack at all, and FLUX.2 (Dev or Klein) isn't ready for the router yet pending
a VRAM measurement. Dropping both from V1's critical path removes most of the
original router complexity.

**Layer A model change:** the handover's Qwen3-VL-4B is confirmed absent
(§4/§7) — plan Layer A around **Qwen2.5-VL 7B**
(`Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf` + mmproj, both confirmed present,
§4), loaded via `ComfyUI-QwenVL`'s `AILab_QwenVL_GGUF_Advanced` (§2).

**V1 shape:**

```text
USER INSTRUCTION + SOURCE/REFERENCE IMAGES
                |
                v
       Qwen2.5-VL 7B (Image Analyzer)
                |
                v
         Structured JSON edit plan
                |
        +-------+-------+
        |               |
        v               v
    GENERATE           EDIT
        |               |
        v               v
  Z-Image Turbo   Qwen Image Edit 2509
```

No FLUX.2 anywhere in the V1 router.

**Staged roadmap:**

```text
V1    Qwen2.5-VL 7B analyzer + router + Qwen Image Edit (2511 primary
      candidate, 2509 as A/B baseline — see §11) + Z-Image Turbo
V1.1  Identity testing: Qwen Edit output + PuLID vs. IPAdapter (A/B, §6.5)
V1.2  FLUX.2 Klein native reference/edit (§5) — no enhancer pack
V1.3  FLUX.2 Dev — only after the NVFP4 VRAM measurement from §4/§7
```

**Why Qwen Image Edit 2509 fits the Image Director goal directly, not just as
a fallback editor:** 2509 is documented for multi-image editing, improved
person/identity consistency, person+product and person+scene composition, and
native ControlNet support, with up to ~3 reference images as a sweet spot.
That maps closely onto the handover's own Test Case A/C shape (image 1 =
person, image 2 = garment, image 3 = optional second garment/material;
change only the targeted region, preserve identity/pose/background) — this is
closer to Qwen Edit 2509's actual designed task than to a generic inpaint
workflow bolted together from primitives.

**Qwen2.5-VL's two distinct roles — don't conflate them:** the same model
family appears twice in this stack for two different jobs.

1. As Qwen Image Edit 2509's own text encoder (`CLIPLoader` /
   `DualCLIPLoaderGGUF`, loaded as part of the editor's own model chain,
   §6.4) — it conditions the edit, it does not produce the image itself
   (`Qwen-Image-Edit-2509-*.gguf` does that).
2. As a **separate, standalone** Image Director Analyzer via
   `ComfyUI-QwenVL` (`AILab_QwenVL_GGUF_Advanced`) — takes the raw user
   instruction + reference images and emits the structured JSON edit plan
   *before* the editor ever runs, so the editor gets a targeted instruction
   instead of having to simultaneously understand and edit.

## 10. Open architecture question — resolved to a decision + a measurement plan (2026-07-31)

Role 1 and role 2 above are the same Qwen2.5-VL 7B model family, loaded
through two different node packs (`AILab_QwenVL_GGUF_*` for the analyzer vs.
`CLIPLoader`/`UnetLoaderGGUF`-driven for the editor's own text encoder). Same
underlying weights does **not** imply ComfyUI holds them once, or that both
node paths share one loaded model object — that depends on the concrete
loaders, ComfyUI's model-cache/offload behavior, and execution order. Not
resolvable from inventory inspection; needs the smoke test to measure.

**Three candidate architectures, in preference order:**

1. **One workflow, sequential** (target) — analyzer runs, emits JSON, is
   offloaded; editor then loads and runs. One queue press, one output, for
   the user. Memory profile must look like `analyzer ████ → release → editor
   ████████`, not an overlapping `████████ / ███████████████`.
2. **One workflow + explicit offload node** — same shape as (1), forced via
   an explicit unload/offload node between analyzer and editor, if ComfyUI's
   default cache behavior doesn't release the analyzer on its own.
3. **Two separate queue runs** (fallback) — analyzer run writes
   `edit_plan.json`, a second run consumes it + the source/reference images.
   Cleanest memory separation, guaranteed to work, but two queue presses
   instead of one. Can still be made invisible to the end user later: an
   outer Image Director orchestrator queues Run 1 (analysis) then Run 2
   (edit) and only surfaces the final output — the two-pass split is an
   implementation detail, not something the user has to see.

**Decision recorded for the handover, ahead of the test:**

> V1 should use sequential analyzer → editor execution. Whether this can
> remain inside one ComfyUI execution graph or requires two queue passes
> depends on measured model-cache/offload behavior on the RTX 5080 16 GB.

**Measurement plan — peak VRAM alone is not sufficient, a time series is
required** (a 6 GB analyzer peak and a 14 GB editor peak do not imply 20 GB
needed: `6→2→14` is fine, `6→6→16→OOM` is not):

| Test | Setup | Question |
|---|---|---|
| A | Qwen2.5-VL analyzer alone | analyzer peak VRAM |
| B | Qwen Image Edit alone | editor peak VRAM |
| C | Analyzer → editor in one workflow | does the analyzer stay resident through the editor's peak? |
| D | C with 1 / 2 / 3 reference images | realistic Image Director load |

For test C specifically, log a VRAM time series, not just a max: idle →
after analyzer load → during VLM inference → after analyzer completion →
editor load start → editor inference peak → after completion.

**Executed 2026-08-01 for B and D; A and C blocked before running — see §12.**

---

## 11. Qwen-Image-Edit-2511 — verified upgrade candidate, not yet installed

Raised in a 2026-07-31 follow-up and checked directly against the installed
template package (same method as §4/§5, not taken on faith):

- `image_qwen_image_edit_2511.json` and `image_qwen_image_edit_2511_int8.json`
  **do exist** as official ComfyUI templates
  (`...\comfyui_workflow_templates_json\templates\`) — "ComfyUI native
  support" for 2511 is confirmed, not a rumor.
- Official 2511 template reuses `qwen_image_vae.safetensors` (**already
  installed**) and the `qwen_2.5_vl_7b_fp8_scaled.safetensors` CLIP family
  (same encoder family as 2509's official path, §6.4) — so the VAE and the
  VLM/text-encoder side of the stack carry over, only the edit unet itself is
  new.
- Unet: `qwen_image_edit_2511_fp8mixed.safetensors` /
  `qwen_image_edit_2511_int8_convrot.safetensors`. **Neither is present** in
  the current model inventory (§4) — this is a genuine upgrade candidate,
  not something already sitting on disk. A GGUF build (e.g. Q4_K_M, reported
  ~13.1 GB, comparable to the installed 2509 Q4_K_M at 12.168 GB) would need
  to be sourced and downloaded before it can be tested — same runtime-not-
  proven caveat as §6.4 applies once it lands (GGUF loader presence ≠
  confirmed inference).

**Recommendation:** don't replace 2509 outright. Download a 2511 GGUF as a
second candidate, A/B it against the existing 2509 install once the Phase-2
smoke test (§10) is running anyway, and let the comparison — not the spec
sheet — decide which becomes the V1 default editor. This audit does not
download or install anything; sourcing the 2511 GGUF is a separate,
explicit step for whoever/whatever fetches it.

---

## 12. VRAM smoke tests executed (2026-08-01) — B and D done, A and C blocked

User go-ahead was given for the full §10 test plan. B and D ran against the
live ComfyUI instance (port 8188, idle baseline 1886 MiB used of 16303 MiB).
A and C did not run — blocked before submission, not attempted-and-failed.

### Why A and C are blocked — corrects §9's Layer A model pick

§9 planned Layer A around **Qwen2.5-VL-7B**
(`Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf` + mmproj) because that pair is
"confirmed present" per §4. That reasoning has the same shape as the error
§6.4 already corrected for the editor path: **class/file presence was read as
proof of a working install.** The pair lives under
`text_encoders\Qwen Image Edit 2509\` because it *is* Qwen Image Edit's own
text encoder (§9's role 1) — its presence says nothing about a standalone
analyzer install.

Checked directly against `ComfyUI-QwenVL`'s own source
(`AILab_QwenVL_GGUF.py`, `gguf_models.json`): `AILab_QwenVL_GGUF_Advanced`'s
`model_name` dropdown is populated only from `gguf_models.json`'s
`qwenVL_model` catalog, which lists **four Qwen3-VL entries only** (4B/8B ×
Instruct/Thinking) — no Qwen2.5-VL entry exists in that catalog at all. The
node also cannot point at an arbitrary installed file; it resolves a fixed
`models/llm/GGUF/<author>/<repo>/<filename>` path per catalog entry and
downloads from HuggingFace if that exact path is empty. None of the four
Qwen3-VL files are present — `models\LLM\` is confirmed empty (§4). Selecting
any catalog entry today would trigger a multi-GB HuggingFace download, not
load the installed Qwen2.5-VL-7B GGUF.

The non-GGUF node (`AILab_QwenVL_Advanced`, transformers/HF backend) *does*
list `Qwen2.5-VL-7B-Instruct` in `hf_models.json` — but selecting it
downloads a full-precision HF safetensors snapshot via `snapshot_download`,
a separate multi-GB fetch that does not reuse the installed Q4_K_S GGUF
either.

One more data point against defaulting Layer A to Qwen2.5-VL-7B: the VTON
project's own history (`Flux.2 Klein 9B\workflow_notes\DECISIONS.md`,
2026-05-21 and 2026-06-27 entries) explicitly rejected `Qwen2.5-VL-7B` as an
outfit captioner ("praktisch zu langsam", hallucinated details) and settled
on `Qwen3VL-4B-Instruct-Q4_K_M.gguf` instead — the same file that is now
deleted from this install (§4/§7). That was an RTX 2070 8 GB finding, so the
speed verdict may not transfer to the RTX 5080, but it is a real prior
negative result on §9's chosen model, not a hypothetical concern.

Separately, and smaller: a bare `python_embeded\python.exe -c "import
llama_cpp"` outside ComfyUI's own process failed to load `ggml.dll` with a
"module not found" error. This is **not** a missing-backend problem —
`ggml.dll`, `ggml-cuda.dll`, `llama.dll`, `mtmd.dll` etc. are all present on
disk under `llama_cpp\lib\` and `llama_cpp\bin\`. It's a dependent-DLL/PATH
resolution issue specific to invoking the bare interpreter outside whatever
DLL-directory setup ComfyUI's own startup does. Confirming this needs
importing `llama_cpp` from inside a running ComfyUI process (e.g. via a
diagnostic node or `/object_info` after a node import), not a repair.

**Net effect:** A and C need a Layer A model decision first — either (a)
register a working local entry in `ComfyUI-QwenVL`'s own catalog pointing at
an already-installed file, (b) source one of the four cataloged Qwen3-VL
GGUF files (a new download, e.g. `Qwen3VL-4B-Instruct-Q4_K_M.gguf` +
mmproj — the exact file the VTON history validated before it was deleted),
or (c) re-test whether `Qwen2.5-VL-7B` is actually usable on the RTX 5080
via the HF/transformers node despite the old 8 GB verdict. Option (b) is not
a free repeat of prior success, though: the VTON history that ran
`Qwen3VL-4B-Instruct-Q4_K_M.gguf` used it only as the *baseline* candidate
and separately judged the same 4B/Q4 path "zu ungenau" for outfit
captioning — re-downloading it is picking the model the project already
found imprecise, not a validated known-good pick. None of these are
audit-scope changes; §27's "prefer already-installed nodes, verify before
adding dependencies" rule puts the choice with the user, not with this
document.

### Test B — Qwen Image Edit 2509 alone (editor peak VRAM)

Built as a minimal ~10-node API-format graph (not the 50+-node VTON
workflow, which would contaminate the measurement with SAM3/RMBG/BodySegment)
by copying the topology of the installed official template
(`comfyui_workflow_templates_json\templates\image_qwen_image_edit_2509.json`)
and substituting `UnetLoaderGGUF` / `CLIPLoaderGGUF` for the template's FP8
`UNETLoader` / `CLIPLoader`, using the exact filenames confirmed live via
`/object_info`:

```
unet:  Qwen Image Edit 2509\Qwen-Image-Edit-2509-Q4_K_M.gguf
clip:  Qwen Image Edit 2509\Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf  (type=qwen_image)
vae:   Qwen Image Edit 2509\qwen_image_vae.safetensors
```

No Lightning LoRA (not verified installed, not needed for a VRAM
measurement). 8 steps, cfg 2.5, euler/simple — step count doesn't materially
change peak VRAM, only wall time. Input images are three synthetic 768×768
solid-color PNGs generated for this test (`imgdir_test_source.png`,
`imgdir_test_ref2.png`, `imgdir_test_ref3.png`) specifically to avoid using
any of the user's personal photos already sitting in `ComfyUI\input\` for a
throwaway VRAM smoke test. Queued directly via `POST /prompt` against the
live server; `nvidia-smi --query-gpu=memory.used` polled at **~1 Hz** — good
enough for the load/plateau/drop shape, but sub-second allocation spikes
between samples are not captured, so every peak below is a sampled lower
bound, not a guaranteed maximum. B, D2, and D3 were also queued
back-to-back: B was a cold start (idle 1886 MiB → climbing), but D2's first
sample was already 15659 MiB eight seconds after submit and D3's was 15249
MiB — both started from whatever was still resident from the previous run,
not from idle. Their load curves are therefore not directly comparable to
B's; only the plateau/peak values are.

**Result: success, and visually verified, not just queue-status-verified —
but the visual check was narrow, not a quality assessment.**
`Read` on all three output files
(`E:\AI_Art\ImageDirector_Test{B,D2,D3}_00001_.png`) shows photorealistic,
anatomically coherent renders — not noise, black frames, or NaN artifacts,
which is what a broken GGUF quantization or a mis-wired text encoder tends
to produce (the VTON history in §5 documents exactly that failure mode for a
different model: "defekten Output mit Token-Repetitionen"). That is the only
claim this check supports: **the GGUF unet + GGUF CLIP combination infers
correctly at the tensor level.**

It does not support a quality claim. Since the inputs were meaningless flat-
color placeholders with no real subject, the model had nothing concrete to
"keep unchanged" and invented a different figure/composition on each run —
B and D3 rendered a complete head, **D2 cropped the head at the top frame
edge**, an obvious compositional defect if this were being judged as a real
edit result. It isn't: the prompt, the input, and the run were never meant
to produce a usable image, only to exercise the loader/sampler/VRAM path.
Real output-quality evaluation (identity preservation, edit locality —
handover §19/§29/§30) needs real source and reference photos and is a
separate, later step this test does not substitute for.

Full VRAM time series in `vram_log_B.txt`/`vram_log_D2.txt`/`vram_log_D3.txt`
(session scratchpad). B's shape: idle 1886 MiB → steady climb over ~32 s as
unet+CLIP+VAE load and the image is encoded → plateau at peak during the
8-step sampler (~35 s) → drop after `VAEDecode`/`SaveImage`. Total execution
100.8 s (`execution_start` → `execution_success`).

| Test | Reference images | Peak VRAM used | Headroom (of 16303 MiB) | Status |
|---|---|---|---|---|
| B  | 1 | 15541 MiB | 762 MiB (4.7%) | success |
| D2 | 2 | 15787 MiB | 516 MiB (3.2%) | success |
| D3 | 3 | 15494 MiB | 809 MiB (5.0%) | success |

All three completed and wrote real output
(`E:\AI_Art\ImageDirector_TestB_00001_.png`, `..._TestD2_00001_.png`,
`..._TestD3_00001_.png`) — not a silently-accepted-but-failed queue item.
D3's peak being lower than D2's is allocator noise (fragmentation/timing),
not evidence that 3 references use less VRAM than 2; the honest statement is
**all three sit in a tight 15.5–15.8 GB band**, not a clean monotonic curve.

This directly answers §6.4's open question: `Qwen-Image-Edit-2509-Q4_K_M.gguf`
loads and produces correct, coherent output through the installed
`ComfyUI-GGUF` loaders — runtime compatibility is now confirmed by an
inspected result image, not just "loader infrastructure present" or a
success status code.

### Critical finding: ~11 GB stays resident after a successful run

`nvidia-smi` immediately after all three runs completed: **10975 MiB**, not
back to the 1886 MiB idle baseline. This is ComfyUI's normal model-cache
behavior (unet+CLIP+VAE kept warm in VRAM for the next queue item, not a
leak — three consecutive runs produced peaks of 15541/15787/15494 MiB with
no upward creep, so nothing is accumulating).

The 11 GB itself is not the risk — `comfy.model_management` treats cached
models as evictable, so ComfyUI can and does free that VRAM when a later
node in the same graph needs room. Resident bytes are not reserved bytes;
treating 11 GB as a hard floor would repeat §4's already-corrected mistake
of reading disk/resident size as a VRAM ceiling.

The actual risk is an **allocator boundary**, not an arithmetic one.
`AILab_QwenVL_GGUF_Advanced` loads its model through `llama_cpp`, which
allocates its own CUDA context directly — outside PyTorch, and therefore
invisible to `comfy.model_management`'s eviction logic. If the analyzer runs
first and stays resident (`keep_model_loaded=true`, or Test C shows
`.clear()` doesn't fully release it) while the editor then tries to claim
its own ~15.5–15.8 GB peak, ComfyUI's cache **cannot evict the analyzer to
make room** — it only knows about its own tracked models, not about a
parallel llama.cpp allocation. The non-GGUF analyzer path
(`AILab_QwenVL_Advanced`, transformers/`BitsAndBytesConfig`) is closer to
torch-native but still not necessarily tracked by ComfyUI's own
`ModelPatcher`/cache system, so the same boundary risk likely applies there
too, just less certainly.

Given the editor alone already leaves under 5% sampled headroom with nothing
else running, **candidate architecture 1** from §10 ("one workflow,
sequential, analyzer offloaded before editor's peak, one queue press") is
the one to bet against — not because 11 GB is reserved, but because there is
no guaranteed mechanism to force the analyzer's allocation out of VRAM
before the editor needs its own peak, if that allocation sits outside
ComfyUI's tracking. **Candidates 2 (explicit forced offload/unload between
stages, calling the analyzer node's own `.clear()`/`keep_model_loaded=false`
path) and 3 (two separate queue passes) both remain plausible** and don't
depend on resolving this boundary question in advance. Distinguishing
between 1 and 2 needs Test C run against whichever Layer A model gets chosen
(see blocker above), not further B/D iteration.

### Updated recommendation

- Don't scope V1's Layer A to a model that needs a new download without
  deciding that explicitly — that decision belongs to the user, matching
  §27.
- Once Layer A is decided, re-run Test C (analyzer → editor, one workflow)
  with the same time-series methodology used here. Given the ~5.3 GB
  headroom just measured, budget for the two-pass fallback (§10, candidate
  3) rather than assuming single-graph residency will work.
- The VRAM logs, payload builders (`build_qwen_edit_test.py`), and history
  JSON for this run are in the session scratchpad, not the repo — they are
  throwaway diagnostic artifacts, not something to commit.

---

## 13. Layer A unblocked: catalog entry + hardlinks, Tests A and C executed (2026-08-01)

§12 identified the blocker: `AILab_QwenVL_GGUF_Advanced`'s model dropdown is
populated only from `gguf_models.json`, which listed four Qwen3-VL entries
and no Qwen2.5-VL entry, so the installed
`Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf` (+ mmproj) — physically present under
`text_encoders\Qwen Image Edit 2509\` as Qwen Image Edit's own text encoder —
was not selectable as a standalone analyzer.

**Fix applied — infrastructure change, not a new node install:**

1. Confirmed the installed `ComfyUI-QwenVL` repo was actually clean
   (`git diff` empty, matches `fcd1ada`; the "dirty" flag in earlier scans is
   the known `__pycache__` false positive from §3) before touching anything.
   Backed up `gguf_models.json` to the session scratchpad regardless.
2. Added one new entry to `gguf_models.json`'s `qwenVL_model` block —
   `Qwen2.5-VL-7B-Instruct-GGUF`, same schema as the existing four Qwen3-VL
   entries, `repo_id: null` (no download source; relies entirely on the
   files already being at the resolved local path). No existing entries
   touched.
3. Created `models\LLM\GGUF\Qwen\Qwen2.5-VL-7B-Instruct-GGUF\` and placed
   **two per-file hardlinks** in it (`New-Item -ItemType HardLink`, not a
   directory link, not a copy) pointing at the existing
   `Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf` and
   `Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf` under
   `text_encoders\Qwen Image Edit 2509\`. Both paths are on `G:`, so no admin
   rights or Developer Mode were needed. Verified via `fsutil hardlink list`:
   both directory entries resolve to the same file data, zero extra disk
   used. The two paths are the same underlying bytes — a future
   redownload/repair of either copy would need to overwrite the existing
   file in place, not delete-and-replace it, or the hardlink pair would
   silently diverge.
4. Restarted ComfyUI (old PID 34740 → new PID 33352, same launch args as
   `Start ComfyUI.bat`: `--windows-standalone-build --output-directory
   E:\AI_Art --disable-auto-launch`). Startup log showed `ComfyUI-QwenVL`
   loading in 0.2 s with no errors.
5. Confirmed live via `/object_info/AILab_QwenVL_GGUF_Advanced`:
   `Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf` now appears in the `model_name`
   dropdown alongside the four Qwen3-VL entries.

A second fork (`Deaquay/ComfyUI-Qwen3.5-Uncensored`) was evaluated and
rejected for this specific task — its local-GGUF auto-scan is real (verified
by reading its source directly: `_scan_local_gguf_models`,
`find_in_llm_paths`, `read_gguf_architecture` all exist as described, no
malicious patterns found in a source read of `__init__.py`, requirements,
and the loader modules) but it still only scans `models\LLM\GGUF\`, so it
needs the identical hardlink placement this fix already does — its only
actual advantage (native Qwen3.5 support) is orthogonal to unblocking Layer A
and remains a separate, later evaluation. Installing it alongside the
existing `ComfyUI-QwenVL` was rejected outright: both packs dynamically load
`.py` files into the same global `NODE_CLASS_MAPPINGS`/`sys.modules` names
(`AILab_QwenVL_GGUF`, etc.), so running both would non-deterministically
decide which implementation every existing VTON workflow using these node
classes actually executes.

### Test A — analyzer alone

`AILab_QwenVL_GGUF_Advanced`, `model_name=Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf`,
`device=auto`, `keep_model_loaded=false`, one image
(`imgdir_test_source.png`, the same flat-color placeholder from §12 — this
test checks the vision pipeline executes and releases memory, not captioning
accuracy). Output captured via `PreviewAny` (comfyui_essentials).

**Result: success.** Peak VRAM **7861 MiB** (idle baseline 1717 MiB before
submit). Response: *"A uniform light purple square fills the entire
image."* — structurally correct (correctly identified a single flat-colored
region, not a hallucinated complex scene, not repeated/garbled tokens), color
naming was off (input was RGB 180/140/120, a muted tan, not purple) but this
is a one-word color-perception detail on a synthetic input, not evidence of
a broken model. **After completion, VRAM dropped to 1574 MiB** — at or below
the pre-test idle baseline, i.e. the `keep_model_loaded=false` → `.clear()`
path (`gc.collect()` + `torch.cuda.empty_cache()`, per the source read in
§12) released essentially all of the analyzer's VRAM back to the system.

### Test C — analyzer → editor, single graph, one queue press

Built as one ~13-node API-format graph: `LoadImage` → `AILab_QwenVL_GGUF_Advanced`
(same settings as Test A) → its `STRING` output wired **directly** into
`TextEncodeQwenImageEditPlus`'s positive `prompt` input (the actual
analyzer-text-becomes-editor-instruction pattern from the handover's
architecture diagram, not just two unrelated nodes coexisting) → the same
minimal Qwen Image Edit 2509 GGUF pipeline from §12 Test B → `SaveImage`.

**Result: success**, and the VRAM time series answers §10's open question
directly, not just plausibly:

```
1537 MiB  idle, before submit
7855 MiB  analyzer peak (matches Test A's 7861 MiB)
1537 MiB  ← immediately after, still inside the same graph execution,
             before the editor's first node has allocated anything
 ...      editor load (unet+CLIP+VAE) climbing through 4157→9317 MiB
15108 MiB editor/sampler peak (in line with §12's 15494–15787 MiB band)
10721 MiB after VAEDecode/SaveImage, execution_success
```

Total wall time `execution_start`→`execution_success`: **75.8 s** for the
full analyzer+editor pipeline in one queue press. Saved output
(`E:\AI_Art\ImageDirector_TestC_00001_.png`) is a flat light gray/pink
image — consistent with the analyzer's own text
("Light gray background with a subtle pinkish tint.") having been used
verbatim as the edit instruction, i.e. the connected pipeline behaved as
designed, not just as two independently-passing stages.

**This corrects §12's allocator-boundary caution, and narrows the actual
mechanism.** §12 speculated that `llama_cpp`'s CUDA context sits outside
`comfy.model_management`'s eviction path and worried ComfyUI could not force
it out to make room for the editor. That framing was too pessimistic about
the *specific* case tested: the release here was not the result of
ComfyUI's cache evicting a foreign allocation — it was the analyzer node
**cleaning up after itself**, synchronously, inside its own `run()`/`finally`
block, before ComfyUI's executor ever moves to the next node. That mechanism
doesn't depend on cross-model eviction working at all, which is why it fired
reliably mid-graph. **Candidate architecture 1 from §10 ("one workflow,
sequential, one queue press") is now empirically validated for this specific
pipeline shape, not merely the risky option to plan against.** The real
remaining caveat is narrower than before: this depends on every node in a
chain calling its own cleanup correctly (as this one does via
`keep_model_loaded=false`); a future Layer A or Layer B node that skips that
step would still reintroduce the residency risk §12 described.

### What's still open

- **This is still a technical smoke test, not a captioning-quality
  evaluation.** Both Test A and Test C had the analyzer describe a flat
  synthetic color field, and both times it got the exact color family wrong
  (purple / pink-gray for what was actually tan). The structured-JSON,
  multi-image, left/right-person, preserve-list evaluation the user
  specified separately (comparing this Qwen2.5-VL-7B GGUF path against a
  Qwen3-VL 8B GGUF candidate) still needs real reference photos and is
  unstarted.
- The ~76 s combined runtime directly contradicts the VTON project history's
  RTX 2070-era verdict that `Qwen2.5-VL-7B` was "praktisch zu langsam" for
  captioning (§12) — that verdict does not transfer to the RTX 5080 and
  should no longer be treated as a reason to avoid this model.
- Qwen3.5 (via the evaluated fork or otherwise) remains a legitimate,
  separate later comparison — not required to unblock V1, and deliberately
  not bundled into this infrastructure fix per the user's explicit
  instruction.

---

*Generated from `comfyui_scan\` (2026-07-31 19:16:54) plus direct inspection
of installed custom-node source files, the installed official
`comfyui_workflow_templates_json` templates, and the existing `VTON` workflow
history. §12 and §13 additionally reflect live VRAM measurements and one
infrastructure change (a `gguf_models.json` catalog entry plus two file
hardlinks in `ComfyUI-QwenVL`, both reversible — see §13) made 2026-08-01
against the running ComfyUI instance. No model files were moved, copied, or
modified; three throwaway synthetic PNGs were added to `ComfyUI\input\` for
the smoke tests and result PNGs were written to `E:\AI_Art\`.*
