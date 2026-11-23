
import asyncio
from src.llm.orchestrator import LLMOrchestrator


async def main():
    engine = LLMOrchestrator(timeout=80)

    sample_text = """
    OpenAI is an artificial intelligence research and
    deployment company.

    ChatGPT is an AI assistant developed by OpenAI.

    Anthropic is an AI safety and research company.
    """

    print("=" * 50)
    print("FRONTIERATLAS LLM FALLBACK TEST")
    print("=" * 50)

    providers = engine.available_providers()

    print("Configured providers:")
    for provider in providers:
        print("-", provider["name"])

    if not providers:
        print("No API credentials configured.")
        return

    try:
        result = await engine.extract(sample_text)

        print("\n" + "=" * 50)
        print("EXTRACTION SUCCESSFUL")
        print("=" * 50)

        print("Chunks processed:", result["chunks_processed"])
        print("Records extracted:", len(result["records"]))

        for record in result["records"]:
            print(record)

    except Exception as error:
        print("\n" + "=" * 50)
        print("ALL CONFIGURED PROVIDERS FAILED")
        print("=" * 50)
        print(type(error).__name__, error)


if __name__ == "__main__":
    asyncio.run(main())
