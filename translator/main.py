"""번역 워커 진입점 — PRD-03 §8

    python -m translator.main                   큐를 비우고 종료 (2패스)
    python -m translator.main --passes 1        초벌만
    python -m translator.main --check           모델 로드 없이 GPU/큐 확인
"""
import argparse
import asyncio
import os

from shared.config import settings
from shared.logging import get_logger

logger = get_logger("translator")


async def check_only() -> None:
    from sqlalchemy import text

    from shared.db import AsyncSessionLocal

    logger.info(f"CUDA_VISIBLE_DEVICES={os.environ.get('CUDA_VISIBLE_DEVICES')}")
    try:
        import torch
        logger.info(f"torch {torch.__version__} / GPU {torch.cuda.device_count()}장")
        for i in range(torch.cuda.device_count()):
            logger.info(f"  GPU {i}: {torch.cuda.get_device_name(i)}")
    except ImportError:
        logger.warning("torch 없음")

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(text(
            "SELECT status, count(*) FROM translation_jobs GROUP BY status"))).fetchall()
    logger.info("큐 현황", {"queue": {s: n for s, n in rows}})


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--passes", type=int, choices=[1, 2], default=2)
    ap.add_argument("--model", default=None)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--loop", action="store_true", help="큐가 비어도 대기")
    args = ap.parse_args()

    logger.info("Translator starting", {"config": settings.safe_dump()})

    if args.check:
        await check_only()
        return

    from .worker import run

    stats = await run(args.model or settings.translator_model,
                      passes=args.passes, once=not args.loop)
    print(stats)


if __name__ == "__main__":
    asyncio.run(main())
