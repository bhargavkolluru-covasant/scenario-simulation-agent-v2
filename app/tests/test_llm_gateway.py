import logging

import pytest

from app.config.settings import settings
from app.services import llm_gateway
from app.services.llm_gateway import LLMGateway


@pytest.mark.asyncio
@pytest.mark.integration
async def test_llm_gateway_live_returns_json():
    if not settings.GROQ_API_KEY:
        pytest.skip("GROQ_API_KEY is not configured.")

    result = await LLMGateway().generate_json(
        'Return JSON {"status":"ok"}',
        system_instruction="Return only a JSON object with status set to ok.",
    )

    assert result.get("status") == "ok"


@pytest.mark.asyncio
async def test_llm_gateway_uses_groq(monkeypatch):
    class FakeGroq:
        is_configured = True

        async def generate_json(self, prompt):
            assert prompt == 'Return JSON {"status":"ok"}'
            return {"status": "ok"}

    monkeypatch.setattr(llm_gateway, "GroqService", FakeGroq)

    result = await LLMGateway().generate_json('Return JSON {"status":"ok"}')

    assert result == {"status": "ok"}


@pytest.mark.asyncio
async def test_llm_gateway_does_not_fall_back_when_groq_fails(monkeypatch):
    calls = []

    class FailingGroq:
        is_configured = True

        async def generate_text(self, prompt):
            assert prompt == "Say hello"
            calls.append("groq")
            raise RuntimeError("Groq unavailable")

    monkeypatch.setattr(llm_gateway, "GroqService", FailingGroq)
    gateway = LLMGateway()

    with pytest.raises(RuntimeError, match="Groq unavailable"):
        await gateway.generate_text("Say hello")

    assert calls == ["groq"]


def test_health_and_startup_report_groq(caplog):
    from fastapi.testclient import TestClient

    from app.main import app

    caplog.set_level(logging.INFO)
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["primary_llm_provider"] == "GROQ"
    assert "Primary LLM Provider: GROQ" in caplog.text
