import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from shared.config import settings
from shared.logging import get_logger

logger = get_logger("collector")

async def dummy_job():
    logger.info("Running collector batch job...")

async def main():
    logger.info("Collector starting", {"config": settings.safe_dump()})
    
    scheduler = AsyncIOScheduler()
    
    batch_times = settings.batch_times.split(",")
    for bt in batch_times:
        hour, minute = bt.strip().split(":")
        scheduler.add_job(dummy_job, 'cron', hour=int(hour), minute=int(minute))
        logger.info(f"Registered batch job at {hour}:{minute}")
        
    scheduler.start()
    
    try:
        while True:
            await asyncio.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
