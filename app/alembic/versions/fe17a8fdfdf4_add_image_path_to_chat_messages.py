"""add_image_path_to_chat_messages

Revision ID: fe17a8fdfdf4
Revises: 2539f90dbaa9
Create Date: 2025-10-28 18:01:14.159283

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fe17a8fdfdf4'
down_revision: Union[str, None] = '2539f90dbaa9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add image_path column to chat_messages
    op.add_column('chat_messages', sa.Column('image_path', sa.String(500), nullable=True))
    
    # Make content column nullable (for image-only messages)
    op.alter_column('chat_messages', 'content', nullable=True)


def downgrade() -> None:
    # Remove image_path column
    op.drop_column('chat_messages', 'image_path')
    
    # Make content column not nullable again
    op.alter_column('chat_messages', 'content', nullable=False)
