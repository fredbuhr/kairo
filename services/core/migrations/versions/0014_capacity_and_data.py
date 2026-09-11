"""D02: shared heavy-work leases, outbox claims and bounded-read indexes."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_capacity_and_data"
down_revision = "0013_model_reservations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("work_admissions",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("owner_subject", sa.String(320), nullable=False),
        sa.Column("capability", sa.String(80), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("lease_token", postgresql.UUID(as_uuid=True)),
        sa.Column("lease_holder", sa.String(320)),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("requested_at", sa.DateTime(timezone=True)),
        sa.Column("result_json", postgresql.JSONB()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_work_admission_owner", "work_admissions", ["owner_subject", "status", "created_at"])
    op.create_index("ix_work_admission_lease", "work_admissions", ["status", "lease_until"])
    op.add_column("outbox_events", sa.Column("claim_token", postgresql.UUID(as_uuid=True)))
    op.add_column("outbox_events", sa.Column("claim_until", sa.DateTime(timezone=True)))
    op.create_index("ix_outbox_pending_claim", "outbox_events", ["claim_until", "created_at", "id"], postgresql_where=sa.text("published_at IS NULL"))
    op.create_index("ix_tasks_project_page", "tasks", ["project_id", "created_at", "id"])
    op.create_index("ix_projects_owner_page", "projects", ["owner_subject", "created_at", "id"])
    op.execute("CREATE INDEX ix_assets_owner_page ON assets ((metadata_json->>'owner_subject'), created_at, id)")
    op.execute("CREATE INDEX ix_documents_owner_page ON documents ((metadata_json->>'owner_subject'), project_id, created_at, id)")
    op.create_index("ix_messages_rebuild_page", "conversation_messages", ["created_at", "id"])


def downgrade():
    for table, index in (("conversation_messages", "ix_messages_rebuild_page"), ("documents", "ix_documents_owner_page"),
                         ("assets", "ix_assets_owner_page"), ("projects", "ix_projects_owner_page"),
                         ("tasks", "ix_tasks_project_page"), ("outbox_events", "ix_outbox_pending_claim")):
        op.drop_index(index, table_name=table)
    op.drop_column("outbox_events", "claim_until")
    op.drop_column("outbox_events", "claim_token")
    op.drop_table("work_admissions")
