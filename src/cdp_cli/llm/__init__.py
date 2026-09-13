"""Grounded LLM path over ContextBundle.

Fake provider is the default (tests, no keys). A real provider is only
used when CDP_MODEL_PROVIDER=openai_compatible (API key optional for
local endpoints). The model never sees the whole business, never writes,
and never emits SQL.

Grounding fails closed: malformed output, missing citations, unknown refs,
or invalid suggested actions are not trusted answers.
"""
from .analyst import MAX_ITERATIONS, registered_tools, run_analyst
from .gateway import (
    ModelCapabilities,
    ModelConfig,
    ModelGateway,
    get_provider,
    load_model_config,
)
from .grounding import (
    GroundedModelOutput,
    SuggestedActionModel,
    ground_answer,
    ground_from_bundle,
    parse_grounded,
)
from .planner import deterministic_plan, plan_question
from .providers import (
    FakeProvider,
    OpenAICompatibleProvider,
    ScriptedProvider,
)

__all__ = [
    "MAX_ITERATIONS",
    "FakeProvider",
    "GroundedModelOutput",
    "ModelCapabilities",
    "ModelConfig",
    "ModelGateway",
    "OpenAICompatibleProvider",
    "ScriptedProvider",
    "SuggestedActionModel",
    "deterministic_plan",
    "get_provider",
    "ground_answer",
    "ground_from_bundle",
    "load_model_config",
    "parse_grounded",
    "plan_question",
    "registered_tools",
    "run_analyst",
]
