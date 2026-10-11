# State requirements

How each state's homeschool law becomes a **requirement pack** in Curiculy, without forcing anything to fit. Part of the [Product spine](../product-spine.md). Agreed **2026-10-11**.

**Not legal advice.** Packs help families keep records. The law and the family's school district have the final word, and every pack links to its sources.

## The rule: no square pegs
When a state requirement asks for something Curiculy doesn't have, we **don't force it into the nearest existing field or rule type**. We stop, review it with the owner, and decide one of three things:
- **a correct mapping** to data Curiculy really has
- **a new feature** that collects what's needed
- **handled outside Curiculy:** the parent does it, and Curiculy reminds them and stores the proof

Curiculy never shows a ✓ for something it can't actually check.

## The process for each state
1. **The worksheet comes first, then the code.** Create `<state>.md` in this folder with one row per requirement:
   - the requirement in plain words
   - its source (the statute section, the state agency's guidance, an HSLDA link)
   - what Curiculy has today
   - a **status** (below), judged against the planned design in the [Product spine](../product-spine.md)
   - notes and, once reviewed, the decision
2. **Open questions go at the top.** Every row marked "Partly covered" or "Needs a decision" adds a question.
3. **The owner reviews.** Each question gets a decision: a mapping, a new feature, or outside Curiculy. Decisions are written in the worksheet and in [Decisions](../decisions.md).
4. **Only reviewed rows become rules.** A new rule type is added on purpose, never bent from an existing one.
5. **Re-check yearly.** Laws change. Each pack shows the date it was last reviewed.

## Row statuses
| Status | Means |
|---|---|
| **Covered** | Curiculy's data proves it. The row names the exact source, e.g. "attendance: days marked present ≥ 180". |
| **Partly covered** | Some data exists; the gap is written down. |
| **Needs a decision** | No honest mapping yet. It's on the open-questions list. |
| **Outside Curiculy** | The parent does it (signing, notarizing, mailing, testing). Curiculy can only remind and store the proof. |

## How a requirement looks in the app (Records)
| State | Means | Example |
|---|---|---|
| **✓ Shown by your records** | Worked out from the family's data | "Ada: 181 of 180 days" |
| **Parent confirms** | A checklist item for anything outside Curiculy or not yet mapped: a checkbox and a date, plus an upload only where it's safe | "Affidavit filed July 28" (no upload); "Evaluator's letter" (upload) |
| **Missing** | Not done yet, with a link straight to the fix | "Q2 science: 1 of 2 samples. Attach to a lesson" |

## Private details: never stored
A requirement that needs sensitive personal information (health or immunization records, birth dates, addresses, criminal-history certifications) is **never stored**. Instead:
- **Forms are fillable PDFs:** what Curiculy knows is filled in, and private details are left blank for the parent to type, e-sign (DocuSign or similar) or ink. Nothing typed into the blanks is saved.
- **The checklist shows a checkbox and a date,** with no upload, for anything sensitive.
- **"Your state" explains where to get each record.**

See [Privacy](../product-spine.md#privacy-keep-the-minimum).

## Where families read the rules
- **Records → Your state:** the rules in plain words, with sources, the date last reviewed, and the official forms
- a **Why?** link on each checklist line, setup step and calendar warning
- a **public page per state** on the website

Settings holds only the family's choices: their state, and their evaluator adjustments.

## Sources
- **Prefer primary sources:** the statute and the state education department's own guidance.
- **Link to [HSLDA](https://hslda.org/legal)** for each state, but don't copy its text (it's their copyrighted summary).
- Quote the statute where wording matters, and mark anything not yet checked against the statute as **to confirm**.

## Hard states alone, easy states together
- **States with demanding laws get their own pack, one at a time:** Pennsylvania, then New York, and so on.
- **States with similar, light laws share a base pack,** and each state adds only its differences.
- **Every state still gets a worksheet and a review.** For a state that matches a base pack, the worksheet is short: it lists the base, then only what differs.

## States
| State | Worksheet | Status |
|---|---|---|
| Pennsylvania | [pennsylvania.md](pennsylvania.md) | Reviewed 2026-10-11 (Q1–Q14 decided); a few wordings to confirm against the statute |
| New York | (not started) | Likely next: its yearly plan (IHIP) and quarterly reports can be generated from courses |
