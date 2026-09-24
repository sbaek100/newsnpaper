"""가입 승인 + 이메일 인증 — PRD-01 §5 (2026-09-24 정정)

Revision ID: 0002
Revises: 0001
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE users
            ADD COLUMN status varchar(20) NOT NULL DEFAULT 'active',
            ADD COLUMN email_verified_at timestamptz,
            ADD CONSTRAINT ck_user_status CHECK (
                status IN ('pending_email','pending_approval','active','rejected'));
    """)
    # 이미 있던 계정(관리자 시드 등)은 active 로 둔다.
    op.execute("UPDATE users SET status='active', email_verified_at=now()")

    # 이메일 인증 토큰. 원본은 메일로만 나가고 DB 에는 해시만 둔다 (FR-18).
    op.execute("""
        CREATE TABLE email_tokens (
            id         bigserial PRIMARY KEY,
            user_id    bigint      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash text        NOT NULL UNIQUE,
            purpose    varchar(20) NOT NULL DEFAULT 'verify',
            expires_at timestamptz NOT NULL,
            used_at    timestamptz,
            created_at timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_email_tokens_user ON email_tokens (user_id, purpose);")


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS email_tokens CASCADE;")
    op.execute("""
        ALTER TABLE users
            DROP CONSTRAINT IF EXISTS ck_user_status,
            DROP COLUMN IF EXISTS status,
            DROP COLUMN IF EXISTS email_verified_at;
    """)
