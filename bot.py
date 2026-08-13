import discord
from discord.ext import commands, tasks
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

    @tasks.loop(minutes=5)
    async def update_presence_task(self):
        """تحديث الحالة الحية للبوت بشكل دوري."""
        if not self.is_ready():
            return
        total_members = sum(g.member_count or 0 for g in self.guilds)
        total_guilds = len(self.guilds)
        activities = [
            discord.Activity(type=discord.ActivityType.watching, name=f"{total_members} عضو في {total_guilds} سيرفر"),
            discord.Activity(type=discord.ActivityType.listening, name="/setup | Neon Engine v2.0"),
            discord.Activity(type=discord.ActivityType.competing, name="Neon AI Intelligence System"),
        ]
        import random
        await self.change_presence(
            activity=random.choice(activities),
            status=discord.Status.online
        )

    @update_presence_task.before_loop
    async def before_presence(self):
        await self.wait_until_ready()

    async def on_ready(self):
        total_members = sum(g.member_count or 0 for g in self.guilds)
        logging.info(f"==================================================")
        logging.info(f"Neon Engine v2.0 Initialized Successfully!")
        logging.info(f"User: {self.user} (ID: {self.user.id})")
        logging.info(f"Servers: {len(self.guilds)} | Total Members: {total_members}")
        logging.info(f"Status: Active & Operational 🟢")
        logging.info(f"==================================================")
        if not self.update_presence_task.is_running():
            self.update_presence_task.start()

bot = NeonBot()

if __name__ == "__main__":
    if not Config.DISCORD_TOKEN:
        print("خطأ حرج: لم يتم توفير DISCORD_TOKEN في ملف .env")
    else:
        token_prefix = Config.DISCORD_TOKEN[:10] if len(Config.DISCORD_TOKEN) >= 10 else Config.DISCORD_TOKEN
        print(f"جاري الاتصال بـ Discord باستخدام التوكن المعرف (بدايته: {token_prefix}...)...")
        bot.run(Config.DISCORD_TOKEN)
