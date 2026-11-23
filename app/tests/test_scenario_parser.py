import pytest

from app.models.scenario_models import ParsedScenario
from app.services.scenario_parser_service import (
    CLARIFICATION_MESSAGE,
    ScenarioClarificationError,
    ScenarioParserService,
)


class StructuredParser:
    is_configured = True

    def __init__(self, response):
        self.response = response
        self.prompt = ""
        self.schema = None

    async def generate_json(self, *, prompt, system_instruction, schema):
        self.prompt = prompt
        self.schema = schema
        return self.response


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("query", "response"),
    [
        (
            "Revenue increases by 20%",
            {
                "scenario_type": "revenue_change",
                "target_entity": "Revenue",
                "change_type": "increase",
                "change_percentage": 20,
                "time_horizon": "unspecified",
            },
        ),
        (
            "Development costs decrease by 10%",
            {
                "scenario_type": "cost_change",
                "target_entity": "Development costs",
                "change_type": "decrease",
                "change_percentage": 10,
                "time_horizon": "unspecified",
            },
        ),
        (
            "Occupancy increases by 12%",
            {
                "scenario_type": "occupancy_change",
                "target_entity": "Occupancy",
                "change_type": "increase",
                "change_percentage": 12,
                "time_horizon": "unspecified",
            },
        ),
        (
            "Cash inflows remain 20% below forecast",
            {
                "scenario_type": "cash_flow_change",
                "target_entity": "Cash inflows",
                "change_type": "decrease",
                "change_percentage": 20,
                "time_horizon": "unspecified",
            },
        ),
        (
            "Construction costs rise by 15% next quarter",
            {
                "scenario_type": "cost_change",
                "target_entity": "Construction costs",
                "change_type": "increase",
                "change_percentage": 15,
                "time_horizon": "next quarter",
            },
        ),
    ],
)
async def test_structured_scenario_examples_parse_without_heuristic_fallback(
    query,
    response,
):
    parser_llm = StructuredParser(response)
    scenario = await ScenarioParserService(llm_service=parser_llm).parse(query)

    assert parser_llm.schema is ParsedScenario
    assert scenario["scenario_type"] == response["scenario_type"]
    assert scenario["target_entity"] == response["target_entity"]
    assert scenario["change_type"] == response["change_type"]
    assert scenario["change_percentage"] == response["change_percentage"]
    assert scenario["time_horizon"] == response["time_horizon"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "query",
    [
        "follow up on vendor invoices",
        "follow up on procurement approvals",
        "review project status",
        "check cash flow",
    ],
)
async def test_ambiguous_requests_return_clarification(query):
    response = {
        "scenario_type": "financial_change",
        "target_entity": "Invoices",
        "change_type": "increase",
        "time_horizon": "unspecified",
    }

    with pytest.raises(
        ScenarioClarificationError,
        match="I couldn't understand the business change being requested",
    ) as exc_info:
        await ScenarioParserService(
            llm_service=StructuredParser(response)
        ).parse(query)

    assert str(exc_info.value) == CLARIFICATION_MESSAGE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "missing_field",
    [
        "scenario_type",
        "target_entity",
        "change_type",
        "change_percentage",
        "time_horizon",
    ],
)
async def test_each_required_field_is_validated(missing_field):
    response = {
        "scenario_type": "revenue_change",
        "target_entity": "Revenue",
        "change_type": "increase",
        "change_percentage": 20,
        "time_horizon": "unspecified",
    }
    response.pop(missing_field)

    with pytest.raises(ScenarioClarificationError) as exc_info:
        await ScenarioParserService(
            llm_service=StructuredParser(response)
        ).parse("Revenue increases by 20%")

    assert str(exc_info.value) == CLARIFICATION_MESSAGE


@pytest.mark.asyncio
async def test_unconfigured_structured_parser_does_not_use_a_heuristic_fallback():
    class UnconfiguredParser:
        is_configured = False

    with pytest.raises(ScenarioClarificationError) as exc_info:
        await ScenarioParserService(llm_service=UnconfiguredParser()).parse(
            "Construction costs rise by 15% next quarter"
        )

    assert str(exc_info.value) == CLARIFICATION_MESSAGE


@pytest.mark.parametrize(
    "invalid_response",
    [
        {
            "scenario_type": "enterprise_scenario",
            "target_entity": "Revenue",
            "change_type": "increase",
            "change_percentage": 20,
            "time_horizon": "unspecified",
        },
        {
            "scenario_type": "revenue_change",
            "target_entity": "Unknown Entity",
            "change_type": "increase",
            "change_percentage": 20,
            "time_horizon": "unspecified",
        },
        {
            "scenario_type": "revenue_change",
            "target_entity": "Revenue",
            "change_type": "scenario_change",
            "change_percentage": 20,
            "time_horizon": "unspecified",
        },
        {
            "scenario_type": "revenue_change",
            "target_entity": "Revenue",
            "change_type": "increase",
            "change_percentage": 0,
            "time_horizon": "unspecified",
        },
    ],
)
def test_pydantic_rejects_placeholder_and_zero_change_values(invalid_response):
    with pytest.raises(ValueError):
        ParsedScenario.model_validate(invalid_response)
