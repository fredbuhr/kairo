"""Add canonical planning fields for human Task operations.

Revision ID: 0008_task_planning_fields
Revises: 0007_mcp_tool_registry
"""

from alembic import op
import sqlalchemy as sa


revision = "0008_task_planning_fields"
down_revision = "0007_mcp_tool_registry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tasks",
        sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
    )
    op.add_column(
        "tasks",
        sa.Column("planned_start_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("planned_end_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tasks",
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_tasks_status_due_priority",
        "tasks",
        ["status", "due_at", "priority"],
        unique=False,
    )
    op.create_index(
        "ix_tasks_planned_start",
        "tasks",
        ["planned_start_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_planned_start", table_name="tasks")
    op.drop_index("ix_tasks_status_due_priority", table_name="tasks")
    op.drop_column("tasks", "due_at")
    op.drop_column("tasks", "planned_end_at")
    op.drop_column("tasks", "planned_start_at")
    op.drop_column("tasks", "priority")
