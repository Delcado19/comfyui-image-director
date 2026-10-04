# ComfyUI Image Director

![ComfyUI Image Director](.github/social-preview.jpg)

A local, modular router for ComfyUI: natural-language instructions and
reference images in, a structured plan out, routed to the right
generation or editing workflow - one graph, one queue press.

## What it does

A vision-language analyzer turns a free-text instruction (plus up to two
reference images) into a structured JSON plan (task type, prompt, what to
preserve). A deterministic lazy switch - no LLM-authored routing decision
- then picks:

- **generate** - text-to-image (Z-Image Turbo)
- **edit** - image editing, with a choice of editor:
  - **Qwen Image Edit 2511** (default) - general-purpose instruction
    editing, with an optional masked-reference mode for region-targeted
    color/material transfer (reference content must be named in text)
  - **FLUX.2 Klein 9B** (opt-in, masked-reference only) - transfers a
    reference image's color/material onto a masked region *without*
    naming it in text, via SAM3 segmentation + latent noise masking
  - **FLUX.2 Dev**, GGUF (opt-in, experimental, masked-reference only) -
    same mechanism as Klein, ~14 minutes per edit; validated for
    feasibility, not for production latency

Only the selected branch ever executes - unused branches, including their
model loads, are never scheduled (ComfyUI's lazy node evaluation).

## Status

Personal research/engineering project, not a packaged product. Built
incrementally with a heavy emphasis on empirical validation: every
non-trivial mechanism (masking, reference transfer, VRAM behavior, router
wiring) has a corresponding `tests/router/RESULTS_*.md` writeup, including
negative results and corrections, not just successes.

## How it works

- `tests/router/build_router_graph.py` builds the full ComfyUI API graph
  for a given instruction (analyzer -> switch -> branch -> single
  `SaveImage`) and submits it directly to a running ComfyUI instance's
  HTTP API.
- `image_director/edit_plan_schema.py` defines the structured JSON schema
  the analyzer is constrained to (grammar-constrained decoding via
  `QwenVLStructuredGGUF`).
- `tests/router/*.py` beyond the router itself are the causal/capability
  tests this project is built on - each one backed by a `RESULTS_*.md`
  with the actual evidence, not just a conclusion.

This repo contains no standalone installer or `requirements.txt` - it
assumes an already-configured ComfyUI installation (with the specific
custom nodes and model checkpoints referenced in `PROJECT_RULES.md`) and
talks to it over HTTP, the same way ComfyUI's own frontend does.

## Project docs

- `PROJECT_RULES.md` - project goal, environment, and the full evidence
  log of what's been tried, what worked, and what didn't.
- `AGENTS.md` / `CLAUDE.md` - the joint Claude-Codex collaboration process
  this project is developed under (independent analysis, cross-review,
  documented disagreement, evidence-before-conclusions).
