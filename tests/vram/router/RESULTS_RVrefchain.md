# Back-to-back router requests with multi-reference edit, no `/free` — result

**Update (run 2, same session):** repeated with fresh seeds
(`RVrefchain2_generate.graph.json`/`RVrefchain2_edit.graph.json`, log
`vram_log_RVrefchain2.csv`). Result: **463 MiB free** at the worst sampled
point - notably roomier than run 1's 196 MiB, never dropped under 400 MiB
at all. Both runs completed without error, full-load confirmed both times.
n=2: {196, 463} MiB free - confirms real run-to-run variance in this exact
scenario (consistent with this project's already-documented allocator/
driver-level drift), not that 196 MiB was a one-off measurement error.
Neither number is a stable "the" margin; 196 MiB remains the worst
*observed* case and the reason the mandatory rule stays in force - a
scenario that can produce 196 MiB on one run and 463 MiB on the next is
not one to call safe without `/free`, precisely because of that spread.

Extends `RESULTS_RVfix.md`'s back-to-back-without-`/free` characterization
(single-image edit) to the multi-reference case now that
`tests/router/build_router_graph.py` supports it
(`RESULTS_RVref.md`). Same method as `RESULTS_RVchain.md`/`RESULTS_RVfix.md`:
fresh `/free`, generate request submitted and completed, then a 2-reference
edit request submitted immediately after with no `/free` in between. One
continuous `nvidia-smi` CSV log spans both. Fresh seeds both graphs
(`tests/router/runs/RVrefchain_generate.graph.json`,
`RVrefchain_edit.graph.json`). Log: `vram_log_RVrefchain.csv`.

**Result: completed without error, but with the tightest sampled margin
recorded anywhere in this project - 196 MiB free.**

## Timeline

- Idle baseline (fresh `/free`): ~1970 MiB used.
- RVrefchain-generate: completed normally, prompt_id
  `b04f7085-f2cf-4d1a-946e-8693d353d2de`.
- RVrefchain-edit (2 references) submitted immediately after, no `/free`:
  completed normally, prompt_id `80cea4a9-a9f5-4a29-a64f-e9b73cb6cd5a`,
  output `ImageDirector_router_00017_.png` produced. Log confirms
  `QwenImage` requested to load at 15:54:23.117, next model load
  (`WanVAE`, i.e. after `KSampler`+`VAEDecode`) not requested until
  15:55:55.308 - a ~92s window covering the full-load + sampling phase.
- Within that window: **337 consecutive samples under 1000 MiB free**
  (15:54:29.843-15:55:55.282, ~85s), **111 consecutive samples under
  400 MiB free** (15:55:12.297-15:55:55.282, ~27.5s), worst single sample
  **196 MiB free** at 15:55:16.360. No errors, no OOM, no lowvram
  fallback anywhere in the log for this window.

## The finding

The analyzer-load gap stays fixed (the `free_vram_before_load` proactive
eviction still applies here; no near-miss occurs at the analyzer's own
load in this run). But the edit branch's own tight window - already
documented as a real, unmitigated constraint in `RESULTS_RVfix.md` for the
single-image case (271/238 MiB free, n=2) - is substantially tighter with
2 reference images stacked on top of a resident prior request: **196 MiB
free**, sustained across a long window (~27.5s under 400 MiB), not a brief
spike. This is tighter than the single-image back-to-back case despite the
*isolated* multi-reference margin (RVref3: 916 MiB free) being roomier
than the isolated single-image margin (456 MiB free) - the back-to-back
sequencing cost is larger for the multi-reference case, not smaller,
opposite of what the isolated numbers alone would suggest.

## What this settles

- Multi-reference router requests complete successfully at n=2 even under
  back-to-back-without-`/free` sequencing that stacks a resident prior
  request - no observed failure in either run.
- The existing mandatory `/free`-between-requests rule
  (`PROJECT_RULES.md`) is not just "still needed" for the multi-reference
  case - this run is the strongest evidence for that rule so far. 196 MiB
  free is close enough to 0 that this project's working assumption
  ("passed, but not a wide margin") no longer feels like sufficient
  caution for this specific combination (back-to-back + multi-reference).
  A single unlucky sample, a driver overhead spike, or a slightly larger
  prompt/context could plausibly tip this into a real CUDA OOM. This is
  the worst margin observed so far, not proof that multi-reference is
  always higher risk than single-image (n=1, see below).

## What this does not settle / open concern

- n=2 now (196, 463 MiB free) - confirms real spread, not a repeat-run
  guarantee of "always tight" or "always fine." A repeat run with 1
  reference (to interpolate between the single-image and 2-reference
  cases) would still strengthen this further, not done here.
- Root cause of *why* multi-reference back-to-back costs more margin than
  single-image back-to-back, and why run 1 vs run 2 differ so much from
  each other, is not investigated - candidates include the extra
  `VAEEncode`/`TextEncodeQwenImageEditPlus` work for 2 additional images
  adding to peak transient memory during the same tight window, or the
  same allocator/driver-level variance already flagged in
  `RESULTS_RVfix.md`'s unexplained ~500 MiB gap - not confirmed against
  the log/CSV at a finer granularity than done here.
- No mitigation attempted (same position as `RESULTS_RVfix.md`'s
  single-image finding) - the accepted mitigation remains calling `/free`
  between requests in production, now with stronger evidence that skipping
  it is worse for multi-reference requests specifically.
