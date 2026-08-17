import base64
import json
import logging
import re
import aiohttp
from typing import Dict, Any, Optional
from config import Config

logger = logging.getLogger(__name__)

MULTIMODAL_PROMPT = """أنت محقق وخبير أمني متقدم في فحص الأدلة والوسائط (صور، لقطات شاشة، وتسجيلات صوتية) داخل مجتمعات ديسكورد.
مهمتك: فحص هذا الدليل بدقة متناهية لتحديد ما إذا كان يحتوي على:
1. شتائم، سباب، ألفاظ نابية أو بذيئة (Profanity/Insults).
2. تهديدات، تنمر، ابتزاز أو إساءات لفظية مباشرة.
3. انتهاك صريح وفاضح لقوانين المجتمع والآداب العامة.

يجب أن تكون إجابتك بصيغة JSON صحيحة ومباشرة فقط بدون أي نصوص إضافية، وفق هذا الهيكل:
{
  "is_violation": true,
  "confidence": 95,
  "severity": "HIGH",
  "transcription_or_text": "النص المكتشف أو المفرغ من الصورة أو الصوت",
  "violation_details": "شرح دقيق للمخالفة أو الشتيمة المكتشفة",
  "recommendation": "BAN"
}
(خيارات severity هي: "NONE", "LOW", "MEDIUM", "HIGH", "CRITICAL")
(خيارات recommendation هي: "NONE", "WARN", "TIMEOUT", "KICK", "BAN")
إذا لم يكن هناك أي مخالفة أو شتيمة، ضع is_violation=false و confidence=100 و severity="NONE"."""


async def analyze_evidence_multimodal(
    file_bytes: bytes,
    mime_type: str,
    context_text: str = ""
) -> Dict[str, Any]:
    """
    تحليل الأدلة متعددة الوسائط (صور وتسجيلات صوتية) باستخدام نموذج Gemini 1.5 Flash Vision/Audio.
    """
    api_key = (Config.GEMINI_API_KEY or "").strip()
    if not api_key:
        logger.warning("مفتاح Gemini API غير متوفر للتحليل متعدد الوسائط.")
        return {
            "is_violation": False,
            "confidence": 50,
            "severity": "PENDING_WITNESS",
            "transcription_or_text": "مفتاح الذكاء الاصطناعي غير متوفر، يتطلب توثيق شاهدين بشريين.",
            "violation_details": "تم رفع الدليل وبانتظار اعتماد الإدارة أو الشهود.",
            "recommendation": "NONE"
        }

    # تحديد نوع الوسائط المدعومة في Gemini
    normalized_mime = mime_type.lower()
    if "png" in normalized_mime:
        normalized_mime = "image/png"
    elif "jpeg" in normalized_mime or "jpg" in normalized_mime:
        normalized_mime = "image/jpeg"
    elif "webp" in normalized_mime:
        normalized_mime = "image/webp"
    elif "gif" in normalized_mime:
        normalized_mime = "image/gif"
    elif "ogg" in normalized_mime:
        normalized_mime = "audio/ogg"
    elif "mp3" in normalized_mime or "mpeg" in normalized_mime:
        normalized_mime = "audio/mp3"
    elif "wav" in normalized_mime:
        normalized_mime = "audio/wav"
    elif "m4a" in normalized_mime or "aac" in normalized_mime:
        normalized_mime = "audio/mp4"

    b64_data = base64.b64encode(file_bytes).decode("utf-8")

    models_to_try = [
        "gemini-1.5-flash",
        "gemini-2.5-flash",
        "gemini-1.5-flash-latest",
        "gemini-1.5-pro",
        "gemini-2.5-pro",
        "gemini-flash-latest"
    ]

    parts = [
        {
            "inline_data": {
                "mime_type": normalized_mime,
                "data": b64_data
            }
        },
        {
            "text": f"{MULTIMODAL_PROMPT}\n\nسياق الشكوى الإضافي إن وجد:\n{context_text}" if context_text else MULTIMODAL_PROMPT
        }
    ]

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": parts
            }
        ],
        "generationConfig": {
            "temperature": 0.1,
            "responseMimeType": "application/json"
        }
    }

    async with aiohttp.ClientSession() as session:
        for model in models_to_try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
            try:
                async with session.post(url, json=payload, timeout=25) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        candidates = data.get("candidates", [])
                        if candidates:
                            raw_text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                            parsed = _parse_json_result(raw_text)
                            if parsed:
                                return parsed
                    else:
                        err = await resp.text()
                        logger.warning(f"نموذج {model} أرجع ({resp.status}): {err[:120]}")
            except Exception as e:
                logger.warning(f"خطأ أثناء استدعاء {model} لفحص الوسائط: {e}")
                continue

    # في حال تعذر الاتصال بـ API، نعيد نتيجة انتظار
    return {
        "is_violation": False,
        "confidence": 0,
        "severity": "PENDING_WITNESS",
        "transcription_or_text": "تعذر اكتمال التحليل الآلي اللحظي للوسائط.",
        "violation_details": "تم حفظ المرفق بنجاح وبانتظار تأكيد الشهود أو مراجعة المشرف.",
        "recommendation": "NONE"
    }


def _parse_json_result(text: str) -> Optional[Dict[str, Any]]:
    """استخراج وتنظيف كائن JSON من رد الذكاء الاصطناعي."""
    try:
        # إزالة علامات الكود ```json
        clean = re.sub(r"```json\s*", "", text)
        clean = re.sub(r"```\s*$", "", clean).strip()
        return json.loads(clean)
    except Exception:
        # محاولة استخراج أول كائن JSON بالـ Regex
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except Exception:
                pass
    return None
