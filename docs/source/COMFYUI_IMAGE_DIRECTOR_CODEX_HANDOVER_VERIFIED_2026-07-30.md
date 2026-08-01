# ComfyUI Image Director — Codex Handover

**Purpose:** Technical handover for implementing a local, ChatGPT-Images-like image generation and editing system in ComfyUI.

**Target hardware:** AMD Ryzen 9 9950X3D + NVIDIA RTX 5080 16 GB *(project context; not reported by the attached scan)*  
**Primary platform:** Windows 11 *(project context; the scan itself only establishes a Windows-style filesystem layout)*  
**ComfyUI root:** `G:\ComfyUI-Easy-Install\ComfyUI`

**Verification status:** Installation inventory verified against the scan dated `2026-07-30 13:57:06`. Runtime loadability, node import success, GPU/VRAM detection, workflow availability, and image quality are **not** established by the inventory scan and must be audited locally by Codex before implementation.

---

## 1. Goal

Build a modular **Image Director** system around the existing ComfyUI installation.

The system should not depend on one single image model. Instead, it should route a user's instruction to the most appropriate local model or workflow:

- high-quality text-to-image generation
- fast photorealistic generation
- precision image editing
- multi-reference editing
- identity preservation
- pose / structure preservation
- selective clothing or object replacement
- detail refinement and upscaling

The intended user experience is closer to:

> "Use image 1 as the base. Replace only the man's upper garment with the garment from image 2. Keep both faces, pose, lighting, background and the woman's clothing unchanged."

than to a classic:

> prompt -> encoder -> sampler -> VAE

workflow.

---

## 2. High-Level Architecture

```text
User request
    |
    v
Vision/LLM analysis
    |
    v
Task parser / structured edit plan
    |
    +-------------------+--------------------+--------------------+
    |                   |                    |                    |
    v                   v                    v                    v
Generate            Precision edit      Multi-reference     Identity/pose
    |                   |                    |                    |
    v                   v                    v                    v
Z-Image /          Qwen Image Edit      FLUX.2 Klein      PuLID / IPAdapter /
FLUX.2             or equivalent        / reference        ControlNet / pose
                   edit workflow        workflow            support
    \                   |                    |                    /
     \__________________|____________________|___________________/
                            |
                            v
                    Refinement / upscale
                            |
                            v
                         Output
```

The routing layer should be designed so models can be swapped later without rewriting the whole workflow.

---

## 3. Important Design Principle

Treat the system as two layers:

### Layer A — Reasoning / orchestration

Responsibilities:

- understand the user's natural-language request
- inspect reference images
- determine which subjects or regions should change
- determine which subjects or regions must remain unchanged
- select a task type
- create a structured internal edit/generation specification

### Layer B — Image generation / editing

Responsibilities:

- execute the selected generation or editing workflow
- preserve requested subjects and regions
- produce the final image
- optionally run detail restoration / upscale as a post-process

The reasoning layer and the image model must remain logically separate.

---

## 4. Structured Task Format

The Image Director should convert free text into a machine-readable plan.

Example:

```yaml
task: image_edit

source_image:
  id: image_1

reference_images:
  - id: image_2
    purpose: garment_reference

edits:
  - subject: man
    region: upper_clothing
    operation: replace
    reference: image_2

preserve:
  - both identities
  - facial features
  - hairstyles
  - woman's clothing
  - man's trousers
  - pose
  - hands
  - background
  - lighting
  - camera perspective
  - framing

constraints:
  identity_strength: high
  geometry_change: minimal
  background_change: none
```

The exact schema can be adjusted, but the concept should remain.

---

## 5. Current ComfyUI Snapshot

Verified inventory snapshot:

`2026-07-30 13:57:06`

### Core

```text
ComfyUI root:
G:\ComfyUI-Easy-Install\ComfyUI

Python:
Python 3.12.13

ComfyUI remote:
https://github.com/Comfy-Org/ComfyUI

ComfyUI commit:
a8c44f9b2a0678ac4082e3529a3f43db7472acfe
short: a8c44f9b

Custom-node directories counted by scan:
59

Git-backed custom nodes:
43

Disabled custom-node directories:
1

Dirty custom-node git repositories:
7

Model files:
148
```

This is an **inventory snapshot**, not a runtime-health report. Before modifying anything, Codex must still verify current `git status`, startup/import health, GPU detection, available workflows, and actual model loading.

---

## 6. Existing Relevant Models

### Z-Image Turbo

Primary existing model:

```text
G:\ComfyUI-Easy-Install\ComfyUI\models\diffusion_models\Z-Image Turbo\jibMixZIT_v10.safetensors
```

Size in scan:

```text
5.732 GB
```

Additional Z-Image Turbo UNET/GGUF models include:

```text
eventHorizon_zitV10-Q5_K_M.gguf
zEpicrealism_turboV1Fp8-Q5_K_M.gguf
```

### Z-Image Base

Installed examples:

```text
easonZimageturboRealistic_baseV3-Q4_K_M.gguf
juggernautZ_v10ByRundiffusion-Q6_K.gguf
rayZimageBaseNSFW_v2-Q6_K.gguf
```

### FLUX.2 Klein

Installed examples:

```text
darkBeast_dbkBlitzV15.safetensors
snofsSexNudesAndOtherFunStuff_distilledV12Fp8.safetensors
unstableRevolutionF2K_AlphaF2K4BQ80.gguf
snofsSexNudesAndOtherFunStuff_v13Base-Q5_K_M.gguf
```

### FLUX.1 Kontext

The current model inventory does **not** list the previously recorded:

```text
flux1-kontext-dev-Q4_K_S.gguf
```

Only this related VAE remains in the current scan:

```text
vae\Flux.1 Kontext\ae.safetensors
```

Therefore FLUX.1 Kontext must **not** be treated as an available execution branch unless Codex finds the model elsewhere during the live audit.

### Krea 2

The custom node repository:

```text
ComfyUI-Krea2T-Enhancer
```

is installed, but the current 148-file model inventory contains **no Krea model file**. Treat Krea 2 as a future/optional branch until a compatible model is explicitly verified.

### Qwen Image Edit

Installed:

```text
Qwen-Image-Edit-2509-Q4_K_M.gguf
```

Size in scan:

```text
12.168 GB
```

### SDXL

Installed checkpoints include:

```text
artaix_v30.safetensors
jibMixRealisticXL_v180SkinSupreme.safetensors
realvisxlV50_v50LightningBakedvae.safetensors
wildcardxXLFusion_fusionOG.safetensors
```

---

## 7. Existing Relevant Text / Vision Encoders

### Z-Image Turbo Qwen3 encoders

Installed:

```text
Lockout-Qwen3-4b-zimage-hereticV2-q8.gguf
mradermacher - Huihui-Qwen3-4B-abliterated-v2.Q8_0.gguf
mradermacher - Josiefied-Qwen3-4B-abliterated-v2.Q8_0.gguf
```

All were approximately:

```text
3.986 GB
```

in the scan.

Existing test ranking:

```text
1. Lockout / Heretic
2. Huihui
3. Josiefied
```

The prior benchmark found the text encoder has a major effect on:

- material realism
- lighting
- mood
- depth

and can matter more than sampler tweaks.

### FLUX.2 Klein Qwen3 8B encoders

Installed examples:

```text
Goekdeniz_Guelmez - Josiefied-Qwen3-8B-abliterated-v1-Q4_K_M.gguf
qwen3_8b_abliterated_v2-fp8mixed.safetensors
```

### Qwen vision-language models

Verified in the current inventory:

```text
LLM\GGUF\Qwen\Qwen3-VL-4B-Instruct-GGUF\Qwen3VL-4B-Instruct-Q4_K_M.gguf
LLM\GGUF\Qwen\Qwen3-VL-4B-Instruct-GGUF\mmproj-Qwen3VL-4B-Instruct-F16.gguf
```

The previously recorded full Qwen3-VL safetensors installation is **not present in the current model inventory**.

Also verified, now grouped under the Qwen Image Edit directory:

```text
text_encoders\Qwen Image Edit 2509\Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf
text_encoders\Qwen Image Edit 2509\Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf
```

These are candidates for orchestration / image analysis, but inventory presence does not prove that `ComfyUI-QwenVL` can load each file in the desired mode. Codex must inspect the installed node classes and test the loaders.

---

## 8. Existing Relevant VAEs

Verified current paths:

```text
vae\Flux.1 Kontext\ae.safetensors
vae\Flux.2 klein\flux2-vae.safetensors
vae\pig_flux_vae_fp32-f16.gguf
vae\Qwen Image Edit 2509\qwen_image_vae.safetensors
vae\SDXL 1.0\sdxlVAE.safetensors
vae\ultrafluxVAEImproved_v10.safetensors
vae\Wan\wan_2.1_vae.safetensors
```

The previously recorded:

```text
zImageClearVae_natural.safetensors
```

is **not present in the current 2026-07-30 model inventory**.

---

## 9. Existing Relevant Identity / Reference Components

Installed:

### IPAdapter

```text
ComfyUI_IPAdapter_plus
```

Model:

```text
ip-adapter-faceid-plusv2_sdxl.bin
```

LoRA:

```text
ip-adapter-faceid-plusv2_sdxl_lora.safetensors
```

### PuLID

Custom node:

```text
ComfyUI-PuLID-Flux-Enhanced
```

Model:

```text
pulid_flux_v0.9.1.safetensors
```

### InsightFace

Installed model sets include:

```text
antelopev2
buffalo_l
```

### Pose / Control

Relevant installed nodes:

```text
comfyui_controlnet_aux
ComfyUI-SCAIL-Pose
ComfyUI-WanAnimatePreprocess
controlaltai-nodes
```

Installed ControlNet model:

```text
controlnet-canny-sdxl-1.0-fp16.safetensors
```

Installed Z-Image patch:

```text
Z-Image-Turbo-Fun-Controlnet-Union-2.1.safetensors
```

---

## 10. Existing Relevant Segmentation / Masking

Installed nodes:

```text
comfyui-easy-sam3
comfyui-rmbg
ComfyUI_LayerStyle
comfyui-inpaint-cropandstitch
```

Installed models include:

```text
sam3.safetensors
RMBG-2.0\model.safetensors
body_segment\deeplabv3p-resnet50-human.onnx
segformer_b2_clothes\model.safetensors
vitmatte\model.safetensors
```

These should be reused before adding redundant segmentation dependencies.

---

## 11. Existing Relevant Workflow / Utility Nodes

Verified installed candidates:

```text
ComfyUI-Easy-Use
rgthree-comfy
cg-use-everywhere
comfyui-logic
comfyui-kjnodes
comfyui_essentials
comfyui-detail-daemon
RES4LYF
ComfyUI-NAG
ComfyUI-GGUF
ComfyUI-FitDiTx
ComfyUI-TiledDiffusion
comfyui_ultimatesdupscale
ComfyUI-Flux2Klein-Enhancer
ComfyUI-Krea2T-Enhancer
ComfyUI-QwenVL
comfyui-image-saver
comfyui-prompt-reader-node
save-image-organized
```

Additional provider-specific caption nodes now exist:

```text
comfyui-google-gemini-outfit-caption
comfyui-nvidia-nim-outfit-caption
```

Do not make provider-specific captioning a dependency of the local-first Version 1. Codex may inspect these nodes as optional comparison/reference implementations.

The existing `ComfyUI-Flux2Klein-Enhancer` repository already exposes files with names suggesting useful functionality:

```text
flux2_klein_color_anchor.py
flux2_klein_enhancer.py
flux2_klein_mask_ref_controller.py
flux2_klein_ref_controller.py
flux2_klein_text_enhancer.py
flux2_sectioned_encoder.py
Flux2klein_Ksampler_exp.py
identity_feature_transfer.py
identity_guidance.py
multi_reference_latent.py
```

Investigate this node pack before implementing overlapping logic elsewhere.

### Newly present but outside Version-1 scope

The current inventory also includes video-oriented additions such as `ComfyUI-LTXVideo`, Wan 2.2 model assets, RIFE frame interpolation, and an FP8 SEEDVR2 model. They explain part of the inventory growth but should remain outside the Version-1 Image Director unless the scope is explicitly expanded.

---

## 12. Dirty Git Repositories

The current scan reports **seven** dirty custom-node repositories:

```text
ComfyUI-Flux2Klein-Enhancer           bdbd930
comfyui-google-gemini-outfit-caption b478534
ComfyUI-Krea2T-Enhancer               50422e3
ComfyUI-PuLID-Flux-Enhanced           edcb3af
ComfyUI-QwenVL                        fcd1ada
comfyui-rmbg                          d740251
wlsh_nodes                            9780746
```

Do not blindly pull, reset, rebase or overwrite these.

Before touching any repository:

```text
git status
git diff
git branch --show-current
git log -1 --oneline
```

Preserve local changes.

---

## 13. Current Z-Image Turbo Baseline

Existing tested baseline:

```text
model: jibMixZIT_v10.safetensors
sampler: euler
scheduler: simple
steps: 10
cfg: 1.0
denoise: 1.0
```

Alternative tested combinations:

```text
res_multistep + simple
dpmpp_sde + beta
dpmpp_sde + ddim_uniform
euler_ancestral + beta
```

For Z-Image Turbo, the current recommendation is:

```text
CFG 1.0 as default
```

not traditional SDXL-style high CFG.

---

## 14. Existing Z-Image Material / Style Assets

Relevant installed Z-Image Turbo LoRAs include:

```text
latex_z_image.safetensors
merge-rubber-suits-2.safetensors
EtherealGothicZ_000002000.safetensors
Z-Detail-Slider.safetensors
REDZ15_DetailDaemonZ_lora_v1.1.safetensors
ZIT_Luneva CyberHD.safetensors
ZIT_Midjourney_Luneva_Cinematic_v1_r128.safetensors
Z-EldenArt.safetensors
zImageT_zidiusArt_melancholy.safetensors
ZiTMythR3alisticF.safetensors
```

These matter because the target look emphasizes:

- dark Gothic styling
- strong contrast
- cinematic lighting
- realistic black materials
- leather / latex / rubber readability
- detailed clothing

---

## 15. SeedVarianceEnhancer Findings

**Evidence status:** historical tuning result from the earlier Z-Image test documents; the current scan confirms the node and relevant Z-Image assets still exist, but these settings have not been re-benchmarked under the 2026-07-30 runtime.

Existing custom node:

```text
seedvarianceenhancer
```

Existing test summary found:

```text
40 / 14 / SW15
```

to be the best character/control balance for the tested Gothic Z-Image workflow.

Safer alternative:

```text
35 / 12 / SW10
```

The test indicated that stronger settings increase:

- image character
- dramatic presence
- lighting contrast
- material aggression

but also increase risk of:

- organic black-mass collapse
- throne / clothing / skull merging
- weaker anatomy
- muddy lower-body areas

Do not make SeedVarianceEnhancer a mandatory global stage. Treat it as an optional style/variation module.

---

## 16. Quantization Strategy

The existing `Quantization Guide.md` was written for the **previous RTX 2070 setup**. Its historical rule of thumb was:

```text
Q6_K      = quality-first
Q5_K_M    = preferred practical compromise
Q4_K_M    = fallback
below Q4  = only when necessary
```

Do **not** treat that ranking as a validated RTX 5080 benchmark.

For the Image Director project:

- detect the actual current GPU and VRAM during the audit
- measure model-specific VRAM and latency
- prefer the highest practical precision that fits the required workflow
- compare FP8 / Q6 / Q5 / Q4 only where multiple variants actually exist
- avoid reducing precision solely because the old RTX 2070 guide recommended it
- document offloading behavior for Qwen Image Edit and other large branches

The attached installation scan does not contain GPU/VRAM data, so no new quantization recommendation is considered verified yet.

---

## 17. Proposed Task Router

Initial task classes:

```text
TEXT_TO_IMAGE
FAST_PHOTOREALISTIC
IMAGE_EDIT
LOCAL_REGION_EDIT
MULTI_REFERENCE_EDIT
IDENTITY_PRESERVING_EDIT
POSE_PRESERVING_EDIT
STYLE_TRANSFER
UPSCALE
DETAIL_REFINEMENT
```

Suggested first-pass routing:

```text
TEXT_TO_IMAGE
    -> Z-Image Turbo / FLUX.2
    -> Krea 2 only after a compatible Krea model is installed and verified

FAST_PHOTOREALISTIC
    -> Z-Image Turbo

IMAGE_EDIT
    -> Qwen Image Edit

LOCAL_REGION_EDIT
    -> segmentation/mask + Qwen Image Edit or inpaint workflow

MULTI_REFERENCE_EDIT
    -> FLUX.2 Klein / existing Flux2Klein enhancer nodes

IDENTITY_PRESERVING_EDIT
    -> PuLID / IPAdapter / identity guidance + selected editor

POSE_PRESERVING_EDIT
    -> pose extraction / ControlNet / SCAIL pose support

UPSCALE
    -> existing upscaler pipeline

DETAIL_REFINEMENT
    -> targeted refinement only after main generation/edit
```

Do not hard-code model names into the routing logic if a configurable model registry is practical.

---

## 18. Proposed Internal Data Model

Use a typed structure similar to:

```python
class ImageDirectorRequest:
    task_type: str
    prompt: str
    source_images: list
    reference_images: list
    edits: list
    preserve: list
    constraints: dict
    model_preferences: dict
```

Possible edit object:

```python
class EditInstruction:
    subject: str
    region: str
    operation: str
    reference_image: str | None
    strength: float | None
```

The exact implementation language can follow the existing node repository.

---

## 19. First Implementation Target

Do not attempt the full system at once.

Build one end-to-end use case first:

### Test Case A — Clothing replacement

Inputs:

```text
image_1 = source scene/person
image_2 = clothing reference
instruction = replace only upper clothing
```

Expected behavior:

```text
Change:
- man's upper garment

Preserve:
- face
- hair
- body proportions
- pose
- hands
- trousers
- second person
- background
- camera
- lighting
```

Use:

```text
QwenVL analysis
-> structured plan
-> subject/garment mask if needed
-> Qwen Image Edit or FLUX.2 edit route
-> identity preservation
-> optional cleanup
```

This single case is enough to validate whether the architecture is sound.

---

## 20. Second Implementation Target

### Test Case B — Body-shape adjustment without identity drift

Instruction example:

```text
Make the woman's hips slightly narrower.
Do not change her face, clothing, pose, hands, background or lighting.
```

Success criteria:

- controlled geometry change
- no face drift
- no clothing redesign
- no background regeneration
- no new accessories
- no significant pose change

---

## 21. Third Implementation Target

### Test Case C — Multi-reference composition

Inputs:

```text
image_1 = subject / composition
image_2 = clothing reference
image_3 = material / style reference
```

Instruction:

```text
Keep image 1's identity, pose, framing and environment.
Use the garment construction from image 2.
Use the material appearance from image 3.
```

Candidate route:

```text
FLUX.2 Klein
+ multi-reference latent / ref controller
+ identity guidance
```

Check the existing `ComfyUI-Flux2Klein-Enhancer` implementation first.

---

## 22. Model Selection Philosophy

Do not select the largest model by default.

Select by task.

### Z-Image Turbo

Use when:

- fast high-quality generation
- photorealistic people
- dark fashion
- strong material rendering
- cinematic generation

### Qwen Image Edit

Use when:

- semantic image editing
- replacing one item
- preserving most of an existing image
- localized natural-language edits

### FLUX.2 Klein

Use when:

- multiple references
- reference blending
- structured edit tasks where FLUX.2 tooling is already present
- identity-guided reference workflows

### SDXL

Keep as compatibility / specialized LoRA / ControlNet branch.

Do not delete or deprecate it prematurely.

---

## 23. Vision / LLM Layer

Current inventory candidates:

```text
Qwen3VL-4B-Instruct-Q4_K_M.gguf
+ mmproj-Qwen3VL-4B-Instruct-F16.gguf

Qwen2.5-VL-7B-Instruct-UD-Q4_K_S.gguf
+ Qwen2.5-VL-7B-Instruct-mmproj-BF16.gguf
```

`ComfyUI-QwenVL` is installed, but the inventory alone does not establish which of these combinations the current node implementation can load successfully. Verify the exact loader/node classes and run a minimal inference test before making the VLM route mandatory.

Initial responsibility:

1. inspect source image(s)
2. identify subjects
3. identify requested target regions
4. identify preservation constraints
5. output strict JSON/YAML
6. never directly rewrite the whole request as a creative prompt unless the task is generation

Suggested structured output:

```json
{
  "task": "LOCAL_REGION_EDIT",
  "subject": "man",
  "target_region": "upper_clothing",
  "operation": "replace",
  "reference_image": "image_2",
  "preserve": [
    "face",
    "hair",
    "pose",
    "hands",
    "trousers",
    "woman",
    "background",
    "lighting",
    "camera"
  ]
}
```

---

## 24. UI Concept

Possible ComfyUI front-end workflow:

```text
[Instruction]
[Source Image]
[Reference Image 1]
[Reference Image 2]
[Reference Image 3]

        |
        v

[Image Director Analyzer]

outputs:
- task type
- structured instruction
- preserve list
- model route

        |
        v

[Router]

        |
        +--> Generation branch
        +--> Qwen Edit branch
        +--> FLUX.2 branch
        +--> Identity branch
        +--> Pose branch
```

Inspect `rgthree-comfy`, `comfyui-logic`, and `cg-use-everywhere` before implementing custom routing/switching logic. Use existing nodes where they satisfy the requirements; do not assume a specific switch node exists until its actual node classes are inspected.

---

## 25. Logging / Debugging

Every run should expose:

```text
Detected task type
Selected model branch
Parsed edits
Preserve constraints
Reference images used
Mask source
Identity module used
Sampler
Scheduler
Steps
CFG
Denoise
Seed
LoRAs
Quantization / precision
```

This should be easy to inspect after a failed result.

A "black box" router is not acceptable.

---

## 26. Reproducibility

Every generated image should retain enough metadata to reproduce:

- model
- text encoder
- VAE
- LoRAs
- sampler
- scheduler
- steps
- CFG
- denoise
- seed
- prompt
- structured edit plan
- branch selection
- reference image identifiers
- key strengths / weights

Do not sacrifice reproducibility for convenience.

Current installed metadata/save candidates include:

```text
save-image-organized
comfyui-image-saver
comfyui-prompt-reader-node
```

Codex must verify which of these preserves the required workflow/prompt metadata before selecting the Version-1 output path.

---

## 27. Safety Around Existing Installation

This ComfyUI installation is heavily customized.

Rules:

1. Do not change global ComfyUI configuration without necessity.
2. Do not overwrite custom nodes.
3. Do not reset dirty git repositories.
4. Do not install large node packs when existing nodes already provide the needed function.
5. Do not invent nodes that are not installed.
6. Prefer native ComfyUI nodes and already-installed custom nodes.
7. Before adding a dependency, verify current ComfyUI compatibility.
8. Test after every meaningful change.
9. Keep rollback available.

---

## 28. Git Workflow

Before edits:

```powershell
Set-Location "G:\ComfyUI-Easy-Install\ComfyUI"
git status
git log -1 --oneline
```

For any custom node repository to be modified:

```powershell
Set-Location "G:\ComfyUI-Easy-Install\ComfyUI\custom_nodes\<repo>"
git status
git diff
git branch --show-current
git log -1 --oneline
```

Do not commit unrelated local changes.

Preferred workflow:

```text
inspect
-> backup / branch
-> modify
-> test
-> review diff
-> commit only working state
```

Rollback must remain easy.

---

## 29. Testing Philosophy

Use controlled A/B tests.

Keep constant:

```text
source image
reference images
seed
resolution
model
text encoder
VAE
LoRA stack
sampler
scheduler
steps
CFG
denoise
```

Change only one variable at a time.

For visual comparison, score:

```text
identity
prompt compliance
edit locality
material realism
lighting consistency
anatomy
background preservation
overall quality
```

---

## 30. Acceptance Criteria

The first usable version is accepted when:

### A. Router

- correctly distinguishes generation vs edit
- correctly identifies local-region edits
- produces readable structured output

### B. Edit locality

- requested region changes
- non-target regions remain substantially unchanged

### C. Identity

- faces remain recognizably stable
- no unnecessary hairstyle drift
- no uncontrolled body/pose changes

### D. Reference handling

- garment reference influences garment
- style/material reference can be isolated from identity reference
- multiple references do not simply blend everything indiscriminately

### E. Reproducibility

- same inputs + same seed + same settings produce repeatable output

### F. Debuggability

- user can see which branch and settings were selected

---

## 31. Non-Goals for Version 1

Do not initially build:

- a full conversational UI
- automatic model downloading
- automatic LoRA discovery
- automatic online model search
- video support
- training / fine-tuning
- cloud fallback
- autonomous installation of dependencies
- dozens of task branches

Start with reliable image editing and routing.

---

## 32. Recommended Development Order

```text
Phase 1
- inspect current installation
- inspect existing workflows
- inspect relevant custom nodes
- confirm current model paths

Phase 2
- define structured request schema
- build QwenVL analysis node / adapter
- emit JSON/YAML

Phase 3
- create task router
- generation branch
- Qwen Image Edit branch

Phase 4
- implement clothing-replacement test case
- add mask support only if needed

Phase 5
- add identity preservation
- PuLID / IPAdapter / existing identity guidance

Phase 6
- add FLUX.2 multi-reference branch
- reuse Flux2Klein enhancer functionality

Phase 7
- add refinement / upscale
- preserve metadata

Phase 8
- benchmark and tune
```

---

## 33. Questions Codex Should Answer Before Coding

1. What relevant workflows already exist in the user's ComfyUI workflow directory?
2. Which exact node classes are available from `ComfyUI-QwenVL`?
3. Which exact node classes are available from `ComfyUI-Flux2Klein-Enhancer`?
4. Can `Qwen-Image-Edit-2509-Q4_K_M.gguf` be loaded by the installed `ComfyUI-GGUF` branch without adding another loader?
5. Which installed identity-preservation path works best with the chosen editor?
6. Can SAM3 / clothes segmentation provide reliable masks without extra dependencies?
7. Which router/switch nodes from `rgthree-comfy` are already available?
8. Which existing save node preserves enough workflow metadata?
9. Which current workflows already contain reusable generation or editing branches?
10. Which installed nodes are currently broken, deprecated or incompatible with Python 3.12.13?

Do not guess these. Inspect the actual installation.

---

## 34. First Codex Assignment

### Objective

Create a technical audit before modifying files.

### Required output

Produce:

```text
IMAGE_DIRECTOR_AUDIT.md
```

containing:

- current ComfyUI commit
- current Python version
- current GPU detection
- current VRAM
- relevant model files and paths
- relevant custom nodes
- dirty repositories
- existing workflows related to:
  - Z-Image
  - Qwen Image Edit
  - FLUX.2
  - QwenVL
  - Krea 2 / Krea2T enhancer
  - PuLID
  - IPAdapter
  - ControlNet
  - SAM3
- routing/logic options from `rgthree-comfy`, `comfyui-logic`, and `cg-use-everywhere`
- metadata/output options from `save-image-organized`, `comfyui-image-saver`, and `comfyui-prompt-reader-node`
- missing dependencies
- likely reusable nodes
- likely blockers
- proposed version-1 implementation plan

Do not change anything during this audit.

---

## 35. Second Codex Assignment

After the audit is reviewed:

Create a minimal proof of concept implementing:

```text
instruction
+ source image
+ optional reference image
        |
        v
QwenVL structured analysis
        |
        v
task router
        |
        +--> generation
        |
        +--> image edit
```

The output should expose the structured plan visibly in the workflow.

No hidden routing.

---

## 36. Third Codex Assignment

Implement the first real acceptance test:

### Clothing replacement

```text
Base image:
person / scene

Reference image:
garment

Instruction:
Replace only the target person's upper garment using the reference garment.
```

Preserve:

```text
identity
face
hair
pose
hands
other people
non-target clothing
background
lighting
camera
```

Document:

```text
workflow used
models used
nodes used
parameters
limitations
known failure modes
```

---

## 37. Important User Preferences for This Project

- normal discussion can be German
- technical documentation should be English
- prefer complete copy/paste-ready files
- prefer full workflow JSON over patch fragments
- do not provide invented ComfyUI nodes
- use only nodes confirmed in the installation or explicitly added
- verify current documentation / `--help` / actual tool output before proposing software-specific syntax
- preserve working functionality
- backup known-good state before edits
- test each change
- commit only after tests pass
- rollback must remain possible

---

## 38. Source Files and Evidence Status

### Current inventory — authoritative for installed-file claims

```text
comfyui_summary.json   scan timestamp 2026-07-30 13:57:06
custom_nodes.json      current attached inventory
models.json            current attached inventory
report.txt             current attached scan report
```

### Historical benchmark / tuning evidence

```text
Quantization Guide.md
Qwen3 4B Q8_0 GGUF - CLIP Benchmark (Z-Image Turbo).md
Z-Image Turbo Sampler Scheduler Analyse.md
SeedVarianceEnhancer Test Summary — Z-Image Turbo.md
```

Historical tuning documents are useful evidence for prior tested behavior, but they must not override the current installation inventory. In particular, the quantization guide targets the previous RTX 2070 environment.

The current scan proves file/repository inventory only. It does **not** prove runtime compatibility, successful imports, workflow existence, GPU/VRAM state, or model loadability.

---

## 39. Verification Delta from the Previous Handover

The previous handover was based on the 2026-06-25 scan. The 2026-07-30 inventory changes the following implementation facts:

| Item | Previous handover | Verified current state |
|---|---|---|
| ComfyUI root | `H:\ComfyUI-Easy-Install\ComfyUI` | `G:\ComfyUI-Easy-Install\ComfyUI` |
| Python | `3.14.3` | `3.12.13` |
| ComfyUI commit | `f6c162dd` | `a8c44f9b` |
| Custom-node count | `44` | `59` |
| Git-backed nodes | `36` | `43` |
| Dirty repos | `5` | `7` |
| Model files | `130` | `148` |
| FLUX.1 Kontext UNet | listed | not present in current inventory |
| Krea2T enhancer | absent from old scan | installed, dirty |
| Krea 2 model | implied future option | no model found in current inventory |
| Full Qwen3-VL safetensors | previously listed | not present in current inventory |
| `zImageClearVae_natural` | previously listed | not present in current inventory |
| Routing helpers | mainly `rgthree-comfy` | also `comfyui-logic`, `cg-use-everywhere` |
| Metadata helpers | existing save path | also `comfyui-image-saver`, `comfyui-prompt-reader-node` |

This table is the minimum set of corrections Codex must honor before beginning the audit.

---

# Final Instruction to Codex

Treat the current ComfyUI installation as a working production environment.

Do not begin by installing new frameworks.

First inspect what is already present, identify reusable components, and build the smallest working version of the Image Director using existing models and nodes.

The goal is not to recreate the internals of ChatGPT Images.

The goal is to recreate the useful behavior:

```text
natural-language instruction
-> image understanding
-> structured edit plan
-> correct model/tool routing
-> local controlled image generation/editing
-> reproducible result
```

Prioritize:

```text
1. control
2. preservation
3. reproducibility
4. image quality
5. speed
```

in that order for the first image-editing implementation.
