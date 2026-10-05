# F15 · Plan
- `frontend/src/theme/tokens.ts` + `tailwind.config` extensions; `components/shell/{Sidebar,TopBar,PeriodPicker,FeedbackButton}.tsx`; `hooks/useTerms.ts`.
- Period picker: Radix Popover; a small calendar component (no heavy date-picker dependency; use `date-fns` for arithmetic, approved).
- Backend: `r2r_core.profile.Terms` model; `app_api` feedback router + migration.
- Keep the F10/F11 Playwright specs green by updating selectors (use `data-testid`, not text).

## Deviations
