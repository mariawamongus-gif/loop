import logging
from typing import List, Dict, Any
from ai.provider_base import AIProvider
from ai.gemini_provider import GeminiProvider
from ai.openrouter import OpenRouterProvider
from ai.huggingface import HuggingFaceProvider
from core.strings import Strings

class AIFallbackManager:
    def __init__(self):
        self.providers: List[AIProvider] = [
            GeminiProvider(),
            OpenRouterProvider(),
            HuggingFaceProvider()
        ]

    async def generate(self, messages: List[Dict[str, str]], system_prompt: str = Strings.SYSTEM_AI_PROMPT) -> str:
        last_error = None
        for provider in self.providers:
            try:
                logging.info(f"جاري إرسال طلب الذكاء الاصطناعي إلى المزود: {provider.name}")
                response = await provider.generate_response(messages, system_prompt)
                if response:
                    logging.info(f"تم استقبال رد ناجح من المزود: {provider.name}")
                    return response
            except Exception as e:
                logging.error(f"تعذر الاتصال بالمزود {provider.name}: {e}")
                last_error = e
                continue
        
        logging.error("فشلت جميع محاولات الاتصال بمزودي الذكاء الاصطناعي.")
        return "تعذر الاتصال بمزودي الذكاء الاصطناعي حالياً. يرجى مراجعة المفاتيح في ملف .env."

ai_manager = AIFallbackManager()
