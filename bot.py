import discord
from discord.ext import commands
import asyncio
import os
import logging
from config import Config
from core.database import init_db
from core.redis_client import redis_manager
from utils.icons import generate_default_png_icons
from cogs.tickets import OpenTicketView

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")

class NeonBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.guilds = True
        intents.voice_states = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        logging.info("بدء تهيئة قاعدة البيانات والخدمات...")
        await init_db()
        await redis_manager.init()
        generate_default_png_icons()

        # تسجيل الـ Views الدائمة
        self.add_view(OpenTicketView())

        # تحميل الـ Cogs
        cogs_dir = os.path.join(os.path.dirname(__file__), "cogs")
        for filename in os.listdir(cogs_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                cog_name = f"cogs.{filename[:-3]}"
                try:
                    await self.load_extension(cog_name)
                    logging.info(f"تم تحميل الـ Cog بنجاح: {cog_name}")
                except Exception as e:
                    logging.error(f"فشل تحميل الـ Cog {cog_name}: {e}")

        # المزامنة التلقائية لأوامر Slash Commands
        try:
            synced = await self.tree.sync()
            logging.info(f"تم مزامنة {len(synced)} أمر Slash بنجاح.")
        except Exception as e:
            logging.error(f"فشل مزامنة الأوامر: {e}")

    async def on_ready(self):
        logging.info(f"==========================================")
        logging.info(f"Neon Engine initialized. User: {self.user} (ID: {self.user.id})")
        logging.info(f"Status: Active | Systems Operational.")
        logging.info(f"==========================================")

bot = NeonBot()

if __name__ == "__main__":
    if not Config.DISCORD_TOKEN:
        print("خطأ حرّج: لم يتم توفير DISCORD_TOKEN في ملف .env")
    else:
        token_prefix = Config.DISCORD_TOKEN[:10] if len(Config.DISCORD_TOKEN) >= 10 else Config.DISCORD_TOKEN
        print(f"جاري الاتصال بـ Discord باستخدام التوكن المعرف (بدايته: {token_prefix}...)...")
        bot.run(Config.DISCORD_TOKEN)

