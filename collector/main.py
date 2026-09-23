"""수집 스케줄러 — 09:00 / 21:00 KST (PRD-03 FR-38)

    python -m collector.main            스케줄러 상주
    python -m collector.main --once     1회 실행
    python -m collector.main --once --dry-run
"""
import argparse
import asyncio

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from shared.config import settings
from shared.logging import get_logger

from .pipeline import run_batch

logger = get_logger("collector")


async def job() -> None:
    logger.info("배치 시작")
    await run_batch()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="스케줄러 없이 1회 실행")
    args = ap.parse_args()

    logger.info("Collector starting", {"config": settings.safe_dump()})

    if args.once:
        stats = await run_batch()
        print(stats)
        return

    sched = AsyncIOScheduler(timezone="Asia/Seoul")
    for bt in settings.batch_times.split(","):
        h, m = bt.strip().split(":")
        # max_instances=1: 배치가 겹쳐 실행되지 않게 (C-38)
        sched.add_job(job, "cron", hour=int(h), minute=int(m), max_instances=1)
        logger.info(f"배치 등록 {h}:{m} KST")
    sched.start()

    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        sched.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
