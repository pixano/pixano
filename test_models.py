import asyncio
from src.pixano.inference.providers.openai import LiteLLMProvider

async def main():
    try:
        provider = LiteLLMProvider(url="http://deeptalk2.intra.cea.fr:4000", api_key="sk-w8Qqp_V_zlX8plaI393ytw")
        models = await provider.list_models()
        print("MODELS:")
        for m in models:
            print(m)
    except Exception as e:
        print("ERROR:")
        print(e)

if __name__ == "__main__":
    asyncio.run(main())
