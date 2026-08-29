from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    catalog_database_url: str = "sqlite:////data/catalog.db"
    tenant_database_url: str = "sqlite:////data/tenant.db"
    admin_database_url: str = "sqlite:////data/admin.db"
    evidence_dir: Path = Path("data/evidence")
    index_html_path: Path = Path("index.html")
    static_dir: Path = Path("static")

    # Auth. DEV_MODE skips JWTs and keeps using tenant_database_url so local
    # docker data is not stranded behind an empty admin.db.
    dev_mode: bool = False
    jwt_secret: str = "insecure-dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    demo_token_expire_minutes: int = 120

    # Bibliographic providers. Open Library needs no credentials; Google Books
    # works anonymously but is rate limited far more aggressively without a key.
    google_books_api_key: str | None = None
    provider_timeout_seconds: float = 10.0
    provider_max_results: int = 10

    # SMTP for evaluator portfolio emails. Dummy fallbacks keep the app booting
    # when a host has not configured mail yet; background sends will fail until
    # real credentials are provided.
    mail_username: str = "curiculy"
    mail_password: str = "changeme"
    mail_from: str = "noreply@example.com"
    mail_from_name: str = "Curiculy"
    mail_port: int = 587
    mail_server: str = "localhost"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False

    # Local Ollama for PDF pacing-guide extraction. The API container reaches
    # a host-installed daemon via host.docker.internal (see docker-compose).
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1"


settings = Settings()
