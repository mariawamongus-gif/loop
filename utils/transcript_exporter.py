import os
import html
from datetime import datetime
import discord
from typing import List

async def generate_html_transcript(channel: discord.TextChannel, ticket_id: str) -> str:
    """
    يولّد ملف HTML فائق الاحترافية بتصميم Cyberpunk / Neon مع تأثيرات Glassmorphism
    وأنيميشن ورسومات متحركة ودعم المرفقات والإمبيدات.
    """
    messages: List[discord.Message] = []
    async for msg in channel.history(limit=500, oldest_first=True):
        messages.append(msg)

    os.makedirs("transcripts", exist_ok=True)
    filename = f"transcripts/ticket_{ticket_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.html"

    rows = ""
    for idx, msg in enumerate(messages):
        author_name = html.escape(msg.author.name)
        author_avatar = msg.author.display_avatar.url if msg.author.display_avatar else ""
        content = html.escape(msg.content or "").replace("\n", "<br>")
        time_str = msg.created_at.strftime("%Y-%m-%d %H:%M:%S")
        bot_tag = '<span class="bot-badge">BOT</span>' if msg.author.bot else ""
        delay = f"animation-delay: {idx * 0.06}s;"

        # Attachments
        attachments_html = ""
        if msg.attachments:
            for att in msg.attachments:
                att_url = html.escape(att.url)
                att_name = html.escape(att.filename)
                if any(att.filename.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp']):
                    attachments_html += f'<div class="attachment"><a href="{att_url}" target="_blank"><img src="{att_url}" alt="{att_name}" class="att-img"/></a></div>'
                else:
                    attachments_html += f'<div class="attachment"><a href="{att_url}" target="_blank" class="att-file">{att_name}</a></div>'

        # Embeds
        embeds_html = ""
        if msg.embeds:
            for emb in msg.embeds:
                emb_title = html.escape(emb.title or "")
                emb_desc = html.escape(emb.description or "").replace("\n", "<br>")
                if emb_title or emb_desc:
                    embeds_html += f'<div class="embed-card"><div class="embed-title">{emb_title}</div><div class="embed-desc">{emb_desc}</div></div>'

        rows += f"""
        <div class="message-card" style="{delay}">
            <img class="avatar" src="{author_avatar}" alt="" loading="lazy"/>
            <div class="message-body">
                <div class="message-header">
                    <span class="username">{author_name}</span>{bot_tag}
                    <span class="timestamp">{time_str}</span>
                </div>
                <div class="message-text">{content}</div>
                {attachments_html}
                {embeds_html}
            </div>
        </div>
        """

    msg_count = len(messages)
    human_count = sum(1 for m in messages if not m.author.bot)

    html_content = f"""<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Neon Transcript | Ticket #{ticket_id}</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            background: #0a0a12;
            color: #c8d6e5;
            font-family: 'Inter', 'Segoe UI', sans-serif;
            line-height: 1.6;
            min-height: 100vh;
        }}
        body::before {{
            content: '';
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background:
                radial-gradient(ellipse at 20% 50%, rgba(0, 245, 255, 0.04) 0%, transparent 50%),
                radial-gradient(ellipse at 80% 20%, rgba(88, 101, 242, 0.04) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 80%, rgba(80, 250, 123, 0.03) 0%, transparent 50%);
            pointer-events: none;
            z-index: 0;
        }}
        ::-webkit-scrollbar {{ width: 8px; }}
        ::-webkit-scrollbar-track {{ background: #0d0d18; }}
        ::-webkit-scrollbar-thumb {{ background: linear-gradient(180deg, #00f5ff, #5865f2); border-radius: 4px; }}
        ::-webkit-scrollbar-thumb:hover {{ background: linear-gradient(180deg, #00dce6, #4752c4); }}

        .container {{ max-width: 960px; margin: 0 auto; padding: 30px 20px; position: relative; z-index: 1; }}

        /* Header */
        .header {{
            background: linear-gradient(135deg, rgba(20,20,35,0.85), rgba(30,30,50,0.85));
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(0, 245, 255, 0.15);
            border-radius: 16px;
            padding: 32px;
            margin-bottom: 28px;
            position: relative;
            overflow: hidden;
            animation: headerGlow 3s ease-in-out infinite alternate;
        }}
        @keyframes headerGlow {{
            0% {{ box-shadow: 0 0 20px rgba(0,245,255,0.05), inset 0 0 30px rgba(0,245,255,0.02); }}
            100% {{ box-shadow: 0 0 40px rgba(0,245,255,0.1), inset 0 0 50px rgba(0,245,255,0.04); }}
        }}
        .header::before {{
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 200%; height: 2px;
            background: linear-gradient(90deg, transparent, #00f5ff, #5865f2, transparent);
            animation: headerLine 4s linear infinite;
        }}
        @keyframes headerLine {{
            0% {{ transform: translateX(-50%); }}
            100% {{ transform: translateX(50%); }}
        }}
        .header h1 {{
            font-size: 26px;
            font-weight: 700;
            background: linear-gradient(135deg, #00f5ff, #5865f2, #50fa7b);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 12px;
        }}
        .header-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 20px;
            margin-top: 14px;
        }}
        .meta-chip {{
            background: rgba(0,245,255,0.08);
            border: 1px solid rgba(0,245,255,0.15);
            border-radius: 8px;
            padding: 6px 14px;
            font-size: 13px;
            color: #8892b0;
        }}
        .meta-chip strong {{ color: #00f5ff; }}

        /* Messages */
        @keyframes fadeSlideIn {{
            0% {{ opacity: 0; transform: translateY(14px); }}
            100% {{ opacity: 1; transform: translateY(0); }}
        }}
        .message-card {{
            display: flex;
            align-items: flex-start;
            gap: 14px;
            background: rgba(18,18,30,0.7);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.04);
            padding: 16px 20px;
            margin-bottom: 6px;
            border-radius: 10px;
            animation: fadeSlideIn 0.4s ease forwards;
            opacity: 0;
            transition: all 0.25s ease;
        }}
        .message-card:hover {{
            background: rgba(24,24,40,0.85);
            border-color: rgba(0,245,255,0.12);
            box-shadow: 0 4px 20px rgba(0,245,255,0.06);
            transform: translateX(4px);
        }}
        .avatar {{
            width: 44px;
            height: 44px;
            border-radius: 50%;
            border: 2px solid rgba(0,245,255,0.25);
            flex-shrink: 0;
            transition: border-color 0.3s;
        }}
        .message-card:hover .avatar {{ border-color: rgba(0,245,255,0.6); box-shadow: 0 0 12px rgba(0,245,255,0.2); }}
        .message-body {{ flex: 1; min-width: 0; }}
        .message-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 5px; flex-wrap: wrap; }}
        .username {{ font-weight: 600; color: #e2e8f0; font-size: 14px; }}
        .bot-badge {{
            background: linear-gradient(135deg, #5865f2, #00f5ff);
            color: #fff;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 4px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-shadow: 0 0 6px rgba(0,245,255,0.4);
        }}
        .timestamp {{ color: #4a5568; font-size: 11px; margin-right: auto; }}
        .message-text {{ color: #a0aec0; font-size: 14px; word-break: break-word; }}

        /* Attachments */
        .attachment {{ margin-top: 10px; }}
        .att-img {{ max-width: 320px; max-height: 220px; border-radius: 8px; border: 1px solid rgba(0,245,255,0.1); transition: transform 0.2s; }}
        .att-img:hover {{ transform: scale(1.03); }}
        .att-file {{
            display: inline-block;
            background: rgba(0,245,255,0.06);
            border: 1px solid rgba(0,245,255,0.15);
            border-radius: 6px;
            padding: 6px 14px;
            color: #00f5ff;
            text-decoration: none;
            font-size: 13px;
        }}
        .att-file:hover {{ background: rgba(0,245,255,0.12); }}

        /* Embeds */
        .embed-card {{
            margin-top: 10px;
            background: rgba(30,30,50,0.6);
            border-right: 3px solid #5865f2;
            border-radius: 6px;
            padding: 12px 16px;
        }}
        .embed-title {{ color: #00f5ff; font-weight: 600; font-size: 14px; margin-bottom: 4px; }}
        .embed-desc {{ color: #8892b0; font-size: 13px; }}

        /* Footer */
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            border-top: 1px solid rgba(0,245,255,0.08);
            color: #4a5568;
            font-size: 12px;
        }}
        .footer span {{ color: #00f5ff; }}

        @media (max-width: 640px) {{
            .container {{ padding: 14px 10px; }}
            .header {{ padding: 20px 16px; }}
            .header h1 {{ font-size: 20px; }}
            .message-card {{ padding: 12px 14px; }}
            .avatar {{ width: 36px; height: 36px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Neon Transcript | Ticket #{ticket_id}</h1>
            <p style="color:#718096; font-size:14px;">القناة: #{html.escape(channel.name)}</p>
            <div class="header-meta">
                <div class="meta-chip"><strong>{msg_count}</strong>&nbsp; رسالة</div>
                <div class="meta-chip"><strong>{human_count}</strong>&nbsp; رسائل بشرية</div>
                <div class="meta-chip"><strong>{msg_count - human_count}</strong>&nbsp; ردود آلية</div>
                <div class="meta-chip">التاريخ: <strong>{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</strong></div>
            </div>
        </div>
        <div class="messages">
            {rows}
        </div>
        <div class="footer">
            Generated by <span>Neon Engine v2.0</span> | Automated Transcript System
        </div>
    </div>
</body>
</html>
"""

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html_content)

    return filename
