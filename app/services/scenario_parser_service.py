import logging
from typing import Any, Dict, Optional

from app.models.scenario_models import ParsedScenario
from app.services.llm_gateway import LLMGateway

logger = logging.getLogger(__name__)

CLARIFICATION_MESSAGE = (
    "I couldn't understand the business change being requested. "
    "Please rephrase the scenario."
)


class ScenarioClarificationError(ValueError):
    """Raised when the query cannot be converted to a complete scenario."""


class ScenarioParserService:
    """
    Enterprise-grade Scenario Parser Service using the configured LLM provider.
    Transforms free-form natural language queries into strictly typed, validated simulation scenarios.
    """

    def __init__(self, llm_service: Optional[LLMGateway] = None):
        self.llm_service = llm_service or LLMGateway.get_service()

    async def parse(self, user_query: str) -> Dict[str, Any]:
        """
        Parse a natural language business query into a structured simulation scenario.
        Enforces Pydantic validation against ParsedScenario.
        """
        clean_query = user_query.strip() if user_query else ""
        if not clean_query:
            raise ScenarioClarificationError(CLARIFICATION_MESSAGE)

        logger.info("[ScenarioParserService] Parsing simulation query")
        if not self.llm_service.is_configured:
            logger.warning(
                "[ScenarioParserService] Structured parser is not configured."
            )
            raise ScenarioClarificationError(CLARIFICATION_MESSAGE)

        system_instruction = (
            "You extract explicit business changes into structured fields. "
            "Do not infer, guess, or supply fallback values. If a required field "
            "cannot be extracted, omit that field so the request can be clarified. "
            "Never use zero, unknown, or generic placeholders for missing information. "
            "Return only a JSON object."
        )

        prompt = f"""
Extract a structured business scenario from the user query.

User Query:
"{clean_query}"

Required fields:
{{
  "scenario_type": "a concise category grounded in the described change",
  "target_entity": "the subject explicitly named in the query",
  "change_type": "increase or decrease, normalized from the business meaning",
  "change_percentage": "positive numeric magnitude explicitly stated as a percentage",
  "time_horizon": "the explicit time horizon, or 'unspecified' when none is stated"
}}

Treat phrases such as "follow up" as an action, not an increase. Interpret
"below forecast" as a decrease only when paired with an explicit percentage.
Do not derive percentages from qualitative wording. If the query does not state
a measurable business change, omit the missing required fields instead of
guessing them.
"""

        try:
            scenario_data = await self.llm_service.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                schema=ParsedScenario,
            )
            scenario = ParsedScenario.model_validate(scenario_data)
        except Exception as exc:
            logger.error(
                "[ScenarioParserService] Structured parsing failed validation.",
                exc_info=True,
            )
            raise ScenarioClarificationError(CLARIFICATION_MESSAGE) from exc

        logger.info(
            "[ScenarioParserService] Structured scenario parsed: type=%s entity=%s",
            scenario.scenario_type,
            scenario.target_entity,
        )
        return scenario.model_dump()