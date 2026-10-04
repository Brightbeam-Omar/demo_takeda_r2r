# T2-05 · Huddle / Leadership Briefing Agent

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Natural-language Q&A over the published contract and a generated morning exceptions brief, the leadership 'digital tier' visibility story.

## Scope
- Q&A: tool-using agent with read-only query tools over the API (no free SQL); answers include a table and links to rows; refuses questions outside data
- Morning brief: deterministic exception selection (late, air gap, blocked, due this week) + model-written summary; validator checks every number in the text against the computed set
- Brief shown on Overview for Site Lead persona; exportable

## Acceptance sketch
- Every numeric claim in a brief matches the computed figures (validator)
- Q&A answers 10 canned questions correctly in eval
