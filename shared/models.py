"""SQLAlchemy 2.0 모델 — architecture.md §8, PRD-03 §6, PRD-05 §10.1

검색 색인(search_ko / search_en)은 생성 컬럼이다.
sections(JSONB)에서 텍스트를 뽑는 IMMUTABLE 헬퍼 함수가 필요하며,
함수 정의는 Alembic 마이그레이션에 있다.
"""

from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    Computed,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


# 생성 컬럼 식. sections_ko_text / sections_en_text 는 마이그레이션에서 만든다.
_SEARCH_KO = (
    "coalesce(title_ko, '') || ' ' || "
    "coalesce(summary_ko, '') || ' ' || "
    "sections_ko_text(sections)"
)
_SEARCH_EN = (
    "coalesce(title_original, '') || ' ' || "
    "coalesce(summary_original, '') || ' ' || "
    "sections_en_text(sections) || ' ' || "
    "coalesce(full_text_original, '')"
)


class Content(Base):
    """뉴스·논문 통합 테이블.

    목록·검색이 둘을 섞어 조회하므로(PRD-06 §9.2) 한 테이블에 둔다.
    분리하면 UNION이 상시 필요해진다.
    """

    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(primary_key=True)

    # ── 공통 ──
    type: Mapped[str] = mapped_column(String(16))  # news | paper
    category: Mapped[str] = mapped_column(String(32))  # international | domestic | paper
    source_url: Mapped[str] = mapped_column(Text, unique=True)  # D-1 dedup 1차 키
    collected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    language: Mapped[str | None] = mapped_column(String(8))
    title_original: Mapped[str] = mapped_column(Text)
    title_ko: Mapped[str | None] = mapped_column(Text)
    translation_status: Mapped[str] = mapped_column(String(16), default="pending")
    matched_keywords: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default="{}"
    )
    thumbnail_url: Mapped[str | None] = mapped_column(Text)

    # ── 뉴스 ──
    summary_original: Mapped[str | None] = mapped_column(Text)
    summary_ko: Mapped[str | None] = mapped_column(Text)

    # ── 논문 ──
    authors: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    venue: Mapped[str | None] = mapped_column(Text)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    doi: Mapped[str | None] = mapped_column(Text)
    arxiv_id: Mapped[str | None] = mapped_column(Text)
    pdf_url: Mapped[str | None] = mapped_column(Text)
    sections: Mapped[list | None] = mapped_column(JSONB)
    section_extract_status: Mapped[str | None] = mapped_column(String(16))
    # D-9: 저장 전 200,000자로 자른다 (PRD-03 FR-52). 애플리케이션 책임.
    full_text_original: Mapped[str | None] = mapped_column(Text)
    full_text_status: Mapped[str | None] = mapped_column(String(16))

    # ── 검색 색인 (생성 컬럼, STORED) ──
    search_ko: Mapped[str] = mapped_column(Text, Computed(_SEARCH_KO, persisted=True))
    search_en: Mapped[str] = mapped_column(Text, Computed(_SEARCH_EN, persisted=True))

    __table_args__ = (
        Index("ix_contents_type_collected", "type", "collected_at"),  # D-7
        Index(
            "ix_contents_matched_keywords",
            "matched_keywords",
            postgresql_using="gin",
        ),  # D-8
        # D-2: 논문 dedup 우선 키. NULL 허용 부분 유니크.
        Index(
            "uq_contents_doi",
            "doi",
            unique=True,
            postgresql_where=doi.isnot(None),
        ),
        Index(
            "uq_contents_arxiv_id",
            "arxiv_id",
            unique=True,
            postgresql_where=arxiv_id.isnot(None),
        ),
        # D-19 / D-20: 검색 인덱스
        Index(
            "ix_contents_search_ko",
            "search_ko",
            postgresql_using="gin",
            postgresql_ops={"search_ko": "gin_bigm_ops"},
        ),
        Index(
            "ix_contents_search_en",
            func.to_tsvector("english", "search_en"),
            postgresql_using="gin",
        ),
    )


class TranslationJob(Base):
    """번역 큐. FOR UPDATE SKIP LOCKED 로 소비한다 (architecture.md §7.3)."""

    __tablename__ = "translation_jobs"

    id: Mapped[int] = mapped_column(primary_key=True)
    content_id: Mapped[int] = mapped_column(
        ForeignKey("contents.id", ondelete="CASCADE")
    )
    # title | summary | section:Abstract | section:Introduction | section:Conclusion
    field: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_translation_jobs_queue", "status", "created_at"),  # D-10
        UniqueConstraint("content_id", "field", name="uq_translation_job"),
    )


class BatchRun(Base):
    """배치 실행 이력. 소스별 성공/실패와 품질 지표를 stats 에 담는다."""

    __tablename__ = "batch_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), default="running")
    stats: Mapped[dict | None] = mapped_column(JSONB)


class Source(Base):
    """수집 소스. 관리자가 변경한다 (PRD-01 FR-3, PRD-03 FR-37)."""

    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(16))  # rss | api | arxiv
    name: Mapped[str] = mapped_column(Text)
    url: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (UniqueConstraint("kind", "name", name="uq_source"),)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default="member")  # member | admin
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    keywords: Mapped[list["UserKeyword"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    tokens: Mapped[list["RefreshToken"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserKeyword(Base):
    """구독 키워드. 회원당 20개 상한은 애플리케이션에서 강제한다 (PRD-01 FR-15)."""

    __tablename__ = "user_keywords"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    keyword: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="keywords")

    __table_args__ = (UniqueConstraint("user_id", "keyword", name="uq_user_keyword"),)


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    token_hash: Mapped[str] = mapped_column(Text, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="tokens")


class SearchLog(Base):
    """검색어 로그.

    🔴 회원 식별자를 두지 않는다 (PRD-02 FR-19). FK 도 두지 않는다.
    30일 후 삭제한다 (FR-20).
    """

    __tablename__ = "search_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    query: Mapped[str] = mapped_column(Text)
    result_count: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (Index("ix_search_logs_created", "created_at"),)
