# F15 · Plan
- `frontend/src/theme/tokens.ts` + `tailwind.config` extensions; `components/shell/{Sidebar,TopBar,PeriodPicker,FeedbackButton}.tsx`; `hooks/useTerms.ts`.
- Period picker: Radix Popover; a small calendar component (no heavy date-picker dependency; use `date-fns` for arithmetic, approved).
- Backend: `r2r_core.profile.Terms` model; `app_api` feedback router + migration.
- Keep the F10/F11 Playwright specs green by updating selectors (use `data-testid`, not text).

## Deviations
- **Group labels use secondary text, not muted.** 05 v2 §2 gives muted text `#9CA3AF` for the VIEWS and ADMIN labels, but at 11 px that is 2.5:1 on white and axe (F10-AC-08) reports it as a serious contrast violation. The labels use secondary text `#6B7280` (4.8:1). Muted stays for non-text and disabled uses.
- **Shared period state is the URL.** The period picker is in the top bar on every page (05 v2 §3) and keeps its value in the `period`/`from`/`to` query parameters that F10 already used, so no new state store. Navigating to another page starts from All Dates again.
- **`useTerms()` reads a context.** `TermsProvider` (in the layout) fills it from `/api/reference`; components outside the shell fall back to the generic defaults, which keeps isolated component tests free of a query client.
- **No `date-fns`.** The two-month calendar reuses the F10 `lib/calendar.ts`, so the approved dependency was not needed.
- **Roadmap hygiene:** `RELEASE_BADGE` reaches the browser through `/api/reference` (OQ-081), not a Vite build variable.
