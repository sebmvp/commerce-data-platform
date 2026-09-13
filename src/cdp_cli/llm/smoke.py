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
        "What was the active listing state for j4-military-s two weeks ago?",
        "What do seller notes say about stone-cargo-l?",
    ]
    con = db.connect(read_only=True)
    failed = 0
    try:
        for question in questions:
            print("---")
            print(f"q         {question}")
            try:
                result = run_analyst(con, question=question, provider=provider)
            except Exception as exc:
                failed += 1
                print(f"status    provider_error {type(exc).__name__}: {exc}")
                continue
            print(f"status    {result.get('grounding_status')}")
            print(f"plan      {result.get('plan')}")
            print(f"tools     {[t.get('summary') for t in result.get('tool_trace') or []]}")
            print(f"sufficient {result.get('sufficient')}")
            print(f"citations {result.get('evidence_refs')}")
            print(f"answer    {str(result.get('answer') or '')[:180]}")
    finally:
        con.close()
    print("ai-smoke finished (no business state mutated)")
    if failed:
        print(f"provider errors: {failed}/{len(questions)} (fail-closed; not CI)")
    return 0
