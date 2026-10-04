# 05 · UX Guidelines

## Principles
1. **Exceptions first.** The screen answers "what needs attention right now?" before "what is everything?"
2. **Show the provenance.** Every number can be clicked to explain itself. Human-entered values are visibly distinct from system values (pencil icon and italic, system value struck through when overridden).
3. **Screen-share legible.** Designed for 1440×900 at 100% zoom: base font 14 px, table 13 px, no text under 12 px.
4. **Calm by default.** Colour carries meaning only (status/RAG). Everything else is neutral.

## Visual system (generic, client-neutral "Demo Pharma" identity)
| Token | Value |
|---|---|
| Font | Inter (self-hosted, no CDN), fallback system-ui |
| Neutral | slate scale (Tailwind `slate-50…900`) |
| Primary/accent | indigo-600 (actions, focus) |
| RAG | red-600 / amber-500 / emerald-600, each with a 50-tint background for chips |
| Stage colours | one muted hue per stage in sort order (sky, cyan, teal, emerald, lime, amber, orange, violet) for the flow strip and stage chips only |
| Radius | 8 px cards, 6 px chips |
| Density | table row height 36 px |

Logo: a simple "R2R Intelligence" wordmark with a generic mark. Badge `DEMO · Phase 1 Trusted Data` in the sidebar.

## Layout
- **Left sidebar** (240 px, collapsible): Overview, Reports (Tier 2), Agents, Sync Status, Audit Log, Admin (admin only). Footer: persona switcher (DEMO_MODE), environment badge, site name.
- **Top bar:** page title · freshness pill (`● Data current · last pipeline run 12 min ago`, green < 6 h, amber 6–12 h, red > 12 h, measured in demo time) · period selector · demo clock (`Mon 12 Oct 2026 08:00`) · user chip.
- **Overview bands** (top to bottom): Filters → Alerts → Pipeline by Stage (flow strip) → Weekly Metrics (M1–M7) → Batch table.

## Components
- **Flow strip:** a card per stage with label, count and SLA days. Separate cards for Total and On Hold. A red outline when `breached`. Click toggles the stage filter. Caption shows the "snapshot" or "due in period" mode.
- **Metric chip:** id + label, **last complete week %** (headline), week-to-date as a small secondary value, sparkline of 12 weeks, SLA days. Colour by thresholds. `awaiting_signal` shows a grey "–" with a tooltip giving `null_reason` and a "Tier 2" tag.
- **Batch table** (TanStack Table): columns Material (no + desc + tag chips) · Campaign · Batch · Location · Inbound · Deviation · Stage · System need-by · Adjusted need-by · Expected completion · Days in stage · Status. Exceptions-first default. Sticky header. Per-column filter. Row click opens the **Batch drawer** (right, 560 px).
- **Tag chips:** HOLD, RE-EVAL, EXPEDITE, FULL SPEC, OFFSITE, ERP BLOCKED, REJECTED, AIR GAP.
- **Explain popover:** an "ⓘ" icon beside every computed value opens a popover with: rule/formula in words → inputs table → source refs → pipeline run id + time. Copyable.
- **Edit modal (need-by):** read-only system date box, date picker, reason code (required), EXPEDITE checkbox, note, live preview of the new expected completion and compression **before saving**, Save / Clear override.
- **Write controls** are hidden for roles without permission. In DEMO_MODE they appear disabled with a tooltip "Read-only role", so the RBAC point can be made.

## Copy
Plain language. Stage labels from the profile. Dates `12 Oct 2026`. Durations `5 d`. Never show raw JSON to a business persona; JSON is allowed only on the Explain "source refs" expander and the Agent Trace page.
