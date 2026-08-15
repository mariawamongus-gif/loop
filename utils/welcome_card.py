import io
import os
import aiohttp
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps


def _get_font(name: str, size: int):
    """جلب خطوط فاخرة مع دعم كامل لأنظمة Windows و Linux/Docker."""
    font_paths = [
        f"C:/Windows/Fonts/{name}.ttf",
        f"C:/Windows/Fonts/{name.lower()}.ttf",
        "C:/Windows/Fonts/georgiab.ttf",
        "C:/Windows/Fonts/georgia.ttf",
        "C:/Windows/Fonts/timesbd.ttf",
        "C:/Windows/Fonts/times.ttf",
        "C:/Windows/Fonts/segoeuib.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ]
    for p in font_paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


async def generate_welcome_card(
    username: str,
    avatar_url: str,
    server_name: str,
    member_count: int
) -> io.BytesIO:
    """
    توليد بطاقة ترحيب فائقة الفخامة بخطوط كبيرة وبارزة جداً ونمط الرخام المنقوش بشعار TS.
    """
    base_width, base_height = 1376, 768

    bg_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "welcome_bg_ts.jpg")
    if os.path.exists(bg_path):
        try:
            card = Image.open(bg_path).convert("RGBA")
            card = card.resize((base_width, base_height), Image.Resampling.LANCZOS)
        except Exception:
            card = _create_fallback_plaque(base_width, base_height)
    else:
        card = _create_fallback_plaque(base_width, base_height)

    draw = ImageDraw.Draw(card)

    # ─── 1. فتح وتثبيت صورة الأفاتار في المكان المخصص ────────────────────────
    avatar_center = (262, 384)
    avatar_radius = 115
    avatar_size = avatar_radius * 2

    avatar_image = None
    if avatar_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(avatar_url) as resp:
                    if resp.status == 200:
                        avatar_bytes = await resp.read()
                        avatar_image = Image.open(io.BytesIO(avatar_bytes)).convert("RGBA")
        except Exception:
            pass

    if not avatar_image:
        avatar_image = Image.new("RGBA", (avatar_size, avatar_size), (70, 70, 80, 255))

    avatar_image = avatar_image.resize((avatar_size, avatar_size), Image.Resampling.LANCZOS)

    # قناع دائري ناعم
    mask = Image.new("L", (avatar_size, avatar_size), 0)
    mask_draw = ImageDraw.Draw(mask)
    mask_draw.ellipse((0, 0, avatar_size, avatar_size), fill=255)

    x1 = avatar_center[0] - avatar_radius
    y1 = avatar_center[1] - avatar_radius

    # دمج الأفاتار
    card.paste(avatar_image, (x1, y1), mask)

    # رسم إطار معدني مشطوف حول دائرة الأفاتار
    draw.ellipse([x1 - 6, y1 - 6, x1 + avatar_size + 6, y1 + avatar_size + 6], outline=(255, 255, 255, 230), width=4)
    draw.ellipse([x1 - 2, y1 - 2, x1 + avatar_size + 2, y1 + avatar_size + 2], outline=(25, 25, 30, 255), width=4)

    # ─── 2. الخطوط الكبيرة والنصوص المحفورة ثلاثية الأبعاد ─────────────────────
    font_welcome = _get_font("georgiab", 52)
    font_server = _get_font("georgiab", 70)
    font_user = _get_font("segoeuib", 58)
    font_count = _get_font("georgiab", 42)

    def draw_engraved(pos, text, font, fill=(30, 30, 35, 255)):
        """رسم نص رخامي منقوش بظل ثلاثي الأبعاد بارز جداً."""
        tx, ty = pos
        # الظل الفاتح السفلي لإبراز النحت
        draw.text((tx + 3, ty + 3), text, fill=(255, 255, 255, 210), font=font)
        # الظل الداكن العلوي للعمق
        draw.text((tx - 2, ty - 2), text, fill=(10, 10, 15, 150), font=font)
        # اللون الأساسي
        draw.text((tx, ty), text, fill=fill, font=font)

    text_x = 430
    text_y = 160

    # سطر WELCOME TO
    draw_engraved((text_x, text_y), "WELCOME TO", font_welcome, (70, 70, 80, 255))

    # سطر اسم السيرفر
    display_server = server_name.strip().upper()
    if len(display_server) > 16:
        display_server = display_server[:14] + "..."
    draw_engraved((text_x, text_y + 68), display_server, font_server, (15, 15, 20, 255))

    # خط فاصل معدني بارز
    line_y = text_y + 175
    draw.line([(text_x, line_y), (text_x + 460, line_y)], fill=(140, 140, 150, 240), width=3)
    draw.line([(text_x, line_y + 3), (text_x + 460, line_y + 3)], fill=(255, 255, 255, 240), width=3)

    # سطر اسم العضو
    display_user = username.strip()
    if len(display_user) > 16:
        display_user = display_user[:14] + "..."
    draw_engraved((text_x, text_y + 200), f"@{display_user}", font_user, (25, 25, 35, 255))

    # سطر رقم العضو
    draw_engraved((text_x, text_y + 285), f"MEMBER #{member_count}", font_count, (80, 80, 90, 255))

    buffer = io.BytesIO()
    card.save(buffer, format="PNG", optimize=True)
    buffer.seek(0)
    return buffer


def _create_fallback_plaque(width: int, height: int) -> Image.Image:
    """توليد لوحة رخامية بديلة بنمط رمادي في حال عدم توفر الصورة الأساسية."""
    img = Image.new("RGBA", (width, height), (225, 228, 230, 255))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([20, 20, width - 20, height - 20], radius=35, outline=(50, 50, 55, 255), width=6)
    draw.rounded_rectangle([26, 26, width - 26, height - 26], radius=30, outline=(255, 255, 255, 220), width=3)
    return img
