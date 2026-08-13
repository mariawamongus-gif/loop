import asyncio
import aiohttp
from config import Config

async def test_gemini():
    api_key = (Config.GEMINI_API_KEY or "").strip()
    print(f"Testing Gemini API Key: {api_key[:10]}...")

    models = [
        ("v1beta", "gemini-2.5-flash"),
        ("v1beta", "gemini-2.0-flash-001"),
        ("v1beta", "gemini-1.5-flash-8b"),
        ("v1", "gemini-1.5-flash"),
        ("v1", "gemini-1.5-pro"),
        ("v1beta", "gemini-2.5-pro"),
        ("v1beta", "gemini-1.5-pro-latest"),
    ]

    payload = {
        "contents": [{"role": "user", "parts": [{"text": "Hello, respond with OK"}]}]
    }

    async with aiohttp.ClientSession() as session:
        # First list available models
        list_url = f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}"
        async with session.get(list_url) as resp:
            print(f"\nListModels Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print("Available models in your API key quota:")
                for m in data.get("models", []):
                    name = m.get("name")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        print(f" - {name}")
            else:
                text = await resp.text()
                print(f"ListModels error: {text[:200]}")

        # Test specific models
        for ver, mod in models:
            url = f"https://generativelanguage.googleapis.com/v1/{ver}/models/{mod}:generateContent?key={api_key}" if ver == "v1" else f"https://generativelanguage.googleapis.com/v1beta/models/{mod}:generateContent?key={api_key}"
            async with session.post(url, json=payload) as resp:
                print(f"Model [{ver} / {mod}] -> Status {resp.status}")
                if resp.status == 200:
                    data = await resp.json()
                    print(f" SUCCESS! Response: {data}")
                    return

if __name__ == "__main__":
    asyncio.run(test_gemini())
