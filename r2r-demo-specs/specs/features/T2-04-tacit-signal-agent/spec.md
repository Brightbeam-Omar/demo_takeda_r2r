# T2-04 · Tacit-Signal Agent & Unstructured Corpus

> **Status: draft (outline).** Detail this into full `spec.md`/`plan.md`/`tasks.md` (same format as Tier 1) before building. Claude Code: do not implement from this outline. Ask the human to promote it first.

## Goal
Demonstrate capture of tacit knowledge: weak signals in handovers/emails/huddle notes linked to batches, suppliers and materials.

## Scope
- Datagen produces ~150 synthetic shift handovers, emails and huddle notes with **planted signals** (labelled ground truth in a sidecar file): e.g. supplier SUP012 'drums arrived with condensation again', analyst note on method drift, 3PL access issue
- Agent extracts `Signal {type (perceptual|pattern|workaround|historical|social), entity refs, quote span, confidence}`; validator checks quote spans exist verbatim and entity IDs resolve
- Context card on batch drawer and a 'Signals' tab; human can confirm/dismiss (confirmed signals become structured, audited knowledge)
- Supplier view: weak-signal chain across deliveries

## Acceptance sketch
- Precision/recall vs planted ground truth reported by the eval harness (T2-06)
- No signal is shown without a verbatim source quote
