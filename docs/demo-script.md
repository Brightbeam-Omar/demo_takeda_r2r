# Demo script

For the **Presenter** (who drives the screen) and the **SME** (who answers the process questions). Plain language
on purpose: if a sentence needs a technical word, say it the way the SME would say it on the shop floor.

The demo has two versions of the same story:

| Version | Length | Use it for |
|---|---|---|
| **Working call** | 40 minutes | Site digital delivery manager, quality and supply SMEs. Acts 1, 2, 3, 5, 6 with questions |
| **Leadership cut** | 12 minutes | Global digital and manufacturing leaders. *Draft: SME to confirm* (see the end) |

Act 4 (what happens when the automatic update is switched off) and acts 7 and 8 (trust and "your world") are not
built yet. Do not promise them. If asked, say they are next.

Everything on screen is synthetic. The site is "Site A – Harbourview". The clock on screen is a demo clock: it starts
on **Monday 12 Oct 2026, 08:00** and only moves when you move it.

---

## Before you start

**The night before** (stack off or on):

1. `make doctor`. It checks Docker, memory, ports, `.env`, the leak list and (if the stack is up) the recordings. Every failure prints its fix.
2. `make up`, then `make doctor EXPECT_UP=1`. All lines must say `ok`.

**30 minutes before:**

1. `make demo-reset` (under 3 minutes). It also repairs a stale recordings folder by itself.
2. `make doctor EXPECT_UP=1` again. Look at the last two lines: *recordings* and *replay keys: 4 of 4*.
3. Open **http://localhost:8080** (present from this address, not from 5173). Browser at 100% zoom, window 1440×900.
4. Sign-in is automatic. You start as **Pat · Planner**.
5. Open the legacy tracker workbook in a spreadsheet application, in a separate window: `artifacts/legacy_tracker.xlsx`. If it is missing: `uv run python -m datagen legacy-workbook --out artifacts/legacy_tracker.xlsx`.
6. Have a terminal open in the project folder, ready for the recovery commands below.
7. Backup: the recorded run-through is `artifacts/video/run-of-show.webm` (made by `make record-video`).

**Do not click around beforehand.** The demo needs the opening state: B1042 not yet approved, B2077 not yet
adjusted, no agent proposals. If you did, run `make demo-reset` again.

### The five people on screen

Switch with the **Persona** box at the bottom of the left menu.

| Persona | Can do | You use them in |
|---|---|---|
| Pat · Planner | Change need-by dates, add comments | Acts 2, 5 |
| Quinn · QC Lead | Set status, approve QC proposals | Q&A |
| Alex · QA Release Lead | Approve QA proposals (the air-gap ticket) | Act 6 |
| Sam · Viewer | Look only | Act 2 |
| Admin | Everything, plus **Demo Controls** | Act 3 |

### Recovery moves at a glance

Every scripted step can be run from **Demo Controls** (as Admin, in the left menu under ADMIN) or from the terminal
as `make scenario STEP=<id>`. A step whose button is greyed out has already run; hover to read why.

| If this fails live | Use this step | Terminal |
|---|---|---|
| The LIMS approval does not move B1042 | `lims-approve-B1042` | `make scenario STEP=lims-approve-B1042` |
| The screen is behind the data | `run-pipeline` | `make scenario STEP=run-pipeline` |
| The need-by edit will not save | `pull-forward-B2077` (does the edit as Pat) | `make scenario STEP=pull-forward-B2077` |
| **Run air-gap agent** fails | `airgap-agent` (runs it as Alex) | `make scenario STEP=airgap-agent` |
| Nothing works at all | Play the backup video | `open artifacts/video/run-of-show.webm` |

If the agent says "No recording for key": run `docker compose up -d --force-recreate agents`, wait ten seconds, try again.

---

# The 40-minute working call

| Act | What | Minutes |
|---|---|---|
| 1 | The problem: the tracker you live with | 4 |
| 2 | Monday morning: exceptions first | 8 |
| 3 | Under the hood: one approval travels the real path | 10 |
| 5 | Human judgement: pull a campaign forward | 7 |
| 6 | The agent: a ticket with evidence, a person decides | 8 |
| | Close and questions | 3 |

(Numbering follows the product run-of-show. Act 4 is not built, so there is no act 4 here.)

## Act 1 · The problem (4 min)

**Clicks**
1. Switch to the spreadsheet window with the legacy tracker.
2. Scroll the tabs along the bottom. Stop on a tab full of colours and typed notes.
3. Click a status cell and type over it, to show how easy that is. Press undo.

**Say**
- "This is how the huddle runs today: one workbook, many tabs, around thirty people looking at it each week."
- "The status in this cell was typed by someone. When the meeting ends it starts to go out of date."
- "If two people save at once, the last one wins. Nobody can tell who changed what, or why."
- *(SME)* "Every Monday somebody rebuilds the KPIs by hand from this."

**Why it matters to the customer** Senior people spend their week deriving numbers instead of making decisions, and a late batch can hide in a tab nobody opened.

**Time** 4 minutes. Do not demo the workbook in detail; the point is the feeling.

**If it goes wrong** The workbook does not open: say the same words over the Overview screen, then continue. No recovery step is needed.

## Act 2 · Monday morning (8 min)

**Clicks**
1. Switch to the browser, **Overview**. It opens as **Pat · Planner**.
2. Point at the top bar: "last sync 0 min ago", the clock (12/10/2026 08:00), and the persona.
3. Point at the red band **LIMS–SAP Insights (4 batches)**. This is the exceptions-first view.
4. Point at the **Pipeline by stage** cards: the count per stage, the SLA days and "late" in red.
5. Point at the **Week 41 R2R metrics** row: M3 Sampling On-Time, M6 Testing On-Time, M7 QA Release On-Time. Cards that say "Awaiting signal" depend on data feeds that come later.
6. Click the **LATE** tag above the table. The table narrows to late batches. Click **ALL** to clear it.
7. Switch the **Persona** (bottom left) to **Sam · Viewer**. Point at the pencil in the Adjusted Need-By column: it is greyed out. Hover it: "Read-only role".
8. Switch back to **Pat · Planner**. The pencil works again.

**Say**
- "The first thing you see is what needs attention: four batches where the lab has approved but the ERP has not caught up."
- "These numbers are not typed. Every count and every percentage comes from the systems of record."
- "Who you are decides what you can do. Sam can look but not touch; the server refuses, not just the button."
- *(SME)* Name one stage card and say what the team does there on a Monday.

**Why it matters to the customer** The huddle starts at the problems, not at the first row of a spreadsheet, and nobody can change a plan they are not allowed to change.

**Time** 8 minutes: 3 on the screen, 3 on the metrics and tags, 2 on the persona switch.

**If it goes wrong** The page is slow or blank: press reload once. Still wrong: run `make scenario STEP=run-pipeline` and reload. Numbers look different from this script: the demo was clicked beforehand; run `make demo-reset` and start the act again.

## Act 3 · Under the hood (10 min)

This is the proof that nothing on screen is faked.

**Clicks**
1. On Overview, type **B1042** in the search box. The row shows **QCL Testing**.
2. Switch the persona to **Admin**. In the left menu under ADMIN, click **Demo Controls**.
3. Find **LIMS approves B1042**. Read its one-line talk track aloud. Click **Run**.
4. Watch the **Progress** panel on the right: *LIMS: approve the sample*, *Run the pipeline*, *Wait for the app to sync*. About 30 seconds. The Run button now greys out; hover it to read why ("already been approved").
5. Click **Webhook Sync Status** in the menu. The newest row reads **done**: "the data product told the app something changed, and the app picked it up".
6. Click **Sync Status**. The newest run says **OK**. Click the run link at the end of its row to show the pipeline run in the run viewer, then come back.
7. Go to **Overview** and search **B1042** again. It now says **QA Release**, highlighted.
8. Clear the search. On the **M3 Sampling On-Time** card, click the **ⓘ**. Read the popover: the rule, the week, the contributing batches. Press Escape.
9. Hover any table row and click the **ⓘ** by its stage. It names the rule that put the batch in that stage ("Rule R-…"). Press Escape.

**Say**
- "I am playing the laboratory: I approve one sample in the lab system."
- "That is a real event. The pipeline reads the lab, ERP and quality systems, works out every batch's stage again, and publishes the result."
- "The application only ever receives that finished result, and it never writes back to your systems."
- "From my click to this screen took about thirty seconds, and I did not touch the page."
- "The ⓘ shows where a number comes from: the rule, the data run and the batches that make it up. Your auditor can follow it."
- *(SME)* "In your world, how long does it take for an approval to be visible to everyone today?"

**Why it matters to the customer** Trust. A number you can trace to a rule and to source rows is a number the huddle stops arguing about.

**Time** 10 minutes: 4 for the step and its progress, 3 for the sync pages, 3 for the ⓘ popovers.

**If it goes wrong**
- Run is greyed out before you click it: the step already ran. Skip to click 7 and say "I did this earlier".
- The click does nothing: terminal `make scenario STEP=lims-approve-B1042`, then continue at click 5.
- B1042 has not moved after 90 seconds: Demo Controls, **Run the pipeline now** (`run-pipeline`).
- Optional extra if you have time or are asked "can it handle a quality event?": run `open-deviation-B1042` and show the red deviation light on B1042.

## Act 5 · Human judgement (7 min)

**Clicks**
1. Switch the persona back to **Pat · Planner**.
2. On Overview search **B2077**. Point at **Expected Completion: 15 Oct** and the system need-by date, **3 Dec 2026**.
3. Click the pencil in the **Adjusted Need-By** column. The **Adjust Needs-by** window opens.
4. In **New Adjusted Date** type **2026-11-26**. The window shows **−7d (pulled forward)**.
5. Point at **Save**: it is greyed out until you give a reason. Pick **Campaign pulled forward** in **Reason for Change**.
6. Point at **Compressed stage deadlines (preview)**: Sampling 14 Oct 2026, QCL Testing 20 Nov 2026, QA Release 26 Nov 2026. Nothing is saved yet.
7. Click **Save**. The row turns up in italics with the new date and a pencil; **Expected Completion** moves from 15 Oct to **14 Oct**; its colour changes from green to amber and the row sorts up.
8. Click **Audit Log** in the menu. The top entry: Pat changed the need-by of B2077. Click **Show details** to see the old and new values and the reason.

**Say**
- "The campaign moved a week earlier. The planner tells the system, and the system squeezes the time left across the remaining stages."
- "It shows the effect before saving, so nobody saves a date they cannot meet."
- "The ERP date is kept, struck through. The planner's date sits beside it. The two never overwrite each other."
- "Every change is recorded: who, when, old value, new value, reason."
- *(SME)* "Is a week the right size for a pull-forward, and does the compression look realistic to you?"

**Why it matters to the customer** The spreadsheet's biggest weakness is untraceable human input. Here the judgement stays, and the audit trail comes free.

**Time** 7 minutes.

**If it goes wrong**
- The window will not save or the field misbehaves: Demo Controls (as Admin), **Pull B2077 forward by a week (fallback)** (`pull-forward-B2077`), or `make scenario STEP=pull-forward-B2077`. It makes the same edit as Pat. Then go to click 7.
- Its button is greyed out: the edit already exists. Go straight to click 7.

## Act 6 · The agent (8 min)

**Clicks**
1. Switch the persona to **Alex · QA Release Lead**.
2. On Overview click **View all 4 →** on the red **LIMS–SAP Insights** band. The Insights window lists the four batches.
3. Click **Run air-gap agent**. A line says "4 proposals created". Each row now shows **Pending approval**.
4. On the **B5003** row click its proposal link. The proposal opens.
5. Point at the draft summary, then the **Evidence** table: every line is from the lab or ERP, with a **verified ✓**. The times read like "11 Oct 2026 02:00", in site time.
6. Point at the **Validator checklist**: V1 to V6, all passed.
7. Switch the persona to **Pat · Planner**: **Approve** is greyed out. Switch back to **Alex**.
8. Click **Approve**. A ticket and an email appear: "Sent to outbox (demo)", nothing leaves the building.
9. Click **View trace**. Walk down the steps: the question, the tool calls to the lab and the ERP, the model's answers, the validation, the decision, the action.

**Say**
- "An air gap means the lab approved the sample, but the ERP never got the result. Today someone notices late, or not at all."
- "The agent does the legwork a person does: it reads the lab, the ERP and the quality system and drafts a ticket."
- "The agent can only look. It cannot change anything."
- "Its draft goes through fixed checks, not another model. Only then does a person see it, and only a person with the right role can approve."
- "Every step is recorded, so you can show an auditor exactly what it read and why."
- *(SME)* "Is this the evidence your QA lead would ask for before raising the ticket?"

**Why it matters to the customer** It is the answer to "can we trust AI near a release decision?": the agent proposes, rules check, a named person decides, and everything is recorded.

**Time** 8 minutes: 2 to run it, 3 on the proposal and evidence, 1 on approval and roles, 2 on the trace.

**If it goes wrong**
- **Run air-gap agent** fails or says "No recording for key": Demo Controls, **Run the air-gap agent** (`airgap-agent`). Still failing: `docker compose up -d --force-recreate agents`, wait ten seconds, try again.
- Proposals already exist (someone ran it): open B5003's proposal from the **Agents** page in the menu.
- Optional follow-up for questions: after approval, run `ud-post-B5003` to post the usage decision in the ERP: B5003 drops out of the Insights band. `interface-sync-B5003` shows the other way a gap closes (the interface finally delivers the lab results).

## Close (3 min)

**Say**
- "What you saw is one chain: your systems, a governed data product, a live application, audited human input, and agents that only propose."
- "All of it is configured for a site, not coded for it: stages, SLA days, team names and terms come from a site profile."
- "Next we would like to connect it to your data and rerun this with your real batches."

**Time** 3 minutes, then questions.

**Extra moves for questions** `advance-day` moves the clock one day to show ages and late flags growing. `close-deviation-B3150` closes a deviation and frees a batch.

---

# The 12-minute leadership cut

**Draft: SME to confirm.** The selection below is a proposal. The SME should check it against what this
audience cares about before the first use.

| Min | Beat | From the 40-minute script | What to leave out |
|---|---|---|---|
| 1 | The problem | Act 1, only the first two clicks and the three opening sentences | Typing in the cell |
| 3 | Monday morning | Act 2 clicks 1 to 5 and the persona switch (7, 8) | The tags, the metric detail |
| 3 | One approval, end to end | Act 3 clicks 1 to 4, 7 and 8 (the **ⓘ** on M3) | Webhook and Sync Status pages, row ⓘ |
| 4 | The agent | Act 6 clicks 1 to 6, 8 and 9 | The Pat-cannot-approve moment |
| 1 | Close | The three sentences of the close | Questions: offer a follow-up call |

Act 5 (the planner's pull-forward) is left out of the cut. Mention it in one sentence: "planners can move a date and
see the effect before they save; every change is audited."

**Talk-track emphasis for leaders**
- Speed: "from the lab's click to everyone's screen in about thirty seconds".
- Governance: "agents propose, rules check, a named person approves, everything is recorded".
- Scale: "configured per site, not rebuilt per site".

**Recovery moves** are the same as above. In 12 minutes there is no room to retry: if a live step fails, run its
terminal command (`make scenario STEP=<id>`) while you keep talking, and carry on. If the screen is not recoverable
in 30 seconds, switch to the backup video and narrate it.

---

# Questions you may get

| Question | Short answer |
|---|---|
| "Is this connected to our systems?" | Not yet. It reads simulated ERP, lab and quality systems shaped like yours. Connecting is a configuration step per site. |
| "Can the agent change anything?" | No. It reads. It can only write a proposal, an action log and a trace. A person approves, and approval re-checks everything. |
| "Is any of this real data?" | No. It is generated, with a fixed seed, so the demo is the same every time. |
| "What if the update fails?" | Not shown today. Resilience (an automatic safety check that catches a missed update) is next. |
