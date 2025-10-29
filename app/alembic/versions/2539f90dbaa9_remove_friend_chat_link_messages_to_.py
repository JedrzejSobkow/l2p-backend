"""remove_friend_chat_link_messages_to_friendship

Revision ID: 2539f90dbaa9
Revises: 563f3c5e5ac8
Create Date: 2025-10-28 17:31:20.934628

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2539f90dbaa9'
down_revision: Union[str, None] = '563f3c5e5ac8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add friendship_id column to chat_messages table
    op.add_column('chat_messages', sa.Column('friendship_id', sa.Integer(), nullable=True))
    
    # Populate friendship_id from friend_chat relationship
    op.execute("""
        UPDATE chat_messages cm
        SET friendship_id = fc.friendship_id
        FROM friend_chats fc
        WHERE cm.friend_chat_id = fc.id_friend_chat
    """)
    
    # Make friendship_id not nullable
    op.alter_column('chat_messages', 'friendship_id', nullable=False)
    
    # Create foreign key constraint
    op.create_foreign_key(
        'fk_chat_messages_friendship_id',
        'chat_messages', 'friendships',
        ['friendship_id'], ['id_friendship']
    )
    
    # Create index on friendship_id
    op.create_index('ix_chat_messages_friendship_id', 'chat_messages', ['friendship_id'])
    
    # Drop old foreign key constraint and column
    op.drop_constraint('chat_messages_friend_chat_id_fkey', 'chat_messages', type_='foreignkey')
    op.drop_index('ix_chat_messages_friend_chat_id', 'chat_messages')
    op.drop_column('chat_messages', 'friend_chat_id')
    
    # Drop friend_chats table
    op.drop_table('friend_chats')


def downgrade() -> None:
    # Recreate friend_chats table
    op.create_table(
        'friend_chats',
        sa.Column('id_friend_chat', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('friendship_id', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id_friend_chat'),
        sa.ForeignKeyConstraint(['friendship_id'], ['friendships.id_friendship']),
        sa.UniqueConstraint('friendship_id')
    )
    op.create_index('ix_friend_chats_id_friend_chat', 'friend_chats', ['id_friend_chat'])
    op.create_index('ix_friend_chats_friendship_id', 'friend_chats', ['friendship_id'])
    
    # Populate friend_chats from existing friendships that have messages
    op.execute("""
        INSERT INTO friend_chats (friendship_id)
        SELECT DISTINCT friendship_id
        FROM chat_messages
    """)
    
    # Add friend_chat_id column to chat_messages
    op.add_column('chat_messages', sa.Column('friend_chat_id', sa.Integer(), nullable=True))
    
    # Populate friend_chat_id from friendship_id
    op.execute("""
        UPDATE chat_messages cm
        SET friend_chat_id = fc.id_friend_chat
        FROM friend_chats fc
        WHERE cm.friendship_id = fc.friendship_id
    """)
    
    # Make friend_chat_id not nullable
    op.alter_column('chat_messages', 'friend_chat_id', nullable=False)
    
    # Create foreign key constraint
    op.create_foreign_key(
        'chat_messages_friend_chat_id_fkey',
        'chat_messages', 'friend_chats',
        ['friend_chat_id'], ['id_friend_chat']
    )
    
    # Create index on friend_chat_id
    op.create_index('ix_chat_messages_friend_chat_id', 'chat_messages', ['friend_chat_id'])
    
    # Drop friendship_id column
    op.drop_constraint('fk_chat_messages_friendship_id', 'chat_messages', type_='foreignkey')
    op.drop_index('ix_chat_messages_friendship_id', 'chat_messages')
    op.drop_column('chat_messages', 'friendship_id')
