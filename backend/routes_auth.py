"""인증·회원·관리자 엔드포인트 — PRD-01 §7"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.logging import get_logger

from . import auth as A
from . import queries
from .schemas import ListOut, to_card

logger = get_logger("backend.auth")
router = APIRouter()


class Credentials(BaseModel):
    # EmailStr 은 .local 같은 special-use 도메인을 거부한다. 이 서비스에서 이메일은
    # 연락 수단이 아니라 식별자일 뿐이므로(PRD-02 §7) 형식만 본다.
    email: str = Field(min_length=3, max_length=254,
                       pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=1)


class PasswordChange(BaseModel):
    currentPassword: str
    newPassword: str


class Keywords(BaseModel):
    keywords: list[str]


class MeOut(BaseModel):
    id: int
    email: str
    role: str
    mustChangePassword: bool


# ───────────────────────── 인증 ─────────────────────────


@router.post("/auth/signup")
async def signup(body: Credentials, resp: Response, db: AsyncSession = Depends(get_db)):
    A.check_password_policy(body.password)
    dup = (await db.execute(text("SELECT 1 FROM users WHERE email = :e"),
                            {"e": body.email})).first()
    if dup:
        raise HTTPException(409, "이미 가입된 이메일입니다")

    uid = (await db.execute(text(
        "INSERT INTO users (email, password_hash, role) VALUES (:e, :p, 'member')"
        " RETURNING id"
    ), {"e": body.email, "p": A.hash_password(body.password)})).scalar()

    raw, h, exp = A.new_refresh()
    await db.execute(text(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at)"
        " VALUES (:u, :h, :x)"), {"u": uid, "h": h, "x": exp})
    await db.commit()

    A.set_refresh_cookie(resp, raw)
    return {"accessToken": A.make_access(uid, "member"),
            "user": {"id": uid, "email": body.email, "role": "member",
                     "mustChangePassword": False}}


@router.post("/auth/login")
async def login(body: Credentials, resp: Response, db: AsyncSession = Depends(get_db)):
    if A.login_blocked(body.email):
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 10분 후 다시 시도하세요")

    r = (await db.execute(text(
        "SELECT id, password_hash, role, must_change_password FROM users WHERE email = :e"
    ), {"e": body.email})).first()

    if not r or not A.verify_password(r.password_hash, body.password):
        A.note_login_fail(body.email)
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")

    A.clear_login_fails(body.email)
    raw, h, exp = A.new_refresh()
    await db.execute(text(
        "INSERT INTO refresh_tokens (user_id, token_hash, expires_at)"
        " VALUES (:u, :h, :x)"), {"u": r.id, "h": h, "x": exp})
    await db.commit()

    A.set_refresh_cookie(resp, raw)
    return {"accessToken": A.make_access(r.id, r.role),
            "user": {"id": r.id, "email": body.email, "role": r.role,
                     "mustChangePassword": r.must_change_password}}


@router.post("/auth/refresh")
async def refresh(resp: Response, raw: str = Depends(A.refresh_cookie),
                  db: AsyncSession = Depends(get_db)):
    r = (await db.execute(text("""
        SELECT t.id, t.user_id, u.role, u.email, u.must_change_password
          FROM refresh_tokens t JOIN users u ON u.id = t.user_id
         WHERE t.token_hash = :h AND t.revoked_at IS NULL AND t.expires_at > now()
    """), {"h": A.refresh_hash(raw)})).first()
    if not r:
        A.clear_refresh_cookie(resp)
        raise HTTPException(401, "세션이 만료되었습니다")

    return {"accessToken": A.make_access(r.user_id, r.role),
            "user": {"id": r.user_id, "email": r.email, "role": r.role,
                     "mustChangePassword": r.must_change_password}}


@router.post("/auth/logout")
async def logout(resp: Response, raw: str | None = Depends(A.refresh_cookie),
                 db: AsyncSession = Depends(get_db)):
    # FR-14 — 서버에서 무효화한다. 쿠키만 지우면 재사용이 가능하다.
    await db.execute(text(
        "UPDATE refresh_tokens SET revoked_at = now() WHERE token_hash = :h"),
        {"h": A.refresh_hash(raw)})
    await db.commit()
    A.clear_refresh_cookie(resp)
    return {"ok": True}


@router.post("/auth/password")
async def change_password(body: PasswordChange, user: dict = Depends(A.current_user),
                          db: AsyncSession = Depends(get_db)):
    A.check_password_policy(body.newPassword)
    cur = (await db.execute(text("SELECT password_hash FROM users WHERE id = :i"),
                            {"i": user["id"]})).scalar()
    if not A.verify_password(cur, body.currentPassword):
        raise HTTPException(401, "현재 비밀번호가 올바르지 않습니다")

    await db.execute(text(
        "UPDATE users SET password_hash = :p, must_change_password = false WHERE id = :i"),
        {"p": A.hash_password(body.newPassword), "i": user["id"]})
    # 비밀번호를 바꾸면 기존 세션을 전부 끊는다
    await db.execute(text(
        "UPDATE refresh_tokens SET revoked_at = now()"
        " WHERE user_id = :i AND revoked_at IS NULL"), {"i": user["id"]})
    await db.commit()
    return {"ok": True}


@router.get("/auth/me", response_model=MeOut)
async def me(user: dict = Depends(A.current_user)):
    return MeOut(**user)


@router.delete("/auth/me")
async def delete_me(resp: Response, user: dict = Depends(A.active_user),
                    db: AsyncSession = Depends(get_db)):
    # FR-16 — 즉시 삭제. CASCADE 로 키워드·토큰도 함께 지워진다.
    await db.execute(text("DELETE FROM users WHERE id = :i"), {"i": user["id"]})
    await db.commit()
    A.clear_refresh_cookie(resp)
    return {"ok": True}


# ───────────────────── 구독 키워드 · 피드 ─────────────────────


@router.get("/me/keywords")
async def get_keywords(user: dict = Depends(A.active_user),
                       db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT keyword FROM user_keywords WHERE user_id = :i ORDER BY created_at"),
        {"i": user["id"]})).scalars().all()
    return {"keywords": list(rows), "max": A.MAX_KEYWORDS}


@router.put("/me/keywords")
async def put_keywords(body: Keywords, user: dict = Depends(A.active_user),
                       db: AsyncSession = Depends(get_db)):
    kws = [k.strip() for k in body.keywords if k.strip()]
    kws = list(dict.fromkeys(kws))  # 중복 제거, 순서 유지
    if len(kws) > A.MAX_KEYWORDS:  # FR-15 — 서버에서 강제
        raise HTTPException(400, f"구독 키워드는 최대 {A.MAX_KEYWORDS}개입니다")
    if any(len(k) < 2 for k in kws):
        raise HTTPException(400, "키워드는 2글자 이상이어야 합니다")

    await db.execute(text("DELETE FROM user_keywords WHERE user_id = :i"),
                     {"i": user["id"]})
    for k in kws:
        await db.execute(text(
            "INSERT INTO user_keywords (user_id, keyword) VALUES (:i, :k)"),
            {"i": user["id"], "k": k})
    await db.commit()
    return {"keywords": kws, "max": A.MAX_KEYWORDS}


@router.get("/me/feed", response_model=ListOut)
async def feed(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100),
               user: dict = Depends(A.active_user), db: AsyncSession = Depends(get_db)):
    """구독 키워드 피드.

    🔴 별도 매칭 엔진을 만들지 않는다. 검색과 같은 질의 경로를 쓴다 (PRD-01 §3.2).
    """
    kws = (await db.execute(text(
        "SELECT keyword FROM user_keywords WHERE user_id = :i"),
        {"i": user["id"]})).scalars().all()

    if not kws:
        return ListOut(items=[], total=0, page=page, size=size,
                       appliedScope="구독 키워드가 없습니다")

    conds, params = [], {"limit": size, "offset": (page - 1) * size}
    for n, k in enumerate(kws):
        conds.append(f"(search_ko LIKE :k{n} OR search_en ILIKE :k{n})")
        params[f"k{n}"] = f"%{k}%"
    w = " WHERE " + " OR ".join(conds)

    total = (await db.execute(text(f"SELECT count(*) FROM contents{w}"), params)).scalar() or 0
    rows = (await db.execute(text(
        f"SELECT {queries.CARD_COLS} FROM contents{w}"
        " ORDER BY collected_at DESC, id DESC LIMIT :limit OFFSET :offset"), params)).all()

    return ListOut(items=[to_card(r) for r in rows], total=total, page=page, size=size,
                   appliedScope=f"구독 키워드 {len(kws)}개: {', '.join(kws)}")


# ───────────────────────── 관리자 ─────────────────────────


@router.get("/admin/sources")
async def admin_sources(_: dict = Depends(A.admin_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT id, kind, name, url, category, enabled FROM sources ORDER BY kind, name"))).all()
    return {"sources": [dict(r._mapping) for r in rows]}


@router.put("/admin/sources/{source_id}")
async def admin_toggle_source(source_id: int, enabled: bool,
                              _: dict = Depends(A.admin_user),
                              db: AsyncSession = Depends(get_db)):
    r = (await db.execute(text(
        "UPDATE sources SET enabled = :e WHERE id = :i RETURNING id"),
        {"e": enabled, "i": source_id})).first()
    if not r:
        raise HTTPException(404, "소스를 찾을 수 없습니다")
    await db.commit()
    return {"ok": True}


@router.get("/admin/batches")
async def admin_batches(limit: int = Query(20, ge=1, le=100),
                        _: dict = Depends(A.admin_user),
                        db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text(
        "SELECT id, started_at, finished_at, status, stats FROM batch_runs"
        " ORDER BY id DESC LIMIT :n"), {"n": limit})).all()
    fails = (await db.execute(text(
        "SELECT count(*) FROM translation_jobs WHERE status = 'failed'"))).scalar()
    return {"batches": [dict(r._mapping) for r in rows], "translationFailed": fails}


@router.post("/admin/translations/retry")
async def admin_retry(_: dict = Depends(A.admin_user), db: AsyncSession = Depends(get_db)):
    """실패한 번역을 수동 재시도 큐에 되돌린다 (PRD-03 FR-47)."""
    n = (await db.execute(text(
        "UPDATE translation_jobs SET status='pending', attempts=0, last_error=NULL"
        " WHERE status='failed'"))).rowcount
    await db.commit()
    return {"requeued": n}
