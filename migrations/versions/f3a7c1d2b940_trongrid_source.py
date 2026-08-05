"""trongrid_source

Revision ID: f3a7c1d2b940
Revises: 0da35e86b777
Create Date: 2026-08-05 10:12:44.518332

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f3a7c1d2b940"
down_revision: str | None = "0da35e86b777"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO abisource (name, url)
        VALUES ('TronGrid', '');
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM abisource
        WHERE name = 'TronGrid' AND url = '';
        """
    )
