"""Initial migration

Revision ID: 001
Revises: 
Create Date: 2026-09-23 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    # 1. Extension
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_bigm;")

    # 2. Immutable functions for JSONB extraction
    op.execute("""
    CREATE OR REPLACE FUNCTION extract_text_ko(sections JSONB) RETURNS TEXT AS $$
    DECLARE
        result TEXT := '';
        elem JSONB;
    BEGIN
        IF sections IS NULL THEN
            RETURN '';
        END IF;
        FOR elem IN SELECT * FROM jsonb_array_elements(sections) LOOP
            IF elem->>'textKo' IS NOT NULL THEN
                result := result || ' ' || (elem->>'textKo');
            END IF;
        END LOOP;
        RETURN trim(result);
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    op.execute("""
    CREATE OR REPLACE FUNCTION extract_text_original(sections JSONB) RETURNS TEXT AS $$
    DECLARE
        result TEXT := '';
        elem JSONB;
    BEGIN
        IF sections IS NULL THEN
            RETURN '';
        END IF;
        FOR elem IN SELECT * FROM jsonb_array_elements(sections) LOOP
            IF elem->>'textOriginal' IS NOT NULL THEN
                result := result || ' ' || (elem->>'textOriginal');
            END IF;
        END LOOP;
        RETURN trim(result);
    END;
    $$ LANGUAGE plpgsql IMMUTABLE;
    """)

    # 3. Create tables
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )

    op.create_table('sources',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('url', sa.String(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('search_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('query', sa.String(), nullable=False),
        sa.Column('result_count', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('batch_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('stats', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('refresh_tokens',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table('user_keywords',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('keyword', sa.String(length=100), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'keyword', name='uq_user_keywords_user_id_keyword')
    )

    op.create_table('contents',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=False),
        sa.Column('category', sa.String(length=255), nullable=True),
        sa.Column('source_url', sa.String(), nullable=False),
        sa.Column('collected_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('language', sa.String(length=50), nullable=True),
        sa.Column('title_original', sa.String(), nullable=True),
        sa.Column('title_ko', sa.String(), nullable=True),
        sa.Column('translation_status', sa.String(length=50), nullable=True),
        sa.Column('matched_keywords', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('thumbnail_url', sa.String(), nullable=True),
        sa.Column('summary_original', sa.Text(), nullable=True),
        sa.Column('summary_ko', sa.Text(), nullable=True),
        sa.Column('authors', postgresql.ARRAY(sa.String()), nullable=True),
        sa.Column('venue', sa.String(), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('doi', sa.String(), nullable=True),
        sa.Column('arxiv_id', sa.String(), nullable=True),
        sa.Column('pdf_url', sa.String(), nullable=True),
        sa.Column('sections', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('section_extract_status', sa.String(length=50), nullable=True),
        sa.Column('full_text_original', sa.Text(), comment='Max 200,000 chars before saving', nullable=True),
        sa.Column('full_text_status', sa.String(length=50), nullable=True),
        
        # Generated columns
        sa.Column('search_ko', sa.Text(), sa.Computed("coalesce(title_ko, '') || ' ' || coalesce(summary_ko, '') || ' ' || coalesce(extract_text_ko(sections), '')", persisted=True), nullable=True),
        sa.Column('search_en', sa.Text(), sa.Computed("coalesce(title_original, '') || ' ' || coalesce(summary_original, '') || ' ' || coalesce(extract_text_original(sections), '') || ' ' || coalesce(full_text_original, '')", persisted=True), nullable=True),
        
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source_url')
    )

    op.create_index('ix_contents_type_collected_at', 'contents', ['type', sa.text('collected_at DESC')])
    op.create_index('ix_contents_matched_keywords', 'contents', ['matched_keywords'], postgresql_using='gin')
    op.create_index('ix_contents_doi', 'contents', ['doi'], unique=True, postgresql_where=sa.text('doi IS NOT NULL'))
    op.create_index('ix_contents_arxiv_id', 'contents', ['arxiv_id'], unique=True, postgresql_where=sa.text('arxiv_id IS NOT NULL'))
    
    # Custom pg_bigm index
    op.execute("CREATE INDEX ix_contents_search_ko_bigm ON contents USING gin (search_ko gin_bigm_ops);")
    # Custom tsvector index
    op.execute("CREATE INDEX ix_contents_search_en_tsvector ON contents USING gin (to_tsvector('english', search_en));")

    op.create_table('translation_jobs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content_id', sa.Integer(), nullable=False),
        sa.Column('field', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['content_id'], ['contents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_translation_jobs_status_created_at', 'translation_jobs', ['status', 'created_at'])

def downgrade() -> None:
    op.drop_table('translation_jobs')
    op.drop_table('contents')
    op.drop_table('user_keywords')
    op.drop_table('refresh_tokens')
    op.drop_table('batch_runs')
    op.drop_table('search_logs')
    op.drop_table('sources')
    op.drop_table('users')
    
    op.execute("DROP FUNCTION IF EXISTS extract_text_ko(JSONB);")
    op.execute("DROP FUNCTION IF EXISTS extract_text_original(JSONB);")
    # pg_bigm extension can remain or be dropped, but standard practice is to leave extensions
    # op.execute("DROP EXTENSION IF EXISTS pg_bigm;")
