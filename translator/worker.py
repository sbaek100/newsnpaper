"""번역 워커 — 큐 소비 + 2패스 번역

추론은 동기다(architecture.md A-7). 큐 I/O 만 async.
큐가 비면 워커를 종료한다 (PRD-03 FR-43).
"""

import asyncio
import os
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from shared.db import AsyncSessionLocal
from shared.logging import get_logger

from . import prompts
from .detect import check, has_critical, strip_preamble

logger = get_logger("translator.worker")

POLL_SEC = 2
BATCH = 8
MAX_ATTEMPTS = 3  # FR-45
BACKOFF = [10, 60, 300]
STALE_MIN = 30  # running 으로 남은 job 회수 (T-5)

CLAIM = text("""
    UPDATE translation_jobs SET status='running', started_at=now(), attempts=attempts+1
    WHERE id IN (
        SELECT id FROM translation_jobs
         WHERE status='pending'
         ORDER BY created_at
         LIMIT :n
         FOR UPDATE SKIP LOCKED
    )
    RETURNING id, content_id, field, attempts
""")

RECLAIM = text("""
    UPDATE translation_jobs SET status='pending'
     WHERE status='running' AND started_at < :cutoff
""")

# 섹션은 해당 요소만 갱신한다. 통째 덮어쓰면 동시 작업이 서로를 지운다 (T-7).
SET_SECTION = text("""
    UPDATE contents SET sections = (
        SELECT jsonb_agg(
            CASE WHEN x->>'name' = :name
                 THEN jsonb_set(x, '{textKo}', to_jsonb(CAST(:val AS text)))
                 ELSE x END)
        FROM jsonb_array_elements(sections) x)
     WHERE id = :cid
""")

FINALIZE = text("""
    UPDATE contents c SET translation_status = CASE
        WHEN EXISTS (SELECT 1 FROM translation_jobs j
                      WHERE j.content_id=c.id AND j.status IN ('pending','running'))
            THEN 'pending'
        WHEN EXISTS (SELECT 1 FROM translation_jobs j
                      WHERE j.content_id=c.id AND j.status='failed')
            THEN 'failed'
        ELSE 'done' END
     WHERE c.id = :cid
""")


async def fetch_source_text(db, content_id: int, field: str) -> str | None:
    if field == "title":
        q = text("SELECT title_original FROM contents WHERE id=:i")
    elif field == "summary":
        q = text("SELECT summary_original FROM contents WHERE id=:i")
    else:
        name = field.split(":", 1)[1]
        q = text("""
            SELECT x->>'textOriginal' FROM contents,
                   jsonb_array_elements(sections) x
             WHERE id=:i AND x->>'name'=:n LIMIT 1
        """)
        return (await db.execute(q, {"i": content_id, "n": name})).scalar()
    return (await db.execute(q, {"i": content_id})).scalar()


async def write_back(db, content_id: int, field: str, value: str) -> None:
    if field == "title":
        await db.execute(text("UPDATE contents SET title_ko=:v WHERE id=:i"),
                         {"v": value, "i": content_id})
    elif field == "summary":
        await db.execute(text("UPDATE contents SET summary_ko=:v WHERE id=:i"),
                         {"v": value, "i": content_id})
    else:
        await db.execute(SET_SECTION,
                         {"name": field.split(":", 1)[1], "val": value, "cid": content_id})


class Translator:
    """모델을 한 번만 로드하고 두 패스에 재사용한다 (FR-39b)."""

    def __init__(self, model_id: str, passes: int = 2):
        self.model_id = model_id
        self.passes = passes
        self.glossary = prompts.load_glossary()
        self.model = None
        self.tok = None

    def load(self) -> float:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        # 🔴 Pascal sm_61: FlashAttention 커널이 없다. math/mem-efficient 로 폴백.
        torch.backends.cuda.enable_flash_sdp(False)
        torch.backends.cuda.enable_math_sdp(True)
        torch.backends.cuda.enable_mem_efficient_sdp(True)

        t0 = time.monotonic()
        self.tok = AutoTokenizer.from_pretrained(self.model_id, trust_remote_code=True)
        # GPU 장당 상한을 명시하지 않으면 accelerate 가 여유를 과하게 잡아
        # 일부 레이어를 CPU 로 흘린다. 7.8B fp16 ≈ 15.6GB 이므로 2장이면 충분하다.
        n_gpu = torch.cuda.device_count()
        self.model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            dtype=torch.float16,  # 🔴 bf16 금지 — Pascal 에서 에뮬레이션이다
            device_map="auto",
            max_memory={i: "11GiB" for i in range(n_gpu)},
            attn_implementation="sdpa",
            trust_remote_code=True,
        )
        self.model.eval()
        # 오프로딩된 파라미터는 device.type 이 "meta" 다. cpu 만 보면 놓친다.
        bad = [n for n, p in self.model.named_parameters() if p.device.type in ("cpu", "meta")]
        if bad:
            raise RuntimeError(
                f"CPU/디스크 오프로딩 감지 ({len(bad)}개, 예: {bad[0]}). 번역이 매우 느려진다")
        return time.monotonic() - t0

    def _generate(self, messages: list[dict], max_new: int) -> str:
        import torch

        enc = self.tok.apply_chat_template(
            messages, tokenize=True, add_generation_prompt=True, return_tensors="pt"
        )
        # transformers 버전에 따라 텐서 또는 BatchEncoding(dict) 을 반환한다.
        ids = enc["input_ids"] if hasattr(enc, "keys") else enc
        ids = ids.to(self.model.device)
        with torch.no_grad():
            out = self.model.generate(
                ids, max_new_tokens=max_new, do_sample=False,
                eos_token_id=self.tok.eos_token_id,
                pad_token_id=self.tok.eos_token_id or self.tok.pad_token_id,
            )
        return strip_preamble(self.tok.decode(out[0][ids.shape[-1]:], skip_special_tokens=True))

    def translate(self, src: str, field: str) -> tuple[str, dict]:
        """(최종 번역, 메타) 반환. 동기 — run_in_executor 로 호출한다."""
        budget = min(max(int(len(src) * 1.5), 128), 4096)

        draft = self._generate(prompts.pass1(src, field, self.glossary), budget)
        meta = {"draft_len": len(draft)}
        if self.passes == 1:
            return draft, meta

        final = self._generate(prompts.pass2(src, draft, field, self.glossary), budget)

        # 과잉 수정 방어 (FR-75)
        ratio = len(final) / max(len(draft), 1)
        if not (0.7 <= ratio <= 1.5):
            meta["overedit"] = round(ratio, 2)
            return draft, meta
        # 검증 출력에 치명 이상이 있으면 초벌 채택 (FR-76)
        if has_critical(check(final, src, self.glossary)):
            meta["verify_fail"] = True
            return draft, meta
        return final, meta


async def run(model_id: str, passes: int = 2, once: bool = True) -> dict:
    tr = Translator(model_id, passes)
    logger.info("모델 로딩", {"model": model_id, "gpus": os.environ.get("CUDA_VISIBLE_DEVICES")})
    load_sec = await asyncio.to_thread(tr.load)
    logger.info(f"모델 로딩 완료 {load_sec:.1f}s")

    stats = {"done": 0, "failed": 0, "retry": 0, "overedit": 0, "verify_fail": 0}
    loop = asyncio.get_running_loop()

    async with AsyncSessionLocal() as db:
        await db.execute(RECLAIM, {"cutoff": datetime.now(timezone.utc) - timedelta(minutes=STALE_MIN)})
        await db.commit()

    idle = 0
    while True:
        async with AsyncSessionLocal() as db:
            jobs = (await db.execute(CLAIM, {"n": BATCH})).fetchall()
            await db.commit()

        if not jobs:
            idle += 1
            if once or idle > 3:  # 큐가 비면 종료 (FR-43)
                break
            await asyncio.sleep(POLL_SEC)
            continue
        idle = 0

        for job_id, cid, field, attempts in jobs:
            async with AsyncSessionLocal() as db:
                src = await fetch_source_text(db, cid, field)
                if not src:
                    await db.execute(
                        text("UPDATE translation_jobs SET status='failed', last_error='원문 없음',"
                             " finished_at=now() WHERE id=:i"), {"i": job_id})
                    await db.execute(FINALIZE, {"cid": cid})
                    await db.commit()
                    stats["failed"] += 1
                    continue

                try:
                    final, meta = await loop.run_in_executor(None, tr.translate, src, field)
                    found = check(final, src, tr.glossary)
                    if has_critical(found):
                        raise RuntimeError(f"치명 이상 {list(found)}")

                    await write_back(db, cid, field, final)
                    await db.execute(
                        text("UPDATE translation_jobs SET status='done', finished_at=now(),"
                             " last_error=NULL WHERE id=:i"), {"i": job_id})
                    stats["done"] += 1
                    for k in ("overedit", "verify_fail"):
                        if k in meta:
                            stats[k] += 1
                except Exception as e:  # noqa: BLE001
                    # 일부 예외는 str() 이 빈 문자열이다 (예: 맨 AttributeError).
                    # 타입을 반드시 남겨야 원인을 추적할 수 있다.
                    err = f"{type(e).__name__}: {e}"[:300]
                    # 실패한 문장 때문에 트랜잭션이 aborted 다. 롤백해야
                    # 후속 UPDATE 가 InFailedSQLTransactionError 로 연쇄 실패하지 않는다.
                    await db.rollback()
                    if attempts < MAX_ATTEMPTS:  # FR-45 재시도
                        await db.execute(
                            text("UPDATE translation_jobs SET status='pending', last_error=:e"
                                 " WHERE id=:i"), {"e": err, "i": job_id})
                        stats["retry"] += 1
                        await asyncio.sleep(BACKOFF[min(attempts - 1, 2)] / 30)  # 배치에선 축소
                    else:  # FR-46 영구 실패
                        await db.execute(
                            text("UPDATE translation_jobs SET status='failed', last_error=:e,"
                                 " finished_at=now() WHERE id=:i"), {"e": err, "i": job_id})
                        stats["failed"] += 1
                    logger.warning("번역 실패", {"job": job_id, "field": field, "error": err})

                await db.execute(FINALIZE, {"cid": cid})
                await db.commit()

        logger.info("진행", stats)

    logger.info("워커 종료", stats)
    return stats
