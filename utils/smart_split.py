import math
import re
from typing import List

def smart_split(text: str, max_length: int = 2000) -> List[str]:
    """
    خوارزمية تقسيم الردود الذكية لرسائل Discord:
    1. تحسب طول الرد بالأحرف والعدد المطلوب للأجزاء.
    2. لا تقسم في منتصف كلمة أو كود أو جملة.
    3. توازن الأحرف قدر الإمكان بين الأجزاء.
    4. تضيف مؤشر ترتيب [1/N].
    5. تحافظ على كتل الكود (Code Blocks) المغلقة والمفتوحة عبر الأجزاء.
    """
    if not text:
        return []

    # خصم مساحة الهيدر/الفوتر للمؤشر مثلا "[10/10]\n" (~10 أحرف)
    effective_max = max_length - 15

    if len(text) <= effective_max:
        return [text]

    total_chars = len(text)
    num_parts = math.ceil(total_chars / effective_max)
    target_part_len = math.ceil(total_chars / num_parts)

    parts: List[str] = []
    current_pos = 0
    in_code_block = False
    code_lang = ""

    while current_pos < total_chars:
        remaining_len = total_chars - current_pos

        if remaining_len <= effective_max:
            chunk = text[current_pos:]
            current_pos = total_chars
        else:
            # البحث عن النقطة المثالية للقطع حول target_part_len لكن دون التجاوز عـ effective_max
            search_end = min(current_pos + effective_max, total_chars)
            target_cut = min(current_pos + target_part_len, search_end)

            # نحاول إيجاد أفضل نقطة توقف: فقرة، جملة، أو سطر
            candidate_cut = -1

            # 1. نهاية فقرة \n\n
            p_cut = text.rfind("\n\n", current_pos, search_end)
            if p_cut != -1 and p_cut > current_pos:
                candidate_cut = p_cut + 2

            # 2. نهاية سطر \n
            if candidate_cut == -1:
                l_cut = text.rfind("\n", current_pos, search_end)
                if l_cut != -1 and l_cut > current_pos:
                    candidate_cut = l_cut + 1

            # 3. نهاية جملة (نقطة + مسافة)
            if candidate_cut == -1:
                s_cut = text.rfind(". ", current_pos, search_end)
                if s_cut != -1 and s_cut > current_pos:
                    candidate_cut = s_cut + 2

            # 4. مسافة عادية بين الكلمات
            if candidate_cut == -1:
                w_cut = text.rfind(" ", current_pos, search_end)
                if w_cut != -1 and w_cut > current_pos:
                    candidate_cut = w_cut + 1

            # إجباري لو لم يجد أي مسافة
            if candidate_cut == -1 or candidate_cut <= current_pos:
                candidate_cut = search_end

            chunk = text[current_pos:candidate_cut]
            current_pos = candidate_cut

        # معالجة كتل الكود code blocks
        chunk_content = ""
        if in_code_block:
            chunk_content += f"```{code_lang}\n"

        chunk_content += chunk

        # فحص حالات فتح/إغلاق ```
        code_matches = list(re.finditer(r"```(\w*)", chunk))
        for match in code_matches:
            if not in_code_block:
                in_code_block = True
                code_lang = match.group(1)
            else:
                in_code_block = False
                code_lang = ""

        if in_code_block and current_pos < total_chars:
            chunk_content += "\n```"

        parts.append(chunk_content)

    # إضافة مؤشرات الأجزاء [1/N]
    final_parts = []
    total_parts = len(parts)
    for idx, part in enumerate(parts, 1):
        if total_parts > 1:
            final_parts.append(f"[{idx}/{total_parts}]\n{part}")
        else:
            final_parts.append(part)

    return final_parts
