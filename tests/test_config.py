"""Runtime security configuration: JWT fail-closed and env-driven SMTP."""

import pytest

from app.config import (
    DEV_ONLY_JWT_SECRET,
    MIN_JWT_SECRET_LENGTH,
    ConfigurationError,
    Settings,
    apply_dev_jwt_fallback,
    jwt_secret_is_insecure,
    reveal_secret,
    settings,
    validate_runtime_configuration,
)
from app.main import create_app, lifespan
from app.services.portfolio import mail_connection

# Historical compose default. Must be rejected in non-dev even though it is long.
_COMPOSE_JWT_PLACEHOLDER = "change_this_to_a_long_random_string_like_a_password"

_STRONG_JWT = "n" * MIN_JWT_SECRET_LENGTH
_REPR_PROBE = "unique-leak-probe-value-32chars!!"
_WEAK_PROBE = "leak-probe-short"


def _isolated_settings(**kwargs: object) -> Settings:
    values = {
        "dev_mode": False,
        "jwt_secret": "",
        "mail_username": "",
        "mail_password": "",
        "google_books_api_key": None,
    }
    values.update(kwargs)
    return Settings(_env_file=None, **values)


def test_dev_mode_allows_missing_jwt_secret_and_applies_explicit_fallback() -> None:
    config = _isolated_settings(dev_mode=True, jwt_secret="")
    validate_runtime_configuration(config)
    assert reveal_secret(config.jwt_secret) == DEV_ONLY_JWT_SECRET


def test_dev_mode_allows_insecure_placeholder() -> None:
    config = _isolated_settings(dev_mode=True, jwt_secret=DEV_ONLY_JWT_SECRET)
    validate_runtime_configuration(config)
    assert reveal_secret(config.jwt_secret) == DEV_ONLY_JWT_SECRET


def test_dev_mode_keeps_an_explicit_secret() -> None:
    config = _isolated_settings(dev_mode=True, jwt_secret=_STRONG_JWT)
    validate_runtime_configuration(config)
    assert reveal_secret(config.jwt_secret) == _STRONG_JWT


def test_production_rejects_missing_jwt_secret() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret="")
    with pytest.raises(ConfigurationError, match="JWT_SECRET is required") as caught:
        validate_runtime_configuration(config)
    assert _WEAK_PROBE not in str(caught.value)


def test_production_rejects_whitespace_jwt_secret() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret="   ")
    with pytest.raises(ConfigurationError, match="JWT_SECRET is required"):
        validate_runtime_configuration(config)


def test_production_rejects_dev_placeholder() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret=DEV_ONLY_JWT_SECRET)
    with pytest.raises(ConfigurationError, match="too weak") as caught:
        validate_runtime_configuration(config)
    assert DEV_ONLY_JWT_SECRET not in str(caught.value)
    assert DEV_ONLY_JWT_SECRET not in repr(caught.value)


def test_production_rejects_compose_placeholder() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret=_COMPOSE_JWT_PLACEHOLDER)
    with pytest.raises(ConfigurationError, match="too weak") as caught:
        validate_runtime_configuration(config)
    assert _COMPOSE_JWT_PLACEHOLDER not in str(caught.value)


def test_production_rejects_short_secret() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret="short-secret")
    with pytest.raises(ConfigurationError, match="too weak"):
        validate_runtime_configuration(config)


def test_production_accepts_a_long_random_secret() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret=_STRONG_JWT)
    validate_runtime_configuration(config)


def test_jwt_secret_is_insecure_detects_placeholders_and_short_values() -> None:
    assert jwt_secret_is_insecure("")
    assert jwt_secret_is_insecure("   ")
    assert jwt_secret_is_insecure(DEV_ONLY_JWT_SECRET)
    assert jwt_secret_is_insecure(_COMPOSE_JWT_PLACEHOLDER)
    assert jwt_secret_is_insecure("changeme")
    assert jwt_secret_is_insecure("secret")
    assert not jwt_secret_is_insecure(_STRONG_JWT)


def test_configuration_error_does_not_include_secret_value() -> None:
    config = _isolated_settings(dev_mode=False, jwt_secret=_WEAK_PROBE)
    with pytest.raises(ConfigurationError) as caught:
        validate_runtime_configuration(config)
    message = str(caught.value)
    assert "JWT_SECRET" in message
    assert _WEAK_PROBE not in message
    assert _WEAK_PROBE not in repr(caught.value)


def test_settings_repr_does_not_include_secrets() -> None:
    config = _isolated_settings(
        jwt_secret=_REPR_PROBE,
        mail_password=_REPR_PROBE,
        google_books_api_key=_REPR_PROBE,
    )
    text = repr(config)
    assert _REPR_PROBE not in text
    assert str(config) == text
    dumped = config.model_dump()
    for value in dumped.values():
        assert _REPR_PROBE not in str(value)


def test_reveal_secret_handles_plain_strings_and_empty() -> None:
    assert reveal_secret(None) == ""
    assert reveal_secret("") == ""
    assert reveal_secret("plain") == "plain"


def test_apply_dev_jwt_fallback_is_noop_when_secret_present() -> None:
    config = _isolated_settings(dev_mode=True, jwt_secret=_STRONG_JWT)
    apply_dev_jwt_fallback(config)
    assert reveal_secret(config.jwt_secret) == _STRONG_JWT


def test_mail_connection_uses_settings_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mail_username", "smtp-user")
    monkeypatch.setattr(settings, "mail_password", "smtp-configured-password")
    monkeypatch.setattr(settings, "mail_from", "from@example.com")
    monkeypatch.setattr(settings, "mail_server", "smtp.example.com")
    cfg = mail_connection()
    assert cfg.MAIL_USERNAME == "smtp-user"
    assert cfg.MAIL_SERVER == "smtp.example.com"
    assert reveal_secret(cfg.MAIL_PASSWORD) == reveal_secret(settings.mail_password)
    assert cfg.USE_CREDENTIALS is True
    assert reveal_secret(cfg.MAIL_PASSWORD) != "changeme"


def test_mail_connection_does_not_invent_dummy_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "mail_username", "")
    monkeypatch.setattr(settings, "mail_password", "")
    cfg = mail_connection()
    assert cfg.MAIL_USERNAME == ""
    assert reveal_secret(cfg.MAIL_PASSWORD) == ""
    assert reveal_secret(cfg.MAIL_PASSWORD) != "changeme"
    assert cfg.MAIL_USERNAME != "curiculy"
    assert cfg.USE_CREDENTIALS is False


@pytest.mark.asyncio
async def test_lifespan_rejects_insecure_jwt_in_non_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "dev_mode", False)
    monkeypatch.setattr(settings, "jwt_secret", DEV_ONLY_JWT_SECRET)
    app = create_app()
    with pytest.raises(ConfigurationError, match="too weak") as caught:
        async with lifespan(app):
            pass
    assert DEV_ONLY_JWT_SECRET not in str(caught.value)


@pytest.mark.asyncio
async def test_lifespan_allows_dev_mode_without_jwt_secret(
    monkeypatch: pytest.MonkeyPatch, tmp_path,
) -> None:
    monkeypatch.setattr(settings, "dev_mode", True)
    monkeypatch.setattr(settings, "jwt_secret", "")
    monkeypatch.setattr(settings, "evidence_dir", tmp_path / "evidence")
    app = create_app()
    async with lifespan(app):
        pass
    assert reveal_secret(settings.jwt_secret) == DEV_ONLY_JWT_SECRET
