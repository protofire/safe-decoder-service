"""add_socialscan_abi_source

Revision ID: 6e4ea7ed1df7
Revises: 0da35e86b777
Create Date: 2026-06-11 11:11:19.881560

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6e4ea7ed1df7"
down_revision: str | None = "0da35e86b777"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO abisource (name, url)
        VALUES ('Socialscan', '');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM abisource
        WHERE name = 'Socialscan' AND url = '';
        """
    )
