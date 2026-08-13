import aiohttp
import logging
from typing import Dict, Any, List
from ai.provider_base import AIProvider
from config import Config

class OpenRouterProvider(AIProvider):
    def __init__(self):
        self._name = "OpenRouter"

    @property
    def name(self) -> str:
        return self._name

    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        api_key = (Config.OPENROUTER_API_KEY or "").strip()
        model = (Config.OPENROUTER_MODEL or "openrouter/auto").strip()

        if not api_key:
            raise ValueError("مفتاح OpenRouter API غير معرف في ملف .env.")

        url = "https://openrouter.ai/api/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://discord.com",
            "X-Title": "Neon Discord Bot"
        }

        formatted_messages = [{"role": "system", "content": system_prompt}]
        formatted_messages.extend(messages)

        payload = {
            "model": model,
            "messages": formatted_messages,
            "temperature": 0.2
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"خطأ OpenRouter ({resp.status}): {text}")
                data = await resp.json()
                if "choices" in data and len(data["choices"]) > 0:
                    return data["choices"][0]["message"]["content"].strip()
                elif "error" in data:
                    raise RuntimeError(f"خطأ من استجابة OpenRouter: {data['error']}")
                else:
                    raise ValueError(f"استجابة غير متوقعة من OpenRouter: {data}")
