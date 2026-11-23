from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, field_validator


class ParsedScenario(BaseModel):
    """
    Structured representation of a natural language simulation request.
    Validates scenario dimensions, target entities, disruption metrics, and domains.
    """
    scenario_type: str = Field(
        ...,
        min_length=1,
        description="High-level scenario category, expressed in terms relevant to the user's domain",
    )
    target_entity: str = Field(
        ...,
        min_length=1,
        description="Name or identifier of any entity, process, asset, group, or other subject in the scenario",
    )
    change_type: str = Field(
        ...,
        min_length=1,
        description="Nature of the change or event described by the user",
    )
    change_percentage: float = Field(
        ...,
        gt=0,
        description="Explicit positive magnitude of the business change in percent",
    )
    time_horizon: str = Field(
        ...,
        min_length=1,
        description="Temporal scope or duration described by the user",
    )
    domain: str = Field(
        default="unspecified",
        description="Business domain described by the user, without restricting it to a predefined set",
    )
    description: Optional[str] = Field(
        default=None,
        description="Detailed description or context of the simulation scenario",
    )
    parameters: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional structured parameters extracted from the query",
    )

    @field_validator("scenario_type", "target_entity", "change_type", "time_horizon")
    @classmethod
    def require_nonempty_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field must not be empty.")
        return value

    @field_validator("scenario_type", "target_entity", "change_type")
    @classmethod
    def reject_placeholder_text(cls, value: str, info) -> str:
        placeholders = {
            "scenario_type": {"enterprise_scenario", "unknown", "unspecified"},
            "target_entity": {"unknown", "unknown entity", "unspecified"},
            "change_type": {"scenario_change", "unknown", "unspecified"},
        }
        if value.casefold() in placeholders.get(info.field_name, set()):
            raise ValueError(f"{info.field_name} must be extracted from the query.")
        return value
