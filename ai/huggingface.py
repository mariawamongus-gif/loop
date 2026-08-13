import aiohttp
import logging
from typing import Dict, Any, List
from ai.provider_base import AIProvider
from config import Config

class HuggingFaceProvider(AIProvider):
    def __init__(self):
        self._name = "HuggingFace"

    @property
    def name(self) -> str:
        return self._name

    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        api_key = (Config.HUGGINGFACE_API_KEY or "").strip()
        model = (Config.HUGGINGFACE_MODEL or "mistralai/Mistral-7B-Instruct-v0.2").strip()

        if not api_key:
            raise ValueError("مفتاح HuggingFace API غير معرف في ملف .env.")

        url = f"https://api-inference.huggingface.co/models/{model}"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        prompt_text = f"System: {system_prompt}\n"
        for m in messages:
            prompt_text += f"{m['role'].capitalize()}: {m['content']}\n"
        prompt_text += "Assistant:"

        payload = {
            "inputs": prompt_text,
            "parameters": {
                "max_new_tokens": 500,
                "temperature": 0.2,
                "return_full_text": False
            }
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    raise RuntimeError(f"خطأ HuggingFace ({resp.status}): {text}")
                data = await resp.json()
                if isinstance(data, list) and len(data) > 0 and "generated_text" in data[0]:
                    return data[0]["generated_text"].strip()
                elif isinstance(data, dict) and "generated_text" in data:
                    return data["generated_text"].strip()
                else:
                    raise ValueError(f"استجابة غير متوقعة من HuggingFace: {data}")
