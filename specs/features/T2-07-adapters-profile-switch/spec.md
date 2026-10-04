# T2-07 · S/4-like Adapter, Spreadsheet Ingest, Site Profile Switch

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Prove reusability across sites and stacks (act 8).

## Scope
- ERP adapter interface in the pipeline extract; `s4_like` view set in erp_sim (MATDOC-style unified material document, I_-style views) producing identical `batch_flat`
- Spreadsheet ingest adapter: a site that keeps part of the process in Excel uploads a template workbook (validated) as a source
- `site_b.yaml` (different stage set, e.g. no 3PL/call-off, extra 'Documentation Review' stage, different SLAs, `adapters.erp: s4_like`), its own seed and story
- Admin profile switch → reset with new profile; UI labels/stages/metrics follow profile with zero code changes

## Acceptance sketch
- Switching to site_b and resetting renders a different flow strip and SLAs; stage engine tests pass for both profiles
- ECC-like and S/4-like adapters produce identical batch_flat for the same world

## Open questions
- Allowing profile-defined custom stages requires rule logic in profile (Tier 1 fixed rules) → design a constrained rule DSL
