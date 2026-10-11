# How Curiculy works (plain language)

```mermaid
flowchart LR
  subgraph Devices
    P[Parent's phone or laptop<br/>web app]
    K[Kid's tablet<br/>web app, kid look]
    X[Chrome extension<br/>Curiculy Capture]
  end
  CF[Cloudflare<br/>curiculy.com, HTTPS]
  subgraph "Home server (Docker)"
    T[cloudflare_tunnel]
    API[curiculy_api<br/>FastAPI app, port 3040]
    B[curiculy_backup<br/>nightly snapshots]
    O[Ollama<br/>local AI on the GPU]
  end
  subgraph Storage
    DB[(NVMe: ./data<br/>admin.db · catalog.db<br/>tenant_&lt;household&gt;.db)]
    EV[(Data array:<br/>/datalake/.../evidence)]
    BK[(Data array:<br/>/datalake/.../backups)]
  end
  P --> CF
  K --> CF
  X --> CF
  CF --> T --> API
  API --> DB
  API --> EV
  API --> O
  API -. portfolio email .-> M[Mail relay, Brevo]
  B --> DB
  B --> BK
```

## The pieces
- **The web app** is one page: `index.html` with `static/js/app.js` and `static/css/tokens.css` + `app.css`.
  - It works on phones, tablets and computers.
  - It switches to the **kid look** when a child signs in.
  - A small **service worker** (`sw.js`) keeps the app's files on the device so it opens offline. See [Offline](../2-features/16-offline-and-sync.md).
- **The server** (`curiculy_api`) is a Python **FastAPI** app in Docker. It answers every `/api/...` request, about 100 of them (see [API reference](../5-engineering/api-reference.md)), and serves the web app.
- **Data is kept in separate SQLite files:**
  - `admin.db`: sign-ins (parents and kids' PINs), invite keys, family codes, capture tokens, and recent request keys
  - `catalog.db`: a shared cache of book details looked up by ISBN
  - `tenant_<household id>.db`: **one file per family**, holding their kids, lessons, plans, attendance, notes, notifications and so on
  
  One file per family keeps families apart and makes backups and restores simple.
- **Work samples** (photos and PDFs) are files on the big data array, one folder per family. Only paths are stored in the database.
- **AI** runs locally on the home server's GPU through **Ollama**. It's used for "Stuck?" nudges, "Ask Sam", and reading PDF and handwritten lesson plans. Every AI feature has a fallback. See [AI features](../2-features/17-ai-features.md).
- **Backups:** the `curiculy_backup` container snapshots every database nightly, checks each copy, mirrors new work samples, and keeps 14 days. See [Backups](../4-operations/backups-and-restore.md).
- **Public access:** Cloudflare handles HTTPS for **curiculy.com** and forwards traffic through a tunnel to the server's port 3040. The app records each visitor's real address for rate limits and logs.

## A request, start to finish (checking off a lesson)
1. Ada taps the check box on her tablet. The app sends `PATCH /api/assignments/42/status` with her sign-in token and a unique "idempotency key".
2. Cloudflare → tunnel → `curiculy_api`.
3. The server confirms the token, sees she's a child, and checks that lesson 42 is **hers**.
4. It opens her family's `tenant_….db`, sets the status to completed, and saves.
5. The reply comes back. The app shows the celebration and fills in a star.
6. If the internet had dropped, the change would wait on the tablet and be sent once when it returns (see [Offline](../2-features/16-offline-and-sync.md)).

## Where things live (folders)
| Folder | What it is |
|---|---|
| `/home/objadv/curiculy` | **Production.** The running app's files, on the local branch `production`. Changes here reach families immediately, so don't edit it by hand. |
| `/home/objadv/curiculy-dev` | **Development copy** (a git worktree). All work happens here. |
| `/home/objadv/curiculy-ops` | The scheduled **log check** script and its reports |
| `/datalake/projects/curiculy/evidence` | Work-sample files |
| `/datalake/projects/curiculy/backups` | Nightly snapshots |
| GitHub `Object-Advanced/curiculy` | The code; pull requests; tests run on every push |

More detail: [Production and deploys](../4-operations/production.md), [Codebase map](../5-engineering/codebase-map.md).
