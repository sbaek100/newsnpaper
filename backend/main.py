from fastapi import FastAPI, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from shared.config import settings
from shared.logging import get_logger
from shared.db import get_db

logger = get_logger("backend")
app = FastAPI(title="Secubrief API")

logger.info("Backend starting", {"config": settings.safe_dump()})

@app.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        logger.error("DB connection failed", {"error": str(e)})
        db_status = "error"
    return {"status": "ok", "db": db_status}
