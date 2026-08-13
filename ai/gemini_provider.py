import aiohttp
import logging
from typing import Dict, Any, List
from ai.provider_base import AIProvider
from config import Config

logger = logging.getLogger(__name__)

class GeminiProvider(AIProvider):
    @property
    def name(self) -> str:
        return "Google AI Studio (Gemini)"

    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        if not Config.GEMINI_API_KEY:
            raise RuntimeError("مفتاح Google AI Studio API Key غير متوفر.")

        model = Config.GEMINI_MODEL or "gemini-1.5-flash"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={Config.GEMINI_API_KEY}"

        # تحويل صيغة الرسائل لـ Gemini Format (user -> user, assistant -> model)
        contents = []
        for msg in messages:
            role = "user" if msg.get("role") == "user" else "model"
            content = msg.get("content", "")
            if content:
                contents.append({
                    "role": role,
                    "parts": [{"text": content}]
                })

        payload = {
            "contents": contents
        }

        if system_prompt:
            payload["system_instruction"] = {
                "parts": [{"text": system_prompt}]
            }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=20) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    try:
                        candidates = data.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            if parts:
                                return parts[0].get("text", "")
                    except Exception as e:
                        logger.error(f"خطأ أثناء قراءة استجابة Gemini: {e}")
                        raise RuntimeError(f"استجابة غير متوقعة من Gemini: {e}")

                error_text = await resp.text()
                logger.error(f"فشل طلب Google AI Studio ({resp.status}): {error_text}")
                raise RuntimeError(f"خطأ Google AI Studio API Status {resp.status}")
