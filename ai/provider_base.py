from abc import ABC, abstractmethod
from typing import Dict, Any, List

class AIProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, str]], system_prompt: str) -> str:
        """
        يُولّد رداً نصياً من نموذج الذكاء الاصطناعي بناءً على السياق ورسالة النظام.
        """
        pass
