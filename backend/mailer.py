"""SMTP 메일 발송 — PRD-01 FR-23·FR-24

자격증명은 secrets/smtp_password 에서 읽는다. 로그에 남기지 않는다.
발송 실패가 가입 자체를 막지 않는다 — 재발송으로 복구한다 (FR-24).
"""

import asyncio
import smtplib
import ssl
from email.message import EmailMessage

from shared.config import settings
from shared.logging import get_logger

logger = get_logger("backend.mailer")


def configured() -> bool:
    return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)


def _send_sync(to: str, subject: str, body: str) -> None:
    msg = EmailMessage()
    msg["From"] = settings.smtp_from or settings.smtp_user
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    ctx = ssl.create_default_context()
    if settings.smtp_port == 465:
        with smtplib.SMTP_SSL(settings.smtp_host, 465, context=ctx, timeout=20) as s:
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)
    else:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as s:
            s.starttls(context=ctx)
            s.login(settings.smtp_user, settings.smtp_password)
            s.send_message(msg)


async def send(to: str, subject: str, body: str) -> bool:
    """성공 여부만 반환한다. 예외를 밖으로 던지지 않는다 (FR-24)."""
    if not configured():
        logger.warning("SMTP 미설정 — 메일을 보내지 않는다", {"to_domain": to.split("@")[-1]})
        return False
    try:
        # smtplib 은 동기다. 이벤트 루프를 막지 않게 스레드로 보낸다.
        await asyncio.to_thread(_send_sync, to, subject, body)
        logger.info("메일 발송", {"to_domain": to.split("@")[-1], "subject": subject})
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning("메일 발송 실패", {"error": f"{type(e).__name__}: {e}"[:200]})
        return False


def verify_mail(link: str) -> tuple[str, str]:
    return (
        "[secubrief] 이메일 인증",
        "secubrief 가입 신청을 받았습니다.\n\n"
        "아래 링크를 눌러 이메일을 인증해 주세요. 24시간 후 만료됩니다.\n\n"
        f"{link}\n\n"
        "인증 후에는 관리자 승인을 거쳐야 로그인할 수 있습니다.\n"
        "본인이 신청하지 않았다면 이 메일을 무시하세요.\n",
    )


def approved_mail(base: str) -> tuple[str, str]:
    return (
        "[secubrief] 가입이 승인되었습니다",
        f"관리자가 가입을 승인했습니다. 이제 로그인할 수 있습니다.\n\n{base}/login\n",
    )
