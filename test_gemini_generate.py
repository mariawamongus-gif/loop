import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ai.gemini_provider import GeminiProvider

async def test_generation():
    provider = GeminiProvider()
    print(f"Testing {provider.name} generation...")
    res = await provider.generate_response(
        messages=[{"role": "user", "content": "مرحباً، هل تعمل بنجاح؟"}],
        system_prompt="أنت مساعد آلي ذكي وبسيط."
    )
    print("\n--- GEMINI RESPONSE SUCCESS ---")
    print(res)
    print("--------------------------------")

if __name__ == "__main__":
    asyncio.run(test_generation())
