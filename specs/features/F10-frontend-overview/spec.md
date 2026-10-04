# F10 · Frontend Shell & Overview

Follow `05-ux-guidelines.md` for all visual and layout decisions.

## Functional requirements
| ID | Requirement |
|---|---|
| F10-FR-01 | App shell: sidebar, top bar, routing (`/overview`, `/agents`, `/sync`, `/audit`, `/admin`), React Query client, generated API client (F09-FR-08), error boundary, toasts |
| F10-FR-02 | Persona switcher (DEMO_MODE): lists `/api/users`. Selecting one sets the `X-Demo-User` header for all requests, persists in `sessionStorage` and refetches everything. The current persona and role are shown in the user chip |
| F10-FR-03 | Freshness pill and demo clock in the top bar. Both poll every 10 s (`/api/sync/status`, scenario `/clock` via API proxy) |
| F10-FR-04 | Filters band: Type (multi), Class (multi), Campaign (pill/dropdown toggle with counts and search), tag-flag chips, free-text search, active-filter summary with "clear all". Filter state lives in the URL query string (shareable, survives reload) |
| F10-FR-05 | Period selector: All dates (default), This/Last/Next week, This month, Custom range (two-month calendar). It applies to the whole page |
| F10-FR-06 | Alerts band: air-gap (count + top items, click filters to them), late, on hold, rejected. Hidden when all are zero |
| F10-FR-07 | Flow strip per the UX guide, including the mode caption and click-to-filter |
| F10-FR-08 | Metrics ribbon: 7 chips (headline = last complete week) with sparkline (inline SVG, no chart library needed) and `awaiting_signal` handling |
| F10-FR-09 | Batch table: exceptions-first default, column sort, per-column filter, row tag chips, deviation/inbound lights, overridden need-by shown italic with pencil and the system date struck through, RAG cell. Virtualised for 1,000 rows. CSV export button (uses `/api/export.csv` with current filters) |
| F10-FR-10 | Empty, loading (skeleton) and error states for every band |
| F10-FR-11 | When `contract_run_id` changes between polls (new data arrived), show a subtle "Updated just now" toast and highlight changed rows for 5 s (the act 3 "it moved!" moment) |

## Acceptance criteria
- **F10-AC-01** (Playwright) Overview loads with seeded data in < 2 s on the target laptop. All bands are rendered.
- **F10-AC-02** Switching persona to Sam disables edit affordances, and the user chip shows "Sam · Viewer".
- **F10-AC-03** Clicking the "QC Testing" flow card filters the table to that stage, and the URL contains `stage=qc_testing`. Reload keeps the filter.
- **F10-AC-04** Selecting "This week" changes the flow-strip caption to "due in period", and overdue rows remain visible.
- **F10-AC-05** After calling the LIMS event API `POST :8102/events/approved` for B1042's sample and `make pipeline`, B1042 shows stage "QA Release" within 90 s of the event, without a manual refresh, and the row is highlighted. (F13 later wraps this as a scenario step.)
- **F10-AC-06** Metric chips M1, M2, M4, M5 show "–" with the tooltip reason.
- **F10-AC-07** Vitest component tests for the flow strip, metric chip and table cell renderers.
- **F10-AC-08** No console errors, and a Lighthouse accessibility score ≥ 90 on Overview.
