import asyncio
import aiohttp
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import Config

async def main():
    key = Config.GEMINI_API_KEY.strip()
    print(f"Key loaded: {key[:8]}...")

    async with aiohttp.ClientSession() as session:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        async with session.get(url) as resp:
            print(f"ListModels Status: {resp.status}")
            if resp.status == 200:
                data = await resp.json()
                print("AVAILABLE MODELS FOR GENERATECONTENT:")
                valid_models = []
                for m in data.get("models", []):
                    name = m.get("name", "")
                    methods = m.get("supportedGenerationMethods", [])
                    if "generateContent" in methods:
                        clean_name = name.replace("models/", "")
                        valid_models.append(clean_name)
                        print(f"  - {clean_name}")
                return valid_models
            else:
                text = await resp.text()
                print(f"Error response: {text}")

if __name__ == "__main__":
    asyncio.run(main())
