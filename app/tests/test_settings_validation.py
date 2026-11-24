import pytest
from fastapi.testclient import TestClient

from app.config.settings import ConfigurationError, settings
from app.main import app


@pytest.mark.parametrize(
    ("groq_api_key", "platform_backend_url", "expected_error"),
    [
        (
            "",
            "https://platform.example.test",
            "GROQ_API_KEY",
        ),
        (
            "test-groq-key",
            "",
            "PLATFORM_BACKEND_URL",
        ),
        (
            "test-groq-key",
            "not-a-url",
            "Invalid configuration: PLATFORM_BACKEND_URL",
        ),
    ],
)
def test_application_startup_rejects_invalid_configuration(
    monkeypatch,
    groq_api_key,
    platform_backend_url,
    expected_error,
):
    monkeypatch.setattr(settings, "GROQ_API_KEY", groq_api_key)
    monkeypatch.setattr(
        settings,
        "PLATFORM_BACKEND_URL",
        platform_backend_url or None,
    )

    with pytest.raises(ConfigurationError, match=expected_error):
        with TestClient(app):
            pass


def test_startup_rejects_non_positive_api_timeout(monkeypatch):
    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-groq-key")
    monkeypatch.setattr(
        settings,
        "PLATFORM_BACKEND_URL",
        "https://platform.example.test",
    )
    monkeypatch.setattr(settings, "API_TIMEOUT", 0)

    with pytest.raises(ConfigurationError, match="API_TIMEOUT"):
        with TestClient(app):
            pass
