"""add_transporter_portal_and_carrier_isolation

Revision ID: e1bdd29d1146
Revises: b66cbef5cc47
Create Date: 2026-11-09 23:19:48.702275

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1bdd29d1146'
down_revision: Union[str, Sequence[str], None] = 'b66cbef5cc47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema to include Transporter Organization, Invitations, and Carrier Isolation."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    existing_tables = inspector.get_table_names()

    # 1. Create transporter_organizations table if not exists
    if 'transporter_organizations' not in existing_tables:
        op.create_table(
            'transporter_organizations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('name', sa.String(length=120), nullable=False),
            sa.Column('code', sa.String(length=50), nullable=False),
            sa.Column('contact_email', sa.String(length=255), nullable=True),
            sa.Column('contact_phone', sa.String(length=50), nullable=True),
            sa.Column('is_active', sa.Boolean(), server_default='1', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('name')
        )
        op.create_index('ix_transporter_organizations_id', 'transporter_organizations', ['id'], unique=False)
        op.create_index('ix_transporter_organizations_code', 'transporter_organizations', ['code'], unique=True)

    # 2. Create transporter_invitations table if not exists
    if 'transporter_invitations' not in existing_tables:
        op.create_table(
            'transporter_invitations',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('company_id', sa.Integer(), nullable=False),
            sa.Column('transporter_org_id', sa.Integer(), nullable=True),
            sa.Column('invited_email', sa.String(length=255), nullable=False),
            sa.Column('carrier_name', sa.String(length=120), nullable=False),
            sa.Column('invite_token', sa.String(length=120), nullable=False),
            sa.Column('status', sa.String(length=30), server_default='PENDING', nullable=False),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(['company_id'], ['companies.id'], ondelete='CASCADE'),
            sa.ForeignKeyConstraint(['transporter_org_id'], ['transporter_organizations.id'], ondelete='SET NULL'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('invite_token')
        )
        op.create_index('ix_transporter_invitations_id', 'transporter_invitations', ['id'], unique=False)
        op.create_index('ix_transporter_invitations_invite_token', 'transporter_invitations', ['invite_token'], unique=True)

    # 3. Alter users table
    user_cols = [c['name'] for c in inspector.get_columns('users')]
    with op.batch_alter_table('users', schema=None) as batch_op:
        if 'transporter_org_id' not in user_cols:
            batch_op.add_column(sa.Column('transporter_org_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_users_transporter_org_id',
                'transporter_organizations',
                ['transporter_org_id'],
                ['id'],
                ondelete='SET NULL'
            )

    # 4. Alter shipments table
    shipment_cols = [c['name'] for c in inspector.get_columns('shipments')]
    with op.batch_alter_table('shipments', schema=None) as batch_op:
        if 'transporter_org_id' not in shipment_cols:
            batch_op.add_column(sa.Column('transporter_org_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_shipments_transporter_org_id',
                'transporter_organizations',
                ['transporter_org_id'],
                ['id'],
                ondelete='SET NULL'
            )
        if 'assignment_status' not in shipment_cols:
            batch_op.add_column(sa.Column('assignment_status', sa.String(length=50), server_default='PENDING', nullable=True))
        if 'current_eta' not in shipment_cols:
            batch_op.add_column(sa.Column('current_eta', sa.Date(), nullable=True))

    # 5. Alter disruption_reports table
    disruption_cols = [c['name'] for c in inspector.get_columns('disruption_reports')]
    with op.batch_alter_table('disruption_reports', schema=None) as batch_op:
        if 'transporter_org_id' not in disruption_cols:
            batch_op.add_column(sa.Column('transporter_org_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                'fk_disruption_reports_transporter_org_id',
                'transporter_organizations',
                ['transporter_org_id'],
                ['id'],
                ondelete='SET NULL'
            )
        if 'idempotency_key' not in disruption_cols:
            batch_op.add_column(sa.Column('idempotency_key', sa.String(length=120), nullable=True))
            batch_op.create_index('ix_disruption_reports_idempotency_key', ['idempotency_key'], unique=True)
        if 'incident_location' not in disruption_cols:
            batch_op.add_column(sa.Column('incident_location', sa.String(length=255), nullable=True))
        if 'evidence_url' not in disruption_cols:
            batch_op.add_column(sa.Column('evidence_url', sa.String(length=500), nullable=True))
        if 'status' not in disruption_cols:
            batch_op.add_column(sa.Column('status', sa.String(length=30), server_default='SUBMITTED', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('disruption_reports', schema=None) as batch_op:
        batch_op.drop_index('ix_disruption_reports_idempotency_key')
        batch_op.drop_constraint('fk_disruption_reports_transporter_org_id', type_='foreignkey')
        batch_op.drop_column('status')
        batch_op.drop_column('evidence_url')
        batch_op.drop_column('incident_location')
        batch_op.drop_column('idempotency_key')
        batch_op.drop_column('transporter_org_id')

    with op.batch_alter_table('shipments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_shipments_transporter_org_id', type_='foreignkey')
        batch_op.drop_column('current_eta')
        batch_op.drop_column('assignment_status')
        batch_op.drop_column('transporter_org_id')

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_transporter_org_id', type_='foreignkey')
        batch_op.drop_column('transporter_org_id')

    op.drop_index('ix_transporter_invitations_invite_token', table_name='transporter_invitations')
    op.drop_index('ix_transporter_invitations_id', table_name='transporter_invitations')
    op.drop_table('transporter_invitations')

    op.drop_index('ix_transporter_organizations_code', table_name='transporter_organizations')
    op.drop_index('ix_transporter_organizations_id', table_name='transporter_organizations')
    op.drop_table('transporter_organizations')
