"""Optional real-provider smoke. Never runs in CI. Never mutates state."""
from __future__ import annotations

from .gateway import load_model_config
from .providers import OpenAICompatibleProvider


def main() -> int:
    try:
        config = load_model_config()
    except ValueError as exc:
        print(f"config error: {exc}")
        return 1
    if config.provider == "fake":
        print(
            "refusing: FakeProvider is not a smoke target.\n"
            "Set CDP_MODEL_PROVIDER=openai_compatible and CDP_MODEL_BASE_URL / "
            "CDP_MODEL_NAME. Local endpoints do not need an API key.\n"
            "Do not run this against a paid API without explicit approval."
        )
        return 1
    if config.kind == "remote" and not config.api_key:
        print(
            "refusing: remote provider has no API key. "
            "A consumer Grok subscription is not API access."
        )
        return 1
    print(f"provider  {config.provider}")
    print(f"kind      {config.kind}")
    print(f"model     {config.model}")
    print(f"base_url  {config.base_url}")
    print(f"auth      {'yes' if config.api_key else 'no'}")
    from .. import db
    from .analyst import run_analyst

    if not db.is_initialized():
        print("schema not initialized — run: make seed")
        return 1
    provider = OpenAICompatibleProvider(config)
    questions = [
        "Should I reprice j4-military-s?",
        "Should I reprice stone-cargo-l?",
        "What should I focus on today?",
    ]
    con = db.connect(read_only=True)
    try:
        for question in questions:
            result = run_analyst(con, question=question, provider=provider)
            print("---")
            print(f"q         {question}")
            print(f"status    {result.get('grounding_status')}")
            print(f"plan      {result.get('plan')}")
            print(f"tools     {[t.get('summary') for t in result.get('tool_trace') or []]}")
            print(f"answer    {str(result.get('answer') or '')[:240]}")
    except Exception as exc:
        print(f"smoke failed: {type(exc).__name__}: {exc}")
        return 1
    finally:
        con.close()
    print("ai-smoke ok (no business state mutated)")
    return 0
