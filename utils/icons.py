import os
from PIL import Image, ImageDraw

def generate_default_png_icons(output_dir: str = "assets/icons/png"):
    """
    يقوم بإنشاء وتجهيز أيقونات PNG شفافة بسيطة بجودة عالية لاستخدامها
    في البوت كصور مصغرة (Thumbnails) أو أيقونات داخل الـ Embeds.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    icons_def = {
        "success": (80, 250, 120),   # أخضر هادئ
        "error": (255, 85, 85),      # أحمر
        "warning": (255, 184, 108),  # برتقالي
        "info": (139, 233, 253),     # سماوي
        "shield": (189, 147, 249),   # بنفسجي أمان
        "ticket": (255, 121, 198)    # وردي تذاكر
    }

    size = (128, 128)
    for name, color in icons_def.items():
        img = Image.new("RGBA", size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        # رسم شكل دائري متناسق مع حواف دائرية
        draw.ellipse([8, 8, 120, 120], outline=color, width=8)
        draw.rectangle([48, 48, 80, 80], fill=color)
        
        filepath = os.path.join(output_dir, f"{name}.png")
        img.save(filepath, "PNG")

if __name__ == "__main__":
    generate_default_png_icons()
