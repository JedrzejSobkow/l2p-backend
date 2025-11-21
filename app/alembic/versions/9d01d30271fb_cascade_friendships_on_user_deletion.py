"""cascade friendships on user deletion

Revision ID: 9d01d30271fb
Revises: a8d8968ad6b5
Create Date: 2025-11-20 19:53:46.512324

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9d01d30271fb'
down_revision: Union[str, None] = 'a8d8968ad6b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
