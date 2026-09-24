"""관리자 계정 시드 — PRD-02 FR-12

secrets/admin_initial_password 의 값으로 만들고, 최초 로그인 시 변경을 강제한다.
    docker compose exec -T backend python tools/seed_admin.py [email]
"""
import asyncio
import sys

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from backend.auth import hash_password  # noqa: E402
from shared.config import settings  # noqa: E402
from shared.db import engine  # noqa: E402

EMAIL = sys.argv[1] if len(sys.argv) > 1 else "admin@secubrief.local"


async def main() -> None:
    pw = settings.admin_initial_password
    if not pw:
        print("secrets/admin_initial_password 가 비어 있다. 값을 넣고 다시 실행하라.")
        raise SystemExit(1)
    async with engine.begin() as conn:
        await conn.execute(text("""
            INSERT INTO users (email, password_hash, role, must_change_password)
            VALUES (:e, :p, 'admin', true)
            ON CONFLICT (email) DO UPDATE
                SET password_hash = EXCLUDED.password_hash,
                    role = 'admin', must_change_password = true
        """), {"e": EMAIL, "p": hash_password(pw)})
    await engine.dispose()
    print(f"관리자 생성: {EMAIL} (최초 로그인 시 비밀번호 변경 강제)")


if __name__ == "__main__":
    asyncio.run(main())
