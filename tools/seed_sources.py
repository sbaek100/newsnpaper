"""수집 소스 시드 — PRD-03 §7.2~7.3

재실행해도 중복되지 않는다 (UPSERT).
    docker compose exec -T backend python tools/seed_sources.py
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from shared.db import engine  # noqa: E402

SOURCES = [
    # kind,  name,                 url,                                                      category
    ("rss", "BleepingComputer", "https://www.bleepingcomputer.com/feed/", "international"),
    ("rss", "The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "international"),
    ("rss", "Krebs on Security", "https://krebsonsecurity.com/feed/", "international"),
    ("rss", "SecurityWeek", "https://www.securityweek.com/feed/", "international"),
    ("rss", "Dark Reading", "https://www.darkreading.com/rss.xml", "international"),
    ("rss", "보안뉴스", "https://www.boannews.com/media/news_rss.xml", "domestic"),
    ("rss", "데일리시큐", "https://www.dailysecu.com/rss/allArticle.xml", "domestic"),
    ("api", "GDELT DOC", "https://api.gdeltproject.org/api/v2/doc/doc", "international"),
    ("api", "Naver News", "https://openapi.naver.com/v1/search/news.json", "domestic"),
    ("arxiv", "arXiv cs.CR", "http://export.arxiv.org/api/query?search_query=cat:cs.CR", "paper"),
    ("arxiv", "arXiv cs.AI", "http://export.arxiv.org/api/query?search_query=cat:cs.AI", "paper"),
    ("arxiv", "arXiv cs.LG", "http://export.arxiv.org/api/query?search_query=cat:cs.LG", "paper"),
]

UPSERT = text("""
    INSERT INTO sources (kind, name, url, category, enabled)
    VALUES (:kind, :name, :url, :category, true)
    ON CONFLICT (kind, name) DO UPDATE
        SET url = EXCLUDED.url, category = EXCLUDED.category
""")


async def main() -> None:
    async with engine.begin() as conn:
        for kind, name, url, category in SOURCES:
            await conn.execute(
                UPSERT, {"kind": kind, "name": name, "url": url, "category": category}
            )
        total = (await conn.execute(text("SELECT count(*) FROM sources"))).scalar()
    await engine.dispose()
    print(f"시드 완료 — sources {total}건")


if __name__ == "__main__":
    asyncio.run(main())
