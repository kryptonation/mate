"""Added document id and signature mode

Revision ID: 522ce2335e76
Revises: d02249b05077
Create Date: 2025-09-29 14:56:47.157408

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = "522ce2335e76"
down_revision: Union[str, Sequence[str], None] = "d02249b05077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _exec(sql: str):
    # tiny helper so we can keep statements tidy
    op.execute(sql)


def upgrade():
    # document_id
    _exec("""
        SET @sql := (
            SELECT IF(COUNT(*) = 0,
                'ALTER TABLE lease_driver_documents ADD COLUMN document_id INT NULL COMMENT ''Associated document ID''' ,
                'SELECT 1')
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'lease_driver_documents'
              AND column_name = 'document_id'
        );
    """)
    _exec("PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;")

    # signing_type
    _exec("""
        SET @sql := (
            SELECT IF(COUNT(*) = 0,
                'ALTER TABLE lease_driver_documents ADD COLUMN signing_type VARCHAR(32) NULL COMMENT ''Signature mode (free text)''' ,
                'SELECT 1')
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'lease_driver_documents'
              AND column_name = 'signing_type'
        );
    """)
    _exec("PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;")

    # index on document_id
    _exec("""
        SET @sql := (
            SELECT IF(COUNT(*) = 0,
                'CREATE INDEX ix_lease_driver_documents_document_id ON lease_driver_documents (document_id)',
                'SELECT 1')
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'lease_driver_documents'
              AND index_name = 'ix_lease_driver_documents_document_id'
        );
    """)
    _exec("PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;")


def downgrade():
    # drop index if present
    _exec("""
        SET @sql := (
            SELECT IF(COUNT(*) > 0,
                'DROP INDEX ix_lease_driver_documents_document_id ON lease_driver_documents',
                'SELECT 1')
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'lease_driver_documents'
              AND index_name = 'ix_lease_driver_documents_document_id'
        );
    """)
    _exec("PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;")

    # drop signing_type if present
    _exec("""
        SET @sql := (
            SELECT IF(COUNT(*) > 0,
                'ALTER TABLE lease_driver_documents DROP COLUMN signing_type',
                'SELECT 1')
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'lease_driver_documents'
              AND column_name = 'signing_type'
        );
    """)
    _exec("PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;")

    # drop document_id if present
    _exec("""
        SET @sql := (
            SELECT IF(COUNT(*) > 0,
                'ALTER TABLE lease_driver_documents DROP COLUMN document_id',
                'SELECT 1')
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = 'lease_driver_documents'
              AND column_name = 'document_id'
        );
    """)
    _exec("PREPARE s FROM @sql; EXECUTE s; DEALLOCATE PREPARE s;")
