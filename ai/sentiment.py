import logging
from typing import Dict
from ai.fallback_manager import ai_manager

logger = logging.getLogger(__name__)

async def analyze_ticket_sentiment(text: str) -> Dict[str, str]:
    """
    يقوم بتقييم نبرة المحادثة ومدى الاستعجال في التذكرة باستخدام الذكاء الاصطناعي.
    المرجع: { "sentiment": "ANGRY/FRUSTRATED/NEUTRAL/CALM", "urgency": "EMERGENCY/HIGH/MEDIUM/LOW" }
    """
    sys_prompt = (
        "أنت وحدة Neon AI لتحليل المشاعر ونبرة التذاكر. "
        "قم بتحليل النص المرفق وأجب بصيغة دقيقة مكونة من سطرين فقط:\n"
        "SENTIMENT: ANGRY أو FRUSTRATED أو NEUTRAL أو CALM\n"
        "URGENCY: EMERGENCY أو HIGH أو MEDIUM أو LOW"
    )

    try:
        response = await ai_manager.generate(
            messages=[{"role": "user", "content": text}],
            system_prompt=sys_prompt
        )

        sentiment = "NEUTRAL"
        urgency = "MEDIUM"

        for line in response.splitlines():
            line_upper = line.upper().strip()
            if line_upper.startswith("SENTIMENT:"):
                sentiment = line_upper.split(":", 1)[1].strip()
            elif line_upper.startswith("URGENCY:"):
                urgency = line_upper.split(":", 1)[1].strip()

        return {"sentiment": sentiment, "urgency": urgency}
    except Exception as e:
        logger.error(f"خطأ أثناء تحليل نبرة التذكرة: {e}")
        return {"sentiment": "NEUTRAL", "urgency": "MEDIUM"}
