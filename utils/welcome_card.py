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
    member_count: int,
    is_rejoin: bool = False
) -> io.BytesIO:
    """
    توليد بطاقة ترحيب فائقة الفخامة بنمط الرخام المنقوش بشعار TS،
    مع نصوص بيضاء مجسمة وبارزة ثلاثية الأبعاد (3D Puffed/Engraved Typography).
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
    avatar_center = (250, 384)
    avatar_radius = 120
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

    # إطار معدني مشطوف ثلاثي الأبعاد حول الأفاتار
    draw.ellipse([x1 - 6, y1 - 6, x1 + avatar_size + 6, y1 + avatar_size + 6], outline=(255, 255, 255, 240), width=5)
    draw.ellipse([x1 - 2, y1 - 2, x1 + avatar_size + 2, y1 + avatar_size + 2], outline=(20, 20, 25, 255), width=5)

    # ─── 2. الخطوط البيضاء المجسمة والبارزة ثلاثية الأبعاد (3D Puffed) ────────
    font_welcome = _get_font("georgiab", 62 if is_rejoin else 66)
    font_server = _get_font("georgiab", 88)
    font_user = _get_font("segoeuib", 74)
    font_count = _get_font("georgiab", 52)

    def draw_3d_text(pos, text, font, main_color=(250, 252, 255, 255)):
        """رسم نص مجسم ثلاثي الأبعاد مع ظل عميق وطبقات إضاءة بارزة."""
        tx, ty = pos
        # تدرج الظل العميق بالأسفل
        for offset in range(6, 0, -1):
            draw.text((tx + offset, ty + offset), text, fill=(15, 18, 22, 170), font=font)
        # إضاءة الحواف العلوية
        draw.text((tx - 1, ty - 1), text, fill=(255, 255, 255, 255), font=font)
        # الوجه الأبيض الساطع
        draw.text((tx, ty), text, fill=main_color, font=font)

    text_x = 405
    text_y = 125

    # سطر الترحيب (Welcome To أو Welcome Back To)
    welcome_title = "WELCOME BACK TO" if is_rejoin else "WELCOME TO"
    draw_3d_text((text_x, text_y), welcome_title, font_welcome, (255, 255, 255, 255))

    # سطر اسم السيرفر
    display_server = server_name.strip().upper()
    if len(display_server) > 16:
        display_server = display_server[:14] + "..."
    draw_3d_text((text_x, text_y + 78), display_server, font_server, (245, 248, 255, 255))

    # خط فاصل معدني بارز ثلاثي الأبعاد
    line_y = text_y + 205
    draw.line([(text_x, line_y), (text_x + 530, line_y)], fill=(120, 125, 135, 255), width=5)
    draw.line([(text_x, line_y + 4), (text_x + 530, line_y + 4)], fill=(255, 255, 255, 255), width=5)

    # سطر اسم العضو
    display_user = username.strip()
    if len(display_user) > 16:
        display_user = display_user[:14] + "..."
    draw_3d_text((text_x, text_y + 235), f"@{display_user}", font_user, (240, 245, 255, 255))

    # سطر العضو أو العضو العائد
    sub_tag = "RETURNING MEMBER" if is_rejoin else f"MEMBER #{member_count}"
    draw_3d_text((text_x, text_y + 338), sub_tag, font_count, (225, 230, 240, 255))

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
