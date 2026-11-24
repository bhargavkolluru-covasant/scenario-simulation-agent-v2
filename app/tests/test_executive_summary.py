import pytest

from app.services.explainability_service import (
    ExplainabilityService,
    _build_executive_prompt,
)
from app.services.report_service import ReportService


@pytest.mark.asyncio
async def test_report_summary_replaces_kpi_listing_with_executive_narrative():
    legacy_style_output = (
        "The most important indicator is NPS Trend. "
        "Review Rating also matters because review scores are falling. "
        "Sentiment Alerts also matters because negative feedback is increasing."
    )
    report = await ReportService().generate_report({
        "query": "Customer satisfaction declined by 12% over the past quarter.",
        "scenario": {
            "description": "Customer satisfaction declined by 12% over the past quarter.",
            "target_entity": "Retailer North",
        },
        "primary_kpi": {
            "name": "NPS Trend",
            "why_it_matters": (
                "NPS Trend matters because customer loyalty is weakening."
            ),
        },
        "supporting_kpis": [{
            "name": "Review Rating",
            "why_it_matters": "Review Rating matters because review scores are falling.",
        }],
        "primary_risk": {
            "name": "Sentiment Alerts",
            "business_impact": (
                "NPS Trend matters because declining customer loyalty may reduce "
                "repeat business."
            ),
            "reason": "Negative feedback is becoming more frequent.",
        },
        "selected_actions": [{
            "title": "Protect customer retention",
            "action": (
                "Review service recovery priorities and address recurring issues."
            ),
            "expected_outcome": (
                "Stabilize satisfaction and reduce churn risk."
            ),
        }],
    })

    summary = report["executive_summary"]
    assert summary != legacy_style_output
    assert "Business Situation:" in summary
    assert "Business Impact:" in summary
    assert "Primary Risk: Sentiment Alerts" in summary
    assert "Leadership Action:" in summary
    assert len(summary.split("\n\n")) == 3
    assert len(summary.split()) <= 100
    assert "declining customer loyalty" in summary.casefold()
    assert "repeat business" in summary.casefold()
    assert "NPS Trend" not in summary
    assert "Review Rating" not in summary
    assert "most important indicator" not in summary.casefold()
    assert "also matters because" not in summary.casefold()


def test_executive_prompt_requires_three_paragraph_business_narrative():
    prompt = _build_executive_prompt({
        "top_kpis": [
            {"name": "NPS Trend"},
            {"name": "Review Rating"},
        ],
        "top_risks": [{"title": "Sentiment Alerts"}],
        "top_actions": [{"title": "Protect customer retention"}],
    })

    assert "Business Situation:" in prompt
    assert "Business Impact:" in prompt
    assert "Primary Risk:" in prompt
    assert "Leadership Action:" in prompt
    assert "Use KPI evidence internally" in prompt
    assert "Do not enumerate KPIs" in prompt
    assert "no more than three paragraphs" in prompt


@pytest.mark.asyncio
async def test_unconfigured_explainability_fallback_uses_executive_structure():
    class UnconfiguredLLM:
        is_configured = False

    explanation = await ExplainabilityService(
        llm_service=UnconfiguredLLM(),
    ).explain({
        "query": "Customer satisfaction declined over the past quarter.",
        "scenario": {
            "description": "Customer satisfaction declined over the past quarter.",
        },
        "primary_kpi": {"name": "NPS Trend"},
        "supporting_kpis": [{"name": "Review Rating"}],
        "primary_risk": {
            "name": "Sentiment Alerts",
            "business_impact": (
                "NPS Trend matters because customer loyalty is weakening."
            ),
        },
        "selected_actions": [{
            "title": "Review NPS Trend and customer comments",
        }],
        "impact_result": {
            "overall_severity": "HIGH",
            "causal_analysis": {
                "business_consequence": (
                    "NPS Trend matters because customer loyalty is weakening."
                ),
            },
        },
        "simulation_result": {"metrics": {}},
    })

    summary = explanation["executive_summary"]
    assert "Business Situation:" in summary
    assert "Business Impact:" in summary
    assert "Primary Risk: Sentiment Alerts" in summary
    assert "Leadership Action:" in summary
    assert len(summary.split("\n\n")) == 3
    assert len(summary.split()) <= 100
    assert "NPS Trend" not in summary
    assert "Review Rating" not in summary
