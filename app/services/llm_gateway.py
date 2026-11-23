from typing import Any

from app.services.groq_service import GroqService


class LLMGateway:
    """Groq-only LLM facade used by application services."""

    def __init__(self) -> None:
        self._groq_service = GroqService()

    @property
    def is_configured(self) -> bool:
        return self._groq_service.is_configured

    async def _invoke(self, method: str, *args: Any, **kwargs: Any) -> Any:
        if not self.is_configured:
            raise RuntimeError("GROQ_API_KEY is not configured.")
        return await getattr(self._groq_service, method)(*args, **kwargs)

    async def generate_text(self, *args: Any, **kwargs: Any) -> str:
        return await self._invoke("generate_text", *args, **kwargs)

    async def generate_json(self, *args: Any, **kwargs: Any) -> Any:
        return await self._invoke("generate_json", *args, **kwargs)

    async def ainvoke(self, *args: Any, **kwargs: Any) -> Any:
        return await self._invoke("ainvoke", *args, **kwargs)

    @staticmethod
    def get_service() -> "LLMGateway":
        return LLMGateway()


GatewayService = LLMGateway
