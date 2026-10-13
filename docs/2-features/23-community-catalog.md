# Community catalog and review

The structure of every book, textbook, workbook, online site and curriculum families enter: shared with every family after an admin reviews it. Nothing about any family is shared.

| | |
|---|---|
| **Who uses it** | Parents (through Library search and the planner's suggestions); admins (the review queue) |
| **Where** | Inside the [Library](21-library.md) and the [Curriculum planner](22-curriculum-planner.md); admins: `/next/admin/catalog`, from **Catalog review** in the nav and the user menu |
| **Health** | **Works** (new in October 2026) |

## Scope

### What families see
- **In the catalog: ready to use** results come first in Library search, with how many families entered each.
- Each library item shows its place in the catalog, in plain words:
  - "Shared with the Curiculy catalog. An admin reviews it before other families see it."
  - "In the Curiculy catalog, used by 4 families."
  - "Shared once it's ready to schedule."
- **Other families built a similar curriculum** in the planner.
- **Notifications** when a review finishes: thanks, the reason it wasn't added, or the admin's question. Opening one goes to the Library.

### The review queue (admins)
- **Waiting for review / Everything / Catalog entries.**
- **Each contribution shows:**
  - its flags, "check" ones first, each with a group, where it was found, and the reason
  - the contributor as a stable label ("Family 3f9a2c"), with how many of their contributions were accepted or rejected
  - for a correction or a likely duplicate, the catalog entry it changes or repeats, and a table of what's different
  - what the book lookup says about the ISBN
  - the uploaded cover
  - the details, chapters and lesson list
- **Decisions:**
  - **Approve**, optionally tidying the title or name and leaving the cover out
  - **Merge into the existing entry**, optionally taking these details as its new version
  - **Reject**, with a reason the family sees
  - **Ask the family**, whose next edit brings it back
- **Catalog entries:** search, versions with **Go back to this** (a rollback adds a new version), and **Retire** (hide from search) or show again.

### Rules
See [Product spine: Community catalog](../6-planning/product-spine.md#community-catalog-built-by-every-family). Contributions are automatic, and only once an item is ready to schedule. The automatic checks are in `app/services/community_checks.py`; the actions in `app/services/community_review.py`.

### Code
- `frontend/src/routes/CatalogReviewPage.tsx`
- Server: `app/routers/community.py`, `app/routers/community_admin.py`, `app/services/community*.py`, `app/models/community.py`

## Review (October 2026)
**Works well:** every contribution is reviewed with its reasons laid out; families never wait on the catalog for their own copy.

**Gaps:**
- face detection on covers
- trusted contributors publishing without review
- catch-up feedback in the queue
- founding-family discounts (billing)
- the lawyer's read of the notice wording

**Tests:** `frontend/src/routes/CatalogReviewPage.test.tsx`, `tests/test_community.py`, and the planner's community-curriculum tests in `tests/test_planner.py`.
