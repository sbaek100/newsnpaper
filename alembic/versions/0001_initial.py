"""초기 스키마 — 8테이블 + 검색 색인

Revision ID: 0001
Revises:
"""
from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 확장 ──
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm;")

    # ── IMMUTABLE 헬퍼 ──
    # 생성 컬럼은 IMMUTABLE 식만 허용한다. sections(JSONB)에서 텍스트를 뽑는
    # 서브쿼리는 그대로 못 쓰므로 함수로 감싼다 (PRD-05 §10.1 D-14~15).
    # coalesce 로 NULL 입력에 안전하게 한다 (D-18).
    op.execute("""
        CREATE OR REPLACE FUNCTION sections_ko_text(secs jsonb)
        RETURNS text AS $$
          SELECT coalesce(
            (SELECT string_agg(x->>'textKo', ' ')
             FROM jsonb_array_elements(coalesce(secs, '[]'::jsonb)) x),
            '')
        $$ LANGUAGE sql IMMUTABLE;
    """)
    op.execute("""
        CREATE OR REPLACE FUNCTION sections_en_text(secs jsonb)
        RETURNS text AS $$
          SELECT coalesce(
            (SELECT string_agg(x->>'textOriginal', ' ')
             FROM jsonb_array_elements(coalesce(secs, '[]'::jsonb)) x),
            '')
        $$ LANGUAGE sql IMMUTABLE;
    """)

    # ── contents ──
    op.execute("""
        CREATE TABLE contents (
            id                      bigserial PRIMARY KEY,
            type                    varchar(16)  NOT NULL,
            category                varchar(32)  NOT NULL,
            source_url              text         NOT NULL UNIQUE,
            collected_at            timestamptz  NOT NULL DEFAULT now(),
            language                varchar(8),
            title_original          text         NOT NULL,
            title_ko                text,
            translation_status      varchar(16)  NOT NULL DEFAULT 'pending',
            matched_keywords        text[]       NOT NULL DEFAULT '{}',
            thumbnail_url           text,

            summary_original        text,
            summary_ko              text,

            authors                 text[],
            venue                   text,
            published_at            timestamptz,
            doi                     text,
            arxiv_id                text,
            pdf_url                 text,
            sections                jsonb,
            section_extract_status  varchar(16),
            -- 저장 전 200,000자로 자른다 (PRD-03 FR-52). 애플리케이션 책임.
            full_text_original      text,
            full_text_status        varchar(16),

            search_ko text GENERATED ALWAYS AS (
                coalesce(title_ko, '') || ' ' ||
                coalesce(summary_ko, '') || ' ' ||
                sections_ko_text(sections)
            ) STORED,
            search_en text GENERATED ALWAYS AS (
                coalesce(title_original, '') || ' ' ||
                coalesce(summary_original, '') || ' ' ||
                sections_en_text(sections) || ' ' ||
                coalesce(full_text_original, '')
            ) STORED,

            CONSTRAINT ck_contents_type
                CHECK (type IN ('news','paper')),
            CONSTRAINT ck_contents_translation_status
                CHECK (translation_status IN ('pending','done','failed','skipped')),
            CONSTRAINT ck_contents_section_status
                CHECK (section_extract_status IS NULL
                       OR section_extract_status IN ('full','abstract_only','failed')),
            CONSTRAINT ck_contents_fulltext_status
                CHECK (full_text_status IS NULL
                       OR full_text_status IN ('indexed','no_pdf','extract_failed'))
        );
    """)

    op.execute("CREATE INDEX ix_contents_type_collected ON contents (type, collected_at DESC);")
    op.execute("CREATE INDEX ix_contents_collected ON contents (collected_at DESC);")
    op.execute("CREATE INDEX ix_contents_matched_keywords ON contents USING gin (matched_keywords);")
    op.execute("CREATE UNIQUE INDEX uq_contents_doi ON contents (doi) WHERE doi IS NOT NULL;")
    op.execute("CREATE UNIQUE INDEX uq_contents_arxiv_id ON contents (arxiv_id) WHERE arxiv_id IS NOT NULL;")
    # 한국어: pg_bigm 2그램 (PRD-05 FR-19)
    op.execute("CREATE INDEX ix_contents_search_ko ON contents USING gin (search_ko gin_bigm_ops);")
    # 영어: tsvector (FR-20)
    op.execute("CREATE INDEX ix_contents_search_en ON contents USING gin (to_tsvector('english', search_en));")

    # ── translation_jobs ──
    op.execute("""
        CREATE TABLE translation_jobs (
            id          bigserial PRIMARY KEY,
            content_id  bigint      NOT NULL REFERENCES contents(id) ON DELETE CASCADE,
            field       varchar(64) NOT NULL,
            status      varchar(16) NOT NULL DEFAULT 'pending',
            attempts    integer     NOT NULL DEFAULT 0,
            last_error  text,
            created_at  timestamptz NOT NULL DEFAULT now(),
            started_at  timestamptz,
            finished_at timestamptz,
            CONSTRAINT uq_translation_job UNIQUE (content_id, field),
            CONSTRAINT ck_job_status CHECK (status IN ('pending','running','done','failed'))
        );
    """)
    op.execute("CREATE INDEX ix_translation_jobs_queue ON translation_jobs (status, created_at);")

    # ── batch_runs ──
    op.execute("""
        CREATE TABLE batch_runs (
            id          bigserial PRIMARY KEY,
            started_at  timestamptz NOT NULL DEFAULT now(),
            finished_at timestamptz,
            status      varchar(16) NOT NULL DEFAULT 'running',
            stats       jsonb
        );
    """)

    # ── sources ──
    op.execute("""
        CREATE TABLE sources (
            id         bigserial PRIMARY KEY,
            kind       varchar(16) NOT NULL,
            name       text        NOT NULL,
            url        text        NOT NULL,
            category   varchar(32) NOT NULL,
            enabled    boolean     NOT NULL DEFAULT true,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_source UNIQUE (kind, name),
            CONSTRAINT ck_source_kind CHECK (kind IN ('rss','api','arxiv'))
        );
    """)

    # ── users ──
    op.execute("""
        CREATE TABLE users (
            id                   bigserial PRIMARY KEY,
            email                text        NOT NULL UNIQUE,
            password_hash        text        NOT NULL,
            role                 varchar(16) NOT NULL DEFAULT 'member',
            must_change_password boolean     NOT NULL DEFAULT false,
            created_at           timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT ck_user_role CHECK (role IN ('member','admin'))
        );
    """)

    op.execute("""
        CREATE TABLE user_keywords (
            id         bigserial PRIMARY KEY,
            user_id    bigint      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            keyword    text        NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            CONSTRAINT uq_user_keyword UNIQUE (user_id, keyword)
        );
    """)

    op.execute("""
        CREATE TABLE refresh_tokens (
            id         bigserial PRIMARY KEY,
            user_id    bigint      NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash text        NOT NULL UNIQUE,
            expires_at timestamptz NOT NULL,
            revoked_at timestamptz
        );
    """)

    # ── search_logs ──
    # 🔴 회원 식별자를 두지 않는다 (PRD-02 FR-19)
    op.execute("""
        CREATE TABLE search_logs (
            id           bigserial PRIMARY KEY,
            query        text        NOT NULL,
            result_count integer     NOT NULL,
            created_at   timestamptz NOT NULL DEFAULT now()
        );
    """)
    op.execute("CREATE INDEX ix_search_logs_created ON search_logs (created_at);")


def downgrade() -> None:
    for t in (
        "search_logs",
        "refresh_tokens",
        "user_keywords",
        "users",
        "sources",
        "batch_runs",
        "translation_jobs",
        "contents",
    ):
        op.execute(f"DROP TABLE IF EXISTS {t} CASCADE;")
    op.execute("DROP FUNCTION IF EXISTS sections_ko_text(jsonb);")
    op.execute("DROP FUNCTION IF EXISTS sections_en_text(jsonb);")
