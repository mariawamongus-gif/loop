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
        api_key = (Config.GEMINI_API_KEY or "").strip()
        if not api_key:
            raise RuntimeError("مفتاح Google AI Studio API Key غير متوفر.")

        configured_model = (Config.GEMINI_MODEL or "gemini-2.5-flash").strip()
        models_to_try = [
            configured_model,
            "gemini-2.5-flash",
            "gemini-flash-latest",
            "gemini-2.5-pro",
            "gemini-pro-latest",
            "gemini-2.5-flash-lite"
        ]
        
        seen = set()
        model_candidates = [m for m in models_to_try if not (m in seen or seen.add(m))]

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

        last_error = None
        async with aiohttp.ClientSession() as session:
            for model_name in model_candidates:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
                try:
                    async with session.post(url, json=payload, timeout=20) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    return parts[0].get("text", "")
                        
                        error_text = await resp.text()
                        logger.warning(f"نموذج {model_name} أرجع ({resp.status}): {error_text[:120]}")
                        last_error = f"Status {resp.status}"
                except Exception as e:
                    logger.warning(f"خطأ أثناء طلب {model_name}: {e}")
                    last_error = str(e)
                    continue

        raise RuntimeError(f"فشلت كافة نماذج Gemini المتاحة ({last_error})")
