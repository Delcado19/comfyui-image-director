# A/B isolation: does the "background" clause in the prompt cause the global tint?

Closes the open concern flagged in `RESULTS_content_quality.md`'s case-3
update: the failing run's analyzer-generated `prompt` described the blue
reference swatch as "a solid blue **background**", the passing re-test's
prompt said just "a solid blue" - flagged as "the most plausible observed
contributor... but this was not isolated in an A/B test."

## Method

The analyzer is non-deterministic (can't force two samples to differ by
exactly one word), so this bypasses it entirely. `tests/router/ab_background_word.py`
builds a standalone edit-only graph reusing the exact edit-branch nodes from
`build_router_graph.py` (`edit_unet`/`edit_clip`/`edit_vae`/`edit_scale`/
`edit_model`/`edit_model_s`/`edit_latent`/`edit_cond_pos`/`edit_cond_neg`/
`edit_sample`/`edit_image`/`save`), with `edit_prompt_str`'s source replaced
by a literal `PrimitiveString` (same node `lazy_switch_probe.py` already
uses - no invented node) instead of the analyzer's `GetTextFromJson` output.
Negative prompt still runs through `StringSubstring(literal, 0, 0)` to match
the router's own empty-negative dependency shape. Per Codex's review
(thread `019fcb5f-8503-7641-85a0-f7a74b1b7659`), this removes analyzer
sampling, router choice, schema, and `role` as confounds - it isolates
exactly the consumed prompt text.

Same seed (424242), same source image (`IMG_7148.jpg`), same reference
image (`imgdir_test_ref2.png`, the blue swatch), same edit-branch params
both runs. Prompt text identical except the clause under test:

- **with**: "...which appears as a solid blue **background**. The rest
  should remain unchanged."
- **without**: "...which appears as a solid blue. The rest should remain
  unchanged."

(Wording matches the two real analyzer samples from `RESULTS_content_quality.md`
as closely as possible.) Graphs: `tests/router/runs/AB_bg_with.graph.json`,
`AB_bg_without.graph.json`.

## Runtime anomaly (cause found via Windows Event Log, not further diagnosed)

ComfyUI crashed with no traceback in its own log between the two runs -
the log shows "got prompt" for the "without" submission at 19:13:17 and
then nothing further; the process stopped responding on port 8188. GPU
came back idle/normal (1682 MiB used) once checked, so not an OOM/VRAM
capacity issue as far as observed.

Windows Event Log (Application, `Application Error`/`Windows Error
Reporting`, event IDs 1000/1001) confirms a real native-code crash at
19:13:26 - `python.exe` (the ComfyUI embedded interpreter) hit an access
violation (`0xc0000005`) inside
`G:\ComfyUI-Easy-Install\python_embeded\Lib\site-packages\torch\lib\c10.dll`
(PyTorch's core C++ library), offset `0x8f514`. This is a hard native
crash, not a Python exception - explains why nothing appeared in
ComfyUI's own log (a Python-level traceback would have been written; a
C++-level access violation kills the process before that can happen).
Timing lines up with model loading/inference during the "without" run's
processing.

n=1, not reproduced, not further diagnosed (out of scope for this test -
per Codex's guidance, a quick read-only log triage was sufficient; no
config change or repro attempt made). Candidate causes not distinguished:
driver-level flakiness, a CUDA allocator race, or a PyTorch/torch build
issue - genuinely unknown from this single occurrence. User restarted
ComfyUI; the "without" run was then re-submitted fresh with a `/free`
first, same seed/graph as originally planned. Per Codex: this restart gap
weakens "same process state" but not the isolation itself - same graph,
seed, images, params, comparably cold-start VRAM conditions both times.

## Result

**Confirmed, single-variable difference reproduces both prior patterns
exactly:**
- **"with background"**: the entire image tinted blue - sky, buildings,
  pavement, background - matching the original case-3 failure. The dress
  itself barely changed (stayed near-black).
- **"without background"**: only the dress turned blue; the rest of the
  photo (background, pose, everything else) preserved correctly - matching
  the passing re-test.

## What this settles

Per Codex's sign-off on this wording: standalone edit-only A/B confirmed
the consumed prompt wording was causal for this specific image/prompt pair
- with the phrase "solid blue background," Qwen Image Edit 2511 applied the
blue globally; with the otherwise identical phrase "solid blue," it
localized the color change to the dress. This does not prove the word
"background" universally causes global recolors in all prompts/images, but
it explains the original case-3 failure better than the schema `role` fix,
which is not consumed by the render path (established in
`RESULTS_content_quality.md`).

## What this does not settle / open concern

- Single seed, single image pair - not tested across other photos,
  garments, or reference colors. Whether this generalizes (e.g. any prompt
  describing a reference as a "background" leaks a global-restyle
  interpretation to the model) vs. is specific to this exact wording/image
  is unknown.
- The runtime crash between runs is undiagnosed - flagged for awareness,
  not investigated as its own issue here.
- Practical implication for the analyzer prompt (`GUIDANCE` in
  `build_router_graph.py`) - e.g. instructing the analyzer to avoid the
  word "background" when describing reference-image content - has not been
  designed or tested; this result only explains the prior failure, it
  doesn't yet fix the analyzer's prompting.

## Follow-up attempt: guidance-clause fix — tried, failed, reverted

Tried the obvious next step: added one clause to `GUIDANCE` (only when
references are present) instructing the analyzer to avoid scene-level words
like "background"/"backdrop" when describing reference content, unless the
edit is actually about the scene. Codex reviewed the scope and wording
before implementation (thread `019fcb5f-8503-7641-85a0-f7a74b1b7659`).

Re-ran case 3 through the **full router** (real analyzer, not bypassed;
seed 99001/analyzer_seed 99002, same photo + blue swatch). Result: **the
guidance did not work.**
- The analyzer's generated `prompt` still said "...which appears as a solid
  blue background..." - the new instruction did not suppress the word at
  this temperature (0.1, the analyzer's existing default) at n=1.
- The visual result was also still wrong, in a different way than before:
  the dress stayed black (didn't recolor at all), and a large blue
  rectangular patch appeared in the scene's mid-ground instead - not a
  full-image tint this time, but still not the intended dress-only
  recolor. Graph: `tests/router/runs/CQ_multiref_retest2.graph.json`.

Per Codex: one clean negative result (failed both the wording check and the
visual check) is enough - more seeds would only characterize flakiness in
an approach that already looks unreliable, not produce a trustworthy fix.
Consistent with `PROMPT_EXPERIMENT_2026-08-03.md`'s prior finding that
single-clause prompt patches on this analyzer aren't reliable without a
real reliability screen. **The guidance-clause change was reverted** -
`build_router_graph.py`'s `GUIDANCE`/`REFERENCE_NOTE_BY_COUNT` are back to
their pre-experiment state, no `REFERENCE_PROMPT_NOTE`.

**Still open:** a real mitigation for reference-based local color/attribute
transfer likely needs something other than more analyzer wording - e.g.
changing how the consumed edit prompt is constructed, or adding explicit
localization/masking for garment-level recolor requests. Not designed or
attempted here.
