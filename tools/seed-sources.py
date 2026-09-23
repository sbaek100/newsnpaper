import asyncio
import logging
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from shared.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

SEED_DATA = [
    # RSS - international
    {"kind": "rss", "name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/", "category": "international", "enabled": True},
    {"kind": "rss", "name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews", "category": "international", "enabled": True},
    {"kind": "rss", "name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/", "category": "international", "enabled": True},
    {"kind": "rss", "name": "SecurityWeek", "url": "https://www.securityweek.com/feed/", "category": "international", "enabled": True},
    {"kind": "rss", "name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml", "category": "international", "enabled": True},
    
    # RSS - domestic
    {"kind": "rss", "name": "보안뉴스", "url": "https://www.boannews.com/media/news_rss.xml", "category": "domestic", "enabled": True},
    {"kind": "rss", "name": "데일리시큐", "url": "https://www.dailysecu.com/rss/allArticle.xml", "category": "domestic", "enabled": True},
    
    # API
    {"kind": "api", "name": "GDELT 2.0 DOC", "url": "https://api.gdeltproject.org/api/v2/doc/doc", "category": "international", "enabled": True},
    {"kind": "api", "name": "Naver 검색(news)", "url": "https://openapi.naver.com/v1/search/news.json", "category": "domestic", "enabled": True},
    
    # arXiv
    {"kind": "arxiv", "name": "arXiv cs.CR", "url": "http://export.arxiv.org/api/query?search_query=cat:cs.CR", "category": "paper", "enabled": True},
    {"kind": "arxiv", "name": "arXiv cs.AI", "url": "http://export.arxiv.org/api/query?search_query=cat:cs.AI", "category": "paper", "enabled": True},
    {"kind": "arxiv", "name": "arXiv cs.LG", "url": "http://export.arxiv.org/api/query?search_query=cat:cs.LG", "category": "paper", "enabled": True},
]

async def seed_sources():
    engine = create_async_engine(DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        for s in SEED_DATA:
            query = text("""
                INSERT INTO sources (kind, name, url, category, enabled)
                VALUES (:kind, :name, :url, :category, :enabled)
                ON CONFLICT (kind, name) DO UPDATE
                SET url = EXCLUDED.url,
                    category = EXCLUDED.category,
                    enabled = EXCLUDED.enabled;
            """)
            await conn.execute(query, s)
        logger.info(f"Upserted {len(SEED_DATA)} sources.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_sources())
