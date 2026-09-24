"""인증 — PRD-01 §5, PRD-02 §5

- 비밀번호: Argon2id (memory=64MiB, iterations=3, parallelism=4)
- 액세스 토큰 30분, 리프레시 14일
- 리프레시는 httpOnly 쿠키로만. 로컬 스토리지 금지 (FR-13)
- 🔴 권한 검사는 서버에서 강제한다. 프론트 표시 제어에 의존하지 않는다 (FR-5)
"""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError
from fastapi import Cookie, Depends, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.db import get_db

ACCESS_MIN = 30      # FR-12
REFRESH_DAYS = 14
ALGO = "HS256"
COOKIE = "sb_refresh"
MAX_KEYWORDS = 20    # FR-15
LOGIN_WINDOW_MIN = 10
LOGIN_MAX_FAIL = 5   # PRD-02 FR-13

# PRD-02 FR-9 의 파라미터를 그대로 쓴다
ph = PasswordHasher(memory_cost=64 * 1024, time_cost=3, parallelism=4, type=Type.ID)

# 로그인 실패 카운터. 단일 인스턴스라 메모리로 충분하다.
_fails: dict[str, list[datetime]] = {}


def hash_password(pw: str) -> str:
    return ph.hash(pw)


def verify_password(hashed: str, pw: str) -> bool:
    try:
        ph.verify(hashed, pw)
        return True
    except VerifyMismatchError:
        return False


def check_password_policy(pw: str) -> None:
    """FR-10 — 최소 10자, 동일 문자 4회 반복 금지."""
    if len(pw) < 10:
        raise HTTPException(400, "비밀번호는 10자 이상이어야 합니다")
    for i in range(len(pw) - 3):
        if pw[i] * 4 == pw[i : i + 4]:
            raise HTTPException(400, "같은 문자를 4번 이상 반복할 수 없습니다")


def note_login_fail(email: str) -> None:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(minutes=LOGIN_WINDOW_MIN)
    lst = [t for t in _fails.get(email, []) if t > cutoff]
    lst.append(now)
    _fails[email] = lst


def login_blocked(email: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=LOGIN_WINDOW_MIN)
    return len([t for t in _fails.get(email, []) if t > cutoff]) >= LOGIN_MAX_FAIL


def clear_login_fails(email: str) -> None:
    _fails.pop(email, None)


def make_access(user_id: int, role: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": str(user_id), "role": role, "iat": now,
         "exp": now + timedelta(minutes=ACCESS_MIN)},
        settings.require_jwt_secret(), algorithm=ALGO,
    )


def new_refresh() -> tuple[str, str, datetime]:
    """(원본 토큰, 해시, 만료) — DB 에는 해시만 저장한다."""
    raw = secrets.token_urlsafe(48)
    return raw, hashlib.sha256(raw.encode()).hexdigest(), \
        datetime.now(timezone.utc) + timedelta(days=REFRESH_DAYS)


def refresh_hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def set_refresh_cookie(resp, raw: str) -> None:
    resp.set_cookie(
        COOKIE, raw, httponly=True, samesite="lax", secure=False,  # 내부망 HTTP
        max_age=REFRESH_DAYS * 86400, path="/api",
    )


def clear_refresh_cookie(resp) -> None:
    resp.delete_cookie(COOKIE, path="/api")


async def current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        raise HTTPException(401, "로그인이 필요합니다")
    try:
        payload = jwt.decode(auth[7:], settings.require_jwt_secret(), algorithms=[ALGO])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "토큰이 만료되었습니다")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "유효하지 않은 토큰입니다")

    r = (await db.execute(text(
        "SELECT id, email, role, must_change_password FROM users WHERE id = :i"
    ), {"i": int(payload["sub"])})).first()
    if not r:
        raise HTTPException(401, "사용자를 찾을 수 없습니다")
    return {"id": r.id, "email": r.email, "role": r.role,
            "mustChangePassword": r.must_change_password}


async def active_user(user: dict = Depends(current_user)) -> dict:
    """비밀번호 변경 전에는 다른 API 를 막는다 (PRD-02 FR-12)."""
    if user["mustChangePassword"]:
        raise HTTPException(403, "비밀번호를 먼저 변경해야 합니다")
    return user


async def admin_user(user: dict = Depends(active_user)) -> dict:
    if user["role"] != "admin":
        raise HTTPException(403, "관리자만 접근할 수 있습니다")
    return user


async def refresh_cookie(sb_refresh: str | None = Cookie(None, alias=COOKIE)) -> str:
    if not sb_refresh:
        raise HTTPException(401, "리프레시 토큰이 없습니다")
    return sb_refresh
