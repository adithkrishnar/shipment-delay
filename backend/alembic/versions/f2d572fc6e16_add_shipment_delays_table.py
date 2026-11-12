"""add_shipment_delays_table

Revision ID: f2d572fc6e16
Revises: e1bdd29d1146
Create Date: 2026-11-10 09:58:11.451124

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2d572fc6e16'
down_revision: Union[str, Sequence[str], None] = 'e1bdd29d1146'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "shipment_delays" not in existing_tables:
        op.create_table(
            "shipment_delays",
            sa.Column("id", sa.Integer(), primary_key=True, index=True),
            sa.Column("shipment_id", sa.Integer(), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, index=True),
            sa.Column("transporter_org_id", sa.Integer(), sa.ForeignKey("transporter_organizations.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("reported_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True),
            sa.Column("previous_eta", sa.DateTime(), nullable=True),
            sa.Column("new_eta", sa.DateTime(), nullable=False),
            sa.Column("delay_hours", sa.Float(), nullable=False),
            sa.Column("reason", sa.String(length=100), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("attachment_url", sa.String(length=500), nullable=True),
            sa.Column("idempotency_key", sa.String(length=120), nullable=True),
            sa.Column("payload_hash", sa.String(length=64), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        op.create_index("ix_shipment_delays_shipment_id", "shipment_delays", ["shipment_id"])
        op.create_index("ix_shipment_delays_transporter_org_id", "shipment_delays", ["transporter_org_id"])
        op.create_index("ix_shipment_delays_created_at", "shipment_delays", ["created_at"])
        op.create_index("ix_shipment_delays_idempotency_key", "shipment_delays", ["idempotency_key"], unique=True)


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    if "shipment_delays" in existing_tables:
        op.drop_table("shipment_delays")
