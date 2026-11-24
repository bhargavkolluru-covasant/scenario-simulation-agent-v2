from math import isfinite
from typing import Dict, Optional
from urllib.parse import urlparse

from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class ConfigurationError(RuntimeError):
    """Raised when required application configuration is missing or invalid."""


_URL_SETTING_NAMES = (
    "PLATFORM_BACKEND_URL",
    "DASHBOARD_URL",
    "KPI_INSIGHTS_URL",
    "ACTIONS_URL",
    "SEMANTIC_REGISTRY_URL",
    "KNOWLEDGE_GRAPH_URL",
    "RULES_SERVICE_URL",
    "RULE_COMPILATION_URL",
    "VENDOR_SERVICE_URL",
    "PROCUREMENT_SERVICE_URL",
    "INVOICE_SERVICE_URL",
    "EXPENSE_SERVICE_URL",
    "MARKET_RISK_SERVICE_URL",
)


class Settings(BaseSettings):

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore"
    )

    # ==================================================
    # Core
    # ==================================================

    API_TIMEOUT: float = 30.0

    PLATFORM_BACKEND_URL: Optional[str] = None

    # ==================================================
    # Dashboard / KPI Intelligence
    # ==================================================

    DASHBOARD_URL: Optional[str] = None

    KPI_INSIGHTS_URL: Optional[str] = None

    ACTIONS_URL: Optional[str] = None

    DASHBOARD_ID: Optional[str] = None

    # ==================================================
    # Context
    # ==================================================

    ARIIA_ENTERPRISE_ID: Optional[str] = None

    ARIIA_DOMAIN_IDS: str = ""

    ARIIA_COOKIE: Optional[str] = None

    ARIIA_SESSION_ID: Optional[str] = None

    # ==================================================
    # Platform Clients
    # ==================================================

    SEMANTIC_REGISTRY_URL: Optional[str] = None

    KNOWLEDGE_GRAPH_URL: Optional[str] = None

    RULES_SERVICE_URL: Optional[str] = None

    RULE_COMPILATION_URL: Optional[str] = None

    VENDOR_SERVICE_URL: Optional[str] = None

    PROCUREMENT_SERVICE_URL: Optional[str] = None

    INVOICE_SERVICE_URL: Optional[str] = None

    EXPENSE_SERVICE_URL: Optional[str] = None

    MARKET_RISK_SERVICE_URL: Optional[str] = None

    # ==================================================
    # Authentication
    # ==================================================

    ARIIA_ACCESS_TOKEN: Optional[str] = None

    ARIIA_SCOPE_ID: Optional[str] = None

    ARIIA_SCOPE_HEADER_NAME: str = (
        "X-Scope-Id"
    )

    # ==================================================
    # LLM
    # ==================================================

    GROQ_API_KEY: Optional[str] = None

    GROQ_MODEL: str = (
        "openai/gpt-oss-120b"
    )

    # ==================================================
    # Properties
    # ==================================================

    def validate_startup(self) -> None:
        missing = []
        if not self.GROQ_API_KEY or not self.GROQ_API_KEY.strip():
            missing.append("GROQ_API_KEY")
        if not self.PLATFORM_BACKEND_URL or not self.PLATFORM_BACKEND_URL.strip():
            missing.append("PLATFORM_BACKEND_URL")

        if missing:
            names = ", ".join(missing)
            raise ConfigurationError(
                f"Missing required configuration: {names}. "
                "Set these values in .env or the process environment."
            )

        invalid_urls = []
        for name in _URL_SETTING_NAMES:
            value = getattr(self, name)
            if value and not self._is_http_url(value):
                invalid_urls.append(name)

        if invalid_urls:
            names = ", ".join(invalid_urls)
            raise ConfigurationError(
                "Invalid configuration: "
                f"{names} must be absolute HTTP(S) URLs."
            )

        if not isfinite(self.API_TIMEOUT) or self.API_TIMEOUT <= 0:
            raise ConfigurationError(
                "Invalid configuration: API_TIMEOUT must be a positive number."
            )

        if not self.GROQ_MODEL.strip():
            raise ConfigurationError(
                "Invalid configuration: GROQ_MODEL must not be empty."
            )

    @staticmethod
    def _is_http_url(value: str) -> bool:
        parsed = urlparse(value.strip())
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or any(character.isspace() for character in parsed.netloc)
        ):
            return False
        try:
            parsed.port
        except ValueError:
            return False
        return True

    @property
    def access_token(self):
        return self.ARIIA_ACCESS_TOKEN

    @property
    def scope_id(self):
        return self.ARIIA_SCOPE_ID

    @property
    def enterprise_id(self):
        return self.ARIIA_ENTERPRISE_ID or ""

    @property
    def domain_ids(self) -> list[str]:
        """Resolve the configured domain identifiers as a normalized list."""
        domain_ids = [
            domain.strip()
            for domain in self.ARIIA_DOMAIN_IDS.split(",")
            if domain.strip()
        ]
        return domain_ids

    @property
    def platform_headers(
        self
    ) -> Dict[str, str]:

        headers = {}

        if self.enterprise_id:

            headers[
                "X-Enterprise-Id"
            ] = self.enterprise_id

        if self.domain_ids:

            headers[
                "X-Domain-Id"
            ] = ",".join(self.domain_ids)

        return headers

    def get_service_url(
        self,
        override: Optional[str] = None
    ) -> str:
        service_url = override or self.PLATFORM_BACKEND_URL
        if not service_url:
            raise ConfigurationError(
                "PLATFORM_BACKEND_URL is required to resolve service URLs."
            )
        return service_url.rstrip("/")


settings = Settings()