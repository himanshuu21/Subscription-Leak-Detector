"""Use fixed-point money, retain import diagnostics, and add query indexes."""

from alembic import op
import sqlalchemy as sa


revision = "0002_hardening_and_indexes"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("uploads") as batch:
        batch.add_column(sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("imported_rows", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("invalid_row_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("credit_row_count", sa.Integer(), server_default="0", nullable=False))
        batch.add_column(sa.Column("invalid_row_errors", sa.Text(), nullable=True))
        batch.create_index("ix_uploads_user_uploaded", ["user_id", "uploaded_at"])

    with op.batch_alter_table("transactions") as batch:
        batch.alter_column("amount", existing_type=sa.Float(), type_=sa.Numeric(14, 2), nullable=False)
        batch.add_column(sa.Column("transaction_type", sa.String(10), server_default="debit", nullable=False))
        batch.create_index("ix_transactions_upload_date", ["upload_id", "date"])
        batch.create_index("ix_transactions_upload_merchant", ["upload_id", "normalized_merchant"])

    with op.batch_alter_table("subscriptions") as batch:
        batch.alter_column("current_amount", existing_type=sa.Float(), type_=sa.Numeric(14, 2), nullable=False)
        batch.create_index("ix_subscriptions_user_confidence", ["user_id", "confidence_score"])
        batch.create_index("ix_subscriptions_upload_confidence", ["upload_id", "confidence_score"])

    with op.batch_alter_table("price_hike_events") as batch:
        batch.alter_column("old_amount", existing_type=sa.Float(), type_=sa.Numeric(14, 2), nullable=False)
        batch.alter_column("new_amount", existing_type=sa.Float(), type_=sa.Numeric(14, 2), nullable=False)


def downgrade() -> None:
    with op.batch_alter_table("price_hike_events") as batch:
        batch.alter_column("new_amount", existing_type=sa.Numeric(14, 2), type_=sa.Float(), nullable=False)
        batch.alter_column("old_amount", existing_type=sa.Numeric(14, 2), type_=sa.Float(), nullable=False)
    with op.batch_alter_table("subscriptions") as batch:
        batch.drop_index("ix_subscriptions_upload_confidence")
        batch.drop_index("ix_subscriptions_user_confidence")
        batch.alter_column("current_amount", existing_type=sa.Numeric(14, 2), type_=sa.Float(), nullable=False)
    with op.batch_alter_table("transactions") as batch:
        batch.drop_index("ix_transactions_upload_merchant")
        batch.drop_index("ix_transactions_upload_date")
        batch.drop_column("transaction_type")
        batch.alter_column("amount", existing_type=sa.Numeric(14, 2), type_=sa.Float(), nullable=False)
    with op.batch_alter_table("uploads") as batch:
        batch.drop_index("ix_uploads_user_uploaded")
        batch.drop_column("invalid_row_errors")
        batch.drop_column("credit_row_count")
        batch.drop_column("invalid_row_count")
        batch.drop_column("imported_rows")
        batch.drop_column("total_rows")
