"""인증·회원·관리자 엔드포인트 — PRD-01 §7"""

import hashlib
import secrets as pysecrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.config import settings
from shared.db import get_db
from shared.logging import get_logger

from . import auth as A
from . import mailer
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




VERIFY_TTL_H = 24  # FR-18


def _status_message(status: str) -> str:
    return {
        "pending_email": "이메일 인증이 아직 끝나지 않았습니다. 메일의 링크를 눌러주세요.",
        "pending_approval": "이메일 인증이 끝났습니다. 관리자 승인을 기다리는 중입니다.",
        "rejected": "가입이 거부된 계정입니다. 관리자에게 문의하세요.",
    }.get(status, "로그인할 수 없는 계정입니다.")


async def _issue_verify_token(db, user_id: int) -> str:
    """원본은 메일로만 나가고 DB 에는 해시만 둔다 (FR-18)."""
    raw = pysecrets.token_urlsafe(32)
    await db.execute(text(
        "UPDATE email_tokens SET used_at = now()"
        " WHERE user_id = :u AND purpose = 'verify' AND used_at IS NULL"), {"u": user_id})
    await db.execute(text(
        "INSERT INTO email_tokens (user_id, token_hash, purpose, expires_at)"
        " VALUES (:u, :h, 'verify', :x)"),
        {"u": user_id, "h": hashlib.sha256(raw.encode()).hexdigest(),
         "x": datetime.now(timezone.utc) + timedelta(hours=VERIFY_TTL_H)})
    return raw


# ───────────────────────── 인증 ─────────────────────────


@router.post("/auth/signup")
async def signup(body: Credentials, db: AsyncSession = Depends(get_db)):
    """가입 신청. 바로 로그인되지 않는다 — 이메일 인증 + 관리자 승인을 거친다 (FR-17)."""
    A.check_password_policy(body.password)
    dup = (await db.execute(text("SELECT 1 FROM users WHERE email = :e"),
                            {"e": body.email})).first()
    if dup:
        raise HTTPException(409, "이미 가입 신청되었거나 사용 중인 이메일입니다")

    uid = (await db.execute(text(
        "INSERT INTO users (email, password_hash, role, status)"
        " VALUES (:e, :p, 'member', 'pending_email') RETURNING id"
    ), {"e": body.email, "p": A.hash_password(body.password)})).scalar()

    raw = await _issue_verify_token(db, uid)
    await db.commit()

    link = f"{settings.site_url}/verify?token={raw}"
    subject, text_body = mailer.verify_mail(link)
    sent = await mailer.send(body.email, subject, text_body)

    # FR-24 — 메일이 안 나가도 가입은 성공시킨다. 재발송으로 복구한다.
    return {"status": "pending_email", "mailSent": sent,
            "message": "인증 메일을 보냈습니다. 메일의 링크를 눌러주세요."
                       if sent else
                       "가입 신청은 접수됐으나 메일 발송에 실패했습니다. 재발송하거나 관리자에게 문의하세요."}


@router.post("/auth/resend")
async def resend_verify(body: Credentials, db: AsyncSession = Depends(get_db)):
    """인증 메일 재발송 (FR-22). 비밀번호를 확인해 타인의 재발송을 막는다."""
    r = (await db.execute(text(
        "SELECT id, password_hash, status FROM users WHERE email = :e"),
        {"e": body.email})).first()
    # 계정 존재 여부를 알려주지 않는다
    if not r or not A.verify_password(r.password_hash, body.password) \
            or r.status != "pending_email":
        return {"ok": True}

    raw = await _issue_verify_token(db, r.id)
    await db.commit()
    subject, text_body = mailer.verify_mail(f"{settings.site_url}/verify?token={raw}")
    await mailer.send(body.email, subject, text_body)
    return {"ok": True}


@router.post("/auth/verify")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    """인증 링크 처리 → pending_approval (FR-19)."""
    r = (await db.execute(text("""
        SELECT t.id, t.user_id, u.status FROM email_tokens t
          JOIN users u ON u.id = t.user_id
         WHERE t.token_hash = :h AND t.purpose = 'verify'
           AND t.used_at IS NULL AND t.expires_at > now()
    """), {"h": hashlib.sha256(token.encode()).hexdigest()})).first()
    if not r:
        raise HTTPException(400, "유효하지 않거나 만료된 링크입니다. 인증 메일을 다시 받아주세요")

    await db.execute(text("UPDATE email_tokens SET used_at = now() WHERE id = :i"),
                     {"i": r.id})
    if r.status == "pending_email":
        await db.execute(text(
            "UPDATE users SET status = 'pending_approval', email_verified_at = now()"
            " WHERE id = :i"), {"i": r.user_id})
    await db.commit()
    return {"status": "pending_approval",
            "message": "이메일 인증이 끝났습니다. 관리자 승인 후 로그인할 수 있습니다."}


@router.post("/auth/login")
async def login(body: Credentials, resp: Response, db: AsyncSession = Depends(get_db)):
    if A.login_blocked(body.email):
        raise HTTPException(429, "로그인 시도가 너무 많습니다. 10분 후 다시 시도하세요")

    r = (await db.execute(text(
        "SELECT id, password_hash, role, must_change_password, status"
        " FROM users WHERE email = :e"
    ), {"e": body.email})).first()

    if not r or not A.verify_password(r.password_hash, body.password):
        A.note_login_fail(body.email)
        raise HTTPException(401, "이메일 또는 비밀번호가 올바르지 않습니다")

    # FR-21 — active 가 아니면 현재 상태를 알려준다
    if r.status != "active":
        raise HTTPException(403, _status_message(r.status))

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


# ───────────────────── 관리자: 가입 승인 (FR-20) ─────────────────────


@router.get("/admin/signups")
async def admin_signups(_: dict = Depends(A.admin_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(text("""
        SELECT id, email, status, created_at, email_verified_at
          FROM users
         WHERE status IN ('pending_email','pending_approval','rejected')
         ORDER BY created_at DESC
    """))).all()
    return {"signups": [dict(r._mapping) for r in rows]}


@router.post("/admin/signups/{user_id}/approve")
async def admin_approve(user_id: int, _: dict = Depends(A.admin_user),
                        db: AsyncSession = Depends(get_db)):
    r = (await db.execute(text("""
        UPDATE users SET status = 'active'
         WHERE id = :i AND status IN ('pending_approval','rejected')
         RETURNING email
    """), {"i": user_id})).first()
    if not r:
        raise HTTPException(400, "이메일 인증을 마친 신청만 승인할 수 있습니다")
    await db.commit()

    subject, body = mailer.approved_mail(settings.site_url)
    await mailer.send(r.email, subject, body)
    return {"ok": True, "status": "active"}


@router.post("/admin/signups/{user_id}/reject")
async def admin_reject(user_id: int, _: dict = Depends(A.admin_user),
                       db: AsyncSession = Depends(get_db)):
    r = (await db.execute(text(
        "UPDATE users SET status = 'rejected' WHERE id = :i AND role <> 'admin'"
        " RETURNING id"), {"i": user_id})).first()
    if not r:
        raise HTTPException(400, "거부할 수 없는 계정입니다")
    # 거부하면 기존 세션을 끊는다
    await db.execute(text(
        "UPDATE refresh_tokens SET revoked_at = now()"
        " WHERE user_id = :i AND revoked_at IS NULL"), {"i": user_id})
    await db.commit()
    return {"ok": True, "status": "rejected"}
