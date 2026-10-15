# Curiculy frontend (React)

The new Curiculy app: Vite + React 19 + TypeScript (strict), Tailwind v4 on the shared design tokens, TanStack Query, and a typed API client generated from the server's OpenAPI description. It's served by FastAPI under **`/next`** while screens move over from the legacy app (`index.html` + `static/js/app.js`) one at a time.

**Screens:**
- **Kids:** **My trail** (`/next/trail`) and the **Sticker journal** (`/next/journal`). See `docs/2-features/19-my-trail.md` and `20-sticker-journal.md`.
- **Parents** ("Morning Light", inside `ParentShell`): the **Library** (`/next/library`), the **Curriculum planner** (`/next/planner`), **Reading lists** (`/next/reading`), **Activities** (`/next/activities`), **Attendance** (`/next/attendance`), and, for admins, **Catalog review** (`/next/admin/catalog`). See `docs/2-features/21-library.md`, `22-curriculum-planner.md`, `23-community-catalog.md`, `24-reading-lists.md`, `25-activities.md` and `12-attendance.md`.

## Layout
```
frontend/
├── index.html            The page; loads /static/js/theme-boot.js (shared) then src/main.tsx
├── vite.config.ts        base "/next/", React + Tailwind plugins, Vitest config, dev proxy to :3040
├── openapi.json          The API description the client is typed from (checked by pytest)
└── src/
    ├── main.tsx          QueryClient + router
    ├── router.tsx        Routes (basename /next); RequireSession sends signed-out people to /
    ├── app.css           Tailwind + ../../static/css/tokens.css + component styles (tokens only)
    ├── parent.css        The parent screens' styles (tokens only)
    ├── api/              client.ts (openapi-fetch + sign-in), queries.ts and parent.ts (TanStack Query), images.ts (signed-in images), schema.d.ts (generated)
    ├── lib/              Pure logic: dates, the daily puzzle (ported from app.js), stickers, map layout, pasted chapters and lessons, cover colors
    ├── components/       Kid: TrailMap (SVG), StopList, StickerPanel, BonusChest, KidHeader, CampBanner, StickerIcon
    │                     Parent: ParentShell, ui/ (Modal, Fields, Checklist), library/, planner/, reading/, activities/, attendance/
    ├── routes/           TrailPage, JournalPage, LibraryPage, PlannerPage, NewCurriculumPage, CurriculumPage, ReadingPage, ActivitiesPage, AttendancePage, CatalogReviewPage, NotFound
    └── test/             Vitest setup and the MSW server
```

## Commands
No Node on the server? Run everything through Docker from the repository root, mounted so `../static` resolves:
```
docker run --rm -u "$(id -u):$(id -g)" -e HOME=/tmp -v "$PWD":/repo -w /repo/frontend node:22.23.2-alpine sh -c 'npm ci && npm test'
```

| Task | Command (inside `frontend/`) |
|---|---|
| Install | `npm ci` |
| Dev server (proxies `/api` and `/static` to a local Curiculy on :3040) | `npm run dev`, then open `http://localhost:5173/next/trail` |
| Type check | `npm run typecheck` |
| Unit and component tests (Vitest, Testing Library, MSW) | `npm test` |
| Production build → `dist/` | `npm run build` |

**Regenerate the API types after an API change.**
1. Write `openapi.json` from the server code:
   ```
   docker compose --profile dev run --rm -T tests python -c "import json,os; os.environ.setdefault('JWT_SECRET','x'*48); from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > frontend/openapi.json
   ```
2. Regenerate the types: `npm run gen:api`.

`tests/test_next_app.py` fails if `openapi.json` is stale, and CI fails if `schema.d.ts` doesn't match it.

## How it fits with the legacy app
- **Sign-in:** still the legacy page. The React app reads the same token (`localStorage["auth_token"]`) until cookie sessions land; with no token it sends you to `/`.
- **Look:**
  - The same `tokens.css`, bundled at build time.
  - The same fonts from `/static/fonts`, loaded at runtime.
  - The same `theme-boot.js` for dark mode and the kid look.
- **Build:** the Dockerfile's `frontend` stage runs `npm ci && npm run build`, and the Python image copies `dist/` to `/app/frontend/dist`.
- **Serving:** FastAPI serves `dist/index.html` for every `/next/...` URL. Hashed files under `/next/assets/` are cached for a year.
- **Pinned versions:** exact versions (see `package.json`), each released at least two weeks before it was added. Upgrade deliberately, one major version at a time.

## Conventions
- **Kid screens guide; they don't teach.** Point to the family's own materials; fun is optional.
- **Colors and sizes come from tokens only.** No raw hex values in `app.css` or components.
- **Every screen passes the axe scan** (`e2e/a11y-baseline.json`), with large touch targets (at least 44 px) on kid screens.
- **Parent screens explain themselves.** Every step says what it's for in plain words, every required field says why, and nothing is saved without a preview when it changes the calendar.
- **Keep logic pure and tested** (`src/lib`). Components get Testing Library tests against MSW.
