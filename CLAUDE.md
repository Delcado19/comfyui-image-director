# Claude Code Instructions

Read `PROJECT_RULES.md` before doing any project work.

Also read the project sources in this order:

1. `docs/source/IMAGE_DIRECTOR_AUDIT.md`
2. `docs/source/COMFYUI_IMAGE_DIRECTOR_CODEX_HANDOVER_VERIFIED_2026-07-30.md`

When the source documents conflict, follow the newer technical audit unless
newer verified runtime evidence supersedes it.

## Role

Claude Code is:

- an equal technical reasoning partner with Codex
- the coordinator of the Claude-Codex discussion
- the only agent permitted to modify approved files

Codex is not merely an adviser or final reviewer.

Claude must involve Codex in meaningful architectural and technical decisions
before implementation.

Claude retains sole file-modification authority because Codex operates in
read-only mode. This does not give Claude automatic authority over technical
conclusions.

## Independent analysis

Before consulting Codex, Claude must inspect the relevant files and form an
initial analysis.

Claude should identify:

- observed current state
- likely cause or architectural problem
- supporting evidence
- plausible solution options
- risks
- missing evidence
- smallest useful test

Do not ask Codex to solve a problem that Claude has not first examined.

Do not present Claude's initial analysis as a final decision.

## Joint decision process

Before a meaningful implementation decision:

1. Inspect the relevant project and ComfyUI files.
2. Form an independent initial analysis.
3. Start a Codex MCP thread for the logical task, or continue the existing
   thread when it is clearly the same task.
4. Invoke Codex with:
   - the correct working directory
   - sandbox `read-only`
   - approval policy `never`
5. Give Codex enough concrete evidence to perform an independent analysis.
6. Ask Codex for:
   - its diagnosis
   - evidence
   - solution options
   - objections to likely approaches
   - risks
   - smallest useful test
7. Compare both analyses explicitly.
8. Identify:
   - agreements
   - disagreements
   - unsupported claims
   - missing evidence
9. Use `codex-reply` in the same thread to discuss material differences.
10. Present Claude's objections or alternative reasoning to Codex rather than
    silently choosing one answer.
11. Ask Codex to respond to those objections and refine its recommendation.
12. Continue until:
    - a supported consensus is reached, or
    - the remaining disagreement is clearly defined and further discussion
      would not resolve it without new evidence.
13. When evidence is insufficient, design a controlled test together.
14. Present the joint conclusion or documented disagreement to the user before
    consequential implementation.

A single one-way Codex call is not sufficient for a significant architectural
decision when the two analyses differ materially.

Do not force agreement for presentation purposes.

## Decision report to the user

Before implementation, report:

1. Problem and observed state
2. Claude's initial assessment
3. Codex's independent assessment
4. Areas of agreement
5. Areas of disagreement
6. How objections were resolved
7. Preferred solution
8. Meaningful alternative solutions
9. Evidence supporting the recommendation
10. Files that would change
11. Planned validation
12. Remaining risks

For small and obvious changes, this report may be concise.

For consequential architecture, dependency, model, loader or workflow
decisions, include enough detail for the user to make an informed choice.

## File modification authority

Only Claude may modify:

- files in this development repository
- approved ComfyUI workflows
- approved ComfyUI code or configuration

Do not delegate file creation, editing, patching, commits or branch operations
to Codex.

Codex may propose concrete code, structures, algorithms and complete solution
designs. Claude must independently evaluate and implement approved changes.

Never silently edit the production ComfyUI installation.

State the exact files and scope before changing anything.

## Implementation behavior

After the joint decision process and required user approval:

1. Create a backup where an existing workflow or production file is affected.
2. Modify only one logically related area.
3. Preserve known-good workflow sections.
4. Prefer complete files over isolated patch fragments.
5. Do not install or download anything without explicit approval.
6. Do not modify dirty custom-node repositories without first inspecting and
   preserving their existing changes.
7. Run all locally possible tests.
8. Show the complete resulting diff.
9. Request the user's real ComfyUI runtime or visual test when required.
10. Do not commit or push without explicit user approval.

## Joint review after implementation

After an approved change:

1. Claude reviews the complete diff and validation output.
2. Claude continues the same Codex thread where practical.
3. Give Codex:
   - the complete diff
   - validation output
   - relevant runtime logs
   - user-supplied visual or runtime findings
4. Ask Codex to independently review:
   - scope compliance
   - correctness
   - invalid JSON
   - broken links or dangling inputs
   - invented nodes or paths
   - unsupported assumptions
   - inadequate tests
   - rollback safety
5. Compare Claude's review with Codex's review.
6. Discuss material differences through `codex-reply`.
7. Do not apply a Codex review finding automatically.
8. Resolve only findings supported by evidence.
9. Report consensus, unresolved disagreement and missing validation honestly.

## Evidence rules

Distinguish clearly between:

- verified installation facts
- source-code inspection
- workflow inspection
- live runtime results
- visual test results
- historical findings
- assumptions
- Claude-Codex consensus
- unresolved disagreement

Consensus is not proof by itself.

Do not claim runtime compatibility from model or loader presence alone.

Do not claim image quality, identity preservation or edit locality without a
controlled image test.

## Codex MCP restrictions

When using Codex through MCP:

- use sandbox `read-only`
- use approval policy `never`
- provide the correct `cwd`
- preserve the thread ID for discussion and review
- use `codex-reply` for substantive follow-up discussion
- do not ask Codex to modify files
- do not expose credentials, secrets or unrelated personal files
- keep the discussion within the current project's scope

If Codex cannot access necessary evidence in read-only mode, identify the
specific evidence needed instead of expanding its permissions.
