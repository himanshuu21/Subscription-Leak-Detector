"""Add optional Google OpenID Connect identities."""

from alembic import op
import sqlalchemy as sa


revision = "0003_google_oauth"
down_revision = "0002_hardening_and_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.alter_column(
            "hashed_password",
            existing_type=sa.String(255),
            nullable=True,
        )
        batch.add_column(
            sa.Column("auth_provider", sa.String(20), server_default="local", nullable=False)
        )
        batch.add_column(sa.Column("google_sub", sa.String(255), nullable=True))
        batch.create_index("ix_users_google_sub", ["google_sub"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("users") as batch:
        batch.drop_index("ix_users_google_sub")
        batch.drop_column("google_sub")
        batch.drop_column("auth_provider")
        batch.alter_column(
            "hashed_password",
            existing_type=sa.String(255),
            nullable=False,
        )
