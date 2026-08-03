# Test E2 result — 2 reference images, analyzer + editor, one graph

Scope: infrastructure/VRAM only. No image-quality, identity, edit-locality,
or prompt-quality conclusions are drawn from this test.

## Run identity

- prompt_id: `8a9bb962-e320-4270-9c0b-617bbd846ee2`
- Graph: `E2_graph.json` (15 nodes, analyzer seed 20260801, `keep_model_loaded=false`)
- Reference images: source (`imgdir_test_source.png`, analyzer input + editor `image1`),
  `imgdir_test_ref2.png` (editor `image2`) — 2 reference images at the editor
  stage, confirmed directly in the submitted graph JSON (`image1`, `image2`
  present on both `TextEncodeQwenImageEditPlus` nodes, no `image3`).
- Wall time: 122.56 s (`comfyui.log`) / 123.0 s (`submit_and_monitor.py`).
- Output: `E:\AI_Art\ImageDirector_TestE2_00001_.png`, 262,819 bytes — exists,
  non-trivial size. No content/quality judgement made or implied.
- `/history` status: `completed=true`, no `execution_error` message. Cached
  nodes were 1,2,3,4,7,10,11,12 (loaders/scale/VAEEncode — expected, same
  models/images as prior runs on this still-running server). Node 16
  (analyzer) was NOT cached — confirms the seed-based cache-bust worked and
  the analyzer executed fresh.

## VRAM time series (250 ms sampling, `vram_log_E2.csv`, 664 samples)

Correlated against `G:\ComfyUI-Easy-Install\ComfyUI\user\comfyui.log`
(`comfyui_log_excerpt_E2.txt`) — not `comfyui_8188.log`, which turned out to
be stale/unwritten since June 29 for this server process.

| Event | Wall time | VRAM used | VRAM free |
|---|---|---|---|
| Pre-submit flat baseline (5 consecutive samples) | t=-8s..0s | 1056 MiB | 14922 MiB |
| `got prompt` (first post-submit sample) | t=0.0s | 1135 MiB | 14843 MiB |
| Editor's own CLIP (QwenImageTEModel_) requested | t=+6.8s | 12035 MiB | 3943 MiB |
| Editor's own CLIP loaded completely (6222.63 MB) | t=+10.6s | 14051 MiB | 1927 MiB |
| Analyzer GGUF load start (`[QwenVL] Loading GGUF...`) | t=+11.8s | 14083 MiB | 1895 MiB |
| **Analyzer inference plateau** (held flat for ~21s straight, 35.73s total inference) — **sampled series peak** | t=+37.2s..+58.5s | **15866 MiB** | **112 MiB** |
| Analyzer unload begins; floor oscillates ~11.6-13.7k MiB for ~3.3s, then one brief true minimum before editor reload | t=+59.1s..+62.3s | 11648-13664 MiB (floor), **5824 MiB (true minimum, one 250ms sample)** | 2314-4330 MiB (floor), **10154 MiB (minimum sample)** |
| Editor unet loaded ("partially", 73 MB offloaded), climbing back up | t=+64.8s | 14560 MiB | 1418 MiB |
| Sampler 8/8 steps done | t=+121.5s | 13664 MiB | 2314 MiB |
| `Prompt executed in 122.56 seconds` | t=+122.6s | 10400 MiB | 5578 MiB |

Sampled series peak: **15866 MiB used / 112 MiB free**, held flat for
roughly 21 seconds straight (samples at t=21:34:53.664 through
t=21:35:14.721) — a sustained plateau, not a brief spike — inside the
analyzer-inference window, not during the editor's own sampler phase.
The lowest point reached anywhere between the analyzer's plateau and the
editor's reload is a single 250ms sample at 5824 MiB used / 10154 MiB free
(t=21:35:18.524) — a real, if brief, partial release, but still ~4.7 GiB
above the 1056 MiB pre-submit idle baseline, not a return to idle.

## What this shows — and does not

The editor's own text-encoder (the same Qwen2.5-VL-7B family, loaded here
as Qwen Image Edit's CLIP, per audit §9's "two distinct roles" note) was
requested and fully loaded into VRAM **before** the analyzer even started
loading its own GGUF — not after, and not released before the analyzer ran.
Both were simultaneously resident in VRAM during the analyzer's own
35.73s inference window, which is where the run's peak (15864-15866 MiB)
occurred — not during the editor's diffusion sampler phase, unlike the
D2/D3 baseline tests (audit §12) where the peak was the sampler's own
peak with no analyzer in the graph at all.

This is a directly log-evidenced fact, not an inference from the VRAM
shape alone. Mechanism, confirmed against ComfyUI's own executor source by
Codex during the joint review (thread `019fbec8-4345-7af1-ba75-b996e16d801f`):
the graph's negative-prompt `TextEncodeQwenImageEditPlus` node ("8") does
not depend on the analyzer node's output — only on the already-available
CLIP/VAE loaders and reference images — so ComfyUI's `ExecutionList`
(topological traversal from the output node, staging whichever node's
inputs are satisfied first) is free to schedule it, and thus trigger
`clip.tokenize()` / `clip.encode_from_tokens_scheduled()` on the editor's
CLIP, before or while the analyzer node runs. This is not strictly a
"lower node ID wins" rule — Codex's source read points to traversal order
plus cache state, not raw ID ordering. Test C's original graph (not
available as a saved file to diff against — built ad-hoc in a prior
session, per the audit's own admission) may have had different node
ordering or cache state that avoided this early scheduling, which would
explain why Test C's 1-reference case showed a clean two-phase separation
and this 2-reference case did not — without the reference-image count
itself being the deciding factor.

## Acceptance criteria (TESTPLAN.md, agreed with Codex before running)

| # | Criterion | Result |
|---|---|---|
| 1 | Graph completes with no node error | PASS |
| 2 | No CUDA OOM | PASS (but see margin below) |
| 3 | No server disconnect | PASS |
| 4 | Analyzer and editor peaks as two distinct, non-overlapping plateaus | **FAIL** — editor CLIP resident throughout the analyzer's entire run |
| 5 | Visible trough back near pre-submit idle baseline between the two phases | **FAIL** — true minimum after the analyzer's unload was a single brief sample at 5824 MiB used (10154 MiB free); the surrounding floor oscillated ~11.6-13.7k MiB. Both are ~4.7-12.6 GiB above the 1056 MiB pre-submit idle baseline, not a return to idle |
| 6 | SaveImage output exists, non-trivial size | PASS (262,819 bytes, verified on disk) |
| 7 | >= 300 MiB free at peak | **FAIL** — 112-114 MiB free at peak, well under the 300 MiB floor |
| 8 | Reference image count in submitted graph matches intent (2) | PASS (confirmed in `E2_graph.json`) |

**Result: E2 FAILED (3 of 8 criteria not met: #4, #5, #7).**

Per the user's own explicit instruction ("Falls E2 fehlschlägt ... Test E3
nicht ausführen"), **E3 was not executed.** Claude and Codex jointly
evaluated this result (thread `019fbec8-4345-7af1-ba75-b996e16d801f`) and
reached consensus: E2 failed, and E3 should not run on this evidence — no
disagreement between the two.

## Explicit limitations

- This test proves an infrastructure/VRAM behavior only. No claim is made
  or implied about analyzer output quality, edit quality, identity
  preservation, or edit locality.
- 250 ms sampling still cannot rule out a shorter sub-250ms spike either
  higher or lower than what was captured.
- The scheduling-order mechanism above is source-supported (Codex checked
  ComfyUI's executor source during joint review), but the specific claim
  that Test C's original graph avoided this via different node
  ordering/cache state is inference, not confirmed — Test C's exact graph
  JSON was never saved and is not available to diff against.
- This was a single run (n=1) for E2; allocator/timing noise between runs
  (as already documented for D2/D3 in audit §12) means the exact peak/free
  numbers could vary somewhat on a repeat run, though the qualitative
  finding (editor CLIP loads before/alongside the analyzer) is a discrete
  scheduling fact from the log, not a noisy measurement.
