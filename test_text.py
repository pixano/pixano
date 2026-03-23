import asyncio
from src.pixano.inference.types import VLMInput
from src.pixano.inference.providers.openai import LiteLLMProvider

async def main():
    try:
        provider = LiteLLMProvider(url="http://deeptalk2.intra.cea.fr:4000", api_key="sk-w8Qqp_V_zlX8plaI393ytw")
        input_data = VLMInput(
            model="qwen3-vl:8b",
            prompt="Hello, are you there?",
            max_new_tokens=100,
            temperature=0.7
        )
        result = await provider.vlm(input_data)
        print("RESULT:")
        print(result)
    except Exception as e:
        print("ERROR:")
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
