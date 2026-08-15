import aiohttp
import asyncio
import re
import urllib.parse
import logging
from ai.fallback_manager import ai_manager

logger = logging.getLogger(__name__)

async def search_duckduckgo_lite(query: str, max_results: int = 5) -> list[dict]:
    """
    البحث السريع المباشر في محرك البحث واستخراج العناوين والروابط والمقتطفات النصية بدون اعتماد على حزم خارجية.
    """
    url = "https://html.duckduckgo.com/html/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US,en;q=0.5"
    }
    data = {"q": query, "b": ""}

    results = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    html = await resp.text()
                    # استخراج النتائج بالـ regex السريع والآمن
                    links = re.findall(r'<a class="result__url" href="([^"]+)".*?>(.*?)</a>', html, re.DOTALL)
                    snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
                    titles = re.findall(r'<a class="result__title[^>]*href="[^"]*"[^>]*>(.*?)</a>', html, re.DOTALL)

                    for i in range(min(len(titles), len(snippets), max_results)):
                        clean_title = re.sub(r'<[^>]+>', '', titles[i]).strip()
                        clean_snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()
                        raw_link = links[i][0] if i < len(links) else ""
                        
                        # فك تشفير رابط DuckDuckGo الفعلي
                        actual_url = raw_link
                        if "uddg=" in raw_link:
                            try:
                                actual_url = urllib.parse.unquote(raw_link.split("uddg=")[1].split("&")[0])
                            except Exception:
                                actual_url = raw_link

                        if clean_title and clean_snippet:
                            results.append({
                                "title": clean_title,
                                "snippet": clean_snippet,
                                "url": actual_url
                            })
    except Exception as e:
        logger.warning(f"تعذر استرجاع نتائج البحث المباشر من DuckDuckGo: {e}")

    # محرك احتياطي عبر Wikipedia API إذا كانت النتائج فارغة
    if not results:
        try:
            wiki_url = f"https://ar.wikipedia.org/w/api.php?action=opensearch&search={urllib.parse.quote(query)}&limit={max_results}&namespace=0&format=json"
            async with aiohttp.ClientSession() as session:
                async with session.get(wiki_url, timeout=8) as resp:
                    if resp.status == 200:
                        wiki_data = await resp.json()
                        if len(wiki_data) >= 4 and wiki_data[1]:
                            for i in range(len(wiki_data[1])):
                                t = wiki_data[1][i]
                                s = wiki_data[2][i] if i < len(wiki_data[2]) else ""
                                u = wiki_data[3][i] if i < len(wiki_data[3]) else ""
                                if t and s:
                                    results.append({"title": t, "snippet": s, "url": u})
        except Exception as e:
            logger.warning(f"تعذر استرجاع نتائج ويكيبيديا: {e}")

    return results


async def search_and_synthesize(query: str) -> dict:
    """
    يبحث في الإنترنت ويلخص النتائج عبر الذكاء الاصطناعي مع تقديم المصادر.
    """
    try:
        search_results = await search_duckduckgo_lite(query, max_results=4)
    except Exception as e:
        logger.warning(f"خطأ أثناء جلب نتائج الويب: {e}")
        search_results = []

    if not search_results:
        return {
            "summary": "لم يتم العثور على معلومات دقيقة ومباشرة في مصادر البحث المفتوحة لهذا الاستعلام.",
            "sources": []
        }

    context_lines = []
    sources = []
    for idx, item in enumerate(search_results, 1):
        context_lines.append(f"[{idx}] العنوان: {item['title']}\nالمعلومة: {item['snippet']}\nالرابط: {item['url']}")
        sources.append(f"[{idx}] [{item['title']}]({item['url']})")

    context_str = "\n\n".join(context_lines)

    sys_prompt = (
        "أنت 'Neon' المساعد الاستراتيجي والعسكري للعمليات. "
        "مهمتك: الإجابة على استعلام البحث التالي بدقة متناهية بناءً على مقتطفات نتائج البحث المرفقة. "
        "قدم إجابة مباشرة وواضحة ومنضبطة، ورتب المعلومات في نقاط تكتيكية واضحة بدون حشو أو إيموجيات تعبيرية."
    )

    user_msg = f"الاستعلام المطلوب: {query}\n\nنتائج البحث الحية المستخرجة:\n{context_str}"

    try:
        summary = await ai_manager.generate(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=sys_prompt
        )
    except Exception as e:
        logger.warning(f"تعذر تلخيص نتائج البحث عبر AI: {e}")
        summary = "تم استخراج المصادر أدناه، ولكن تعذر استدعاء نموذج التلخيص اللحظي."

    return {
        "summary": summary,
        "sources": sources
    }
