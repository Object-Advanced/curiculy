from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# Used only when DEV_MODE is true and JWT_SECRET is unset. Rejected in non-dev.
DEV_ONLY_JWT_SECRET = "insecure-dev-secret"

# HS256 secrets shorter than this are treated as obviously insecure in non-dev.
MIN_JWT_SECRET_LENGTH = 32

# Exact values (compared case-insensitively after strip). Never log these.
_INSECURE_JWT_SECRETS = frozenset(
    {
        DEV_ONLY_JWT_SECRET,
        "change_this_to_a_long_random_string_like_a_password",
        "changeme",
        "secret",
        "password",
        "jwt_secret",
        "your-secret-here",
    }
)

_REDACTED = "***"


class ConfigurationError(RuntimeError):
    """The process cannot start with the current security configuration."""


def reveal_secret(value: str | SecretStr | None) -> str:
    """Return a secret for crypto/SMTP/API use. Never log or raise the result."""
    if value is None:
        return ""
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    return str(value)


def jwt_secret_is_insecure(secret: str) -> bool:
    """True when a JWT signing key is missing, a known placeholder, or too short."""
    stripped = secret.strip()
    if not stripped:
        return True
    if stripped.lower() in _INSECURE_JWT_SECRETS:
        return True
    if len(stripped) < MIN_JWT_SECRET_LENGTH:
        return True
    return False


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    catalog_database_url: str = "sqlite:////data/catalog.db"
    tenant_database_url: str = "sqlite:////data/tenant.db"
    admin_database_url: str = "sqlite:////data/admin.db"
    evidence_dir: Path = Path("data/evidence")
    index_html_path: Path = Path("index.html")
    static_dir: Path = Path("static")

    # Auth. DEV_MODE skips JWTs and keeps using tenant_database_url so local
    # docker data is not stranded behind an empty admin.db. JWT_SECRET is
    # required in non-dev; see validate_runtime_configuration().
    dev_mode: bool = False
    jwt_secret: SecretStr = SecretStr("")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    demo_token_expire_minutes: int = 120
    capture_token_expire_days: int = 365

    # Bibliographic providers. Open Library needs no credentials; Google Books
    # works anonymously but is rate limited far more aggressively without a key.
    google_books_api_key: SecretStr | None = None
    provider_timeout_seconds: float = 10.0
    provider_max_results: int = 10

    # SMTP for evaluator portfolio emails. Username and password come only from
    # the environment; the app still boots without them, and sends fail until
    # they are set.
    mail_username: str = ""
    mail_password: SecretStr = SecretStr("")
    mail_from: str = "noreply@example.com"
    mail_from_name: str = "Curiculy"
    mail_port: int = 587
    mail_server: str = "localhost"
    mail_starttls: bool = True
    mail_ssl_tls: bool = False

    # Zone used for "today" when a household has none stored yet (the SPA
    # stores the parent's browser zone). Unset means the server's own clock.
    default_timezone: str | None = None

    # Local Ollama for PDF pacing-guide extraction. The API container reaches
    # a host-installed daemon via host.docker.internal (see docker-compose).
    ollama_host: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.1"

    def __repr__(self) -> str:
        return (
            f"Settings(dev_mode={self.dev_mode!r}, jwt_secret={_REDACTED}, "
            f"mail_password={_REDACTED}, google_books_api_key={_REDACTED})"
        )

    def __str__(self) -> str:
        return repr(self)

    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        data = super().model_dump(*args, **kwargs)
        redacted = dict(data)
        for key in ("jwt_secret", "mail_password", "google_books_api_key"):
            if key in redacted and redacted[key] not in (None, ""):
                redacted[key] = _REDACTED
        return redacted


def apply_dev_jwt_fallback(config: Settings) -> None:
    """Give DEV_MODE an explicit signing key when JWT_SECRET was left empty."""
    if config.dev_mode and not reveal_secret(config.jwt_secret).strip():
        config.jwt_secret = SecretStr(DEV_ONLY_JWT_SECRET)


def _validate_default_timezone(config: Settings) -> None:
    name = (config.default_timezone or "").strip()
    if not name:
        return
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ConfigurationError(
            "DEFAULT_TIMEZONE must be an IANA time zone such as America/Chicago."
        ) from error


def validate_runtime_configuration(config: Settings | None = None) -> None:
    """Fail closed unless JWT signing is acceptable for this process.

    DEV_MODE may use the explicit development placeholder. Any other process
    must have JWT_SECRET set to a value that is not a known placeholder and is
    at least MIN_JWT_SECRET_LENGTH characters. Error text never includes the
    secret.
    """
    config = settings if config is None else config
    _validate_default_timezone(config)
    if config.dev_mode:
        apply_dev_jwt_fallback(config)
        return

    secret = reveal_secret(config.jwt_secret)
    if not secret.strip():
        raise ConfigurationError(
            "JWT_SECRET is required when DEV_MODE is false. "
            "Set a long random value (at least "
            f"{MIN_JWT_SECRET_LENGTH} characters) in the environment or .env."
        )
    if jwt_secret_is_insecure(secret):
        raise ConfigurationError(
            "JWT_SECRET is too weak for non-development use. "
            "Set a long random value (at least "
            f"{MIN_JWT_SECRET_LENGTH} characters) that is not a known placeholder."
        )


settings = Settings()
