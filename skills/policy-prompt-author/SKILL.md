---
name: policy-prompt-author
description: Use this skill when asked to create, revise, align, or quality-check Popu Agent system prompts in skills/policy-prompt-author/references/prompts.json for Analyst, Critic, Lobbyist, and Synthesizer.
---

# Policy Prompt Author

## Purpose

Maintain high-quality, consistent system prompts for the Popu Agent multi-agent workflow while preserving required output constraints and safety behavior.

## Source of Truth

Treat these files as authoritative prompt sources:

- `skills/policy-prompt-author/references/prompts.json`
- `agents/prompt_store.py`

Runtime loads agent instructions from `prompts.json` through `get_agent_instruction(...)`.
Use `agents/*.py` only to confirm key mapping (`analyst`, `critic`, `lobbyist`, `synthesizer`) and wiring.

For human-readable baseline and intent notes, use `references/prompts.md`.

## Workflow

1. Discover
- Read `prompts.json` and extract current prompt strings exactly.
- Confirm each key maps to the right agent module (`analyst`, `critic`, `lobbyist`, `synthesizer`).
- Identify each prompt's role, mandatory output format, and evidence requirements.

2. Draft
- Propose edits that are minimal and role-specific.
- Keep intent stable unless the user explicitly requests behavior changes.
- Preserve strict output requirements (especially Lobbyist directive structure and Synthesizer summary structure).

3. Consistency Check
- Verify that Analyst, Critic, Lobbyist, and Synthesizer prompts align in scope and handoff.
- Remove contradictory requirements across prompts.
- Ensure terminology is consistent (policy topic, directive, risks, roadmap, demographics, data points).

4. No-Regression Check
- Confirm no prompt asks for hidden reasoning, chain-of-thought, or internal search traces.
- Confirm required evidence constraints remain explicit (citations/data points where expected).
- Confirm formatting constraints remain explicit and testable.

5. Finalize
- Return revised prompt set grouped by agent.
- Include a short checklist pass/fail summary using the rubric below.

## Quality Rubric

A revised prompt set should satisfy all checks:

- Role clarity: each agent has one clear responsibility.
- Format strictness: required sections/ordering are explicit and unambiguous.
- Evidence grounding: Analyst/Critic require concrete supporting data.
- Handoff compatibility: outputs from early agents can feed later agents without re-interpretation.
- Safety/privacy: no requests for hidden reasoning or internal tool traces.
- Brevity/control: instructions are concise and avoid redundant constraints.

## Default Output Pattern

When asked to revise prompts, output in this structure:

- `Analyst` prompt
- `Critic` prompt
- `Lobbyist` prompt
- `Synthesizer` prompt
- `Validation checklist` (role, format, evidence, no-leakage)

## Notes

- Keep edits ASCII unless source text already requires Unicode.
- Prefer small iterative prompt changes over full rewrites.
