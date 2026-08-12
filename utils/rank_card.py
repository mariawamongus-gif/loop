from PIL import Image, ImageDraw, ImageFont, ImageFilter
import io
import aiohttp
import os

async def generate_rank_card(username: str, avatar_url: str, level: int, xp: int, xp_needed: int, rank_position: int) -> io.BytesIO:
    """
    يولّد بطاقة مستوى PNG فائقة الاحترافية بتصميم Cyberpunk / Neon Dark.
    """
    width, height = 900, 300
    # خلفية داكنة مع تدرج أنيق
    card = Image.new("RGBA", (width, height), (15, 15, 23, 255))
    draw = ImageDraw.Draw(card)

    # رسم خلفية شبكة سايبر خفيفة (Cyber Grid)
    grid_color = (30, 30, 48, 255)
    for x in range(0, width, 30):
        draw.line([(x, 0), (x, height)], fill=grid_color, width=1)
    for y in range(0, height, 30):
        draw.line([(0, y), (width, y)], fill=grid_color, width=1)

    # رسم إطار غلاسي داكن داخلي
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=18, fill=(24, 24, 37, 230), outline=(0, 245, 255, 200), width=2)

    # تحميل صورة الأفاتار من الرابط
    avatar_image = None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(avatar_url) as resp:
                if resp.status == 200:
                    avatar_bytes = await resp.read()
                    avatar_image = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
    except Exception:
        pass

    if not avatar_image:
        avatar_image = Image.new("RGBA", (140, 140), (0, 245, 255, 255))

    avatar_size = (140, 140)
    avatar_image = avatar_image.resize(avatar_size, Image.Resampling.LANCZOS)

    # قص الأفاتار بشكل دائري
    mask = Image.new("L", avatar_size, 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0) + avatar_size, fill=255)

    # رسم هالة مضيئة نيون حول الأفاتار
    draw.ellipse([45, 75, 195, 225], outline=(0, 245, 255, 255), width=4)
    card.paste(avatar_image, (50, 80), mask)

    # كتابة النصوص (الاسم، المستوى، الخبرة، الترتيب)
    # استخدام الخط الافتراضي
    font_large = ImageFont.load_default()

    # الاسم
    draw.text((220, 75), f"USER: {username}", fill=(255, 255, 255, 255), font=font_large)

    # الترتيب والمستوى
    draw.text((220, 110), f"RANK: #{rank_position}  |  LEVEL: {level}", fill=(0, 245, 255, 255), font=font_large)

    # شريط التقدم (Progress Bar)
    bar_x, bar_y, bar_w, bar_h = 220, 175, 620, 26
    progress = min(xp / max(xp_needed, 1), 1.0)
    fill_w = int(bar_w * progress)

    # خلفية الشريط
    draw.rounded_rectangle([bar_x, bar_y, bar_x + bar_w, bar_y + bar_h], radius=13, fill=(35, 35, 55, 255))
    # الجزء الممتلئ النيون
    if fill_w > 0:
        draw.rounded_rectangle([bar_x, bar_y, bar_x + fill_w, bar_y + bar_h], radius=13, fill=(0, 245, 255, 255))

    # نص الخبرة فوق الشريط
    draw.text((bar_x + 10, bar_y + 6), f"XP: {xp} / {xp_needed} ({int(progress * 100)}%)", fill=(15, 15, 23, 255), font=font_large)

    buffer = io.BytesIO()
    card.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer
