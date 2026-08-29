# Curiculy
Curiculy is a local-first, multi-child homeschool planner designed to run on a single family node. It handles curriculum pacing, family calendars, work-sample evidence (via Chrome extension), and printable portfolios.

## 1. Configuration (`.env`)
Before starting the application, you must configure your environment secrets. Copy the example file:
`cp .env.example .env`

Edit `.env` and provide a strong `JWT_SECRET`. **The application will refuse to start in production mode if this is missing, weak, or set to a known placeholder.**

Optional configurations:
* `MAIL_USERNAME` / `MAIL_PASSWORD`: Required only if you want to email evaluator PDFs. (Do not commit these).
* `OLLAMA_HOST`: Required only if you are using background AI PDF parsing or the homework-help tutor.

## 2. Starting the Application
Curiculy runs via Docker Compose.
`docker compose up -d`
The UI will be available at `http://localhost:3040`. *(Note: Code directories are bind-mounted. Evidence files and databases are stored in the `./data` directory on the host).*

## 3. Bootstrapping the First Admin
Because registration is invite-gated, you need to manually generate the first invite key directly in the admin database to create your initial parent account.
1. Exec into the container: `docker compose exec api bash`
2. Open the admin database: `sqlite3 /data/admin.db`
3. Insert an invite key: `INSERT INTO invite_keys (key, expires_at) VALUES ('YOUR_HEX_KEY', datetime('now', '+1 day'));`
4. Go to `http://localhost:3040`, click **Register**, and use your new invite key.

## 4. Development Mode
Run tests using the dev profile:
`docker compose --profile dev run --rm tests pytest`
