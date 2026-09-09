"""Scope automation invocation idempotency keys to one AutomationDefinition.

Revision ID: 0016_automation_idempotency_scope
Revises: 0015_secret_reference_ownership
Create Date: 2026-09-09

A caller-selected idempotency key is request identity, not a deployment-global namespace. Keeping it
globally unique lets an unrelated user collide with another user's key and creates an unnecessary
cross-tenant oracle. The canonical scope is one automation definition.
"""

from __future__ import annotations

from alembic import op

revision = "0016_automation_idempotency_scope"
down_revision = "0015_secret_reference_ownership"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # PostgreSQL's default name for the unnamed UniqueConstraint created in migration 0010.
    op.execute(
        "ALTER TABLE automation_invocations "
        "DROP CONSTRAINT IF EXISTS automation_invocations_idempotency_key_key"
    )
    op.create_unique_constraint(
        "uq_automation_invocation_definition_idempotency",
        "automation_invocations",
        ["automation_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_automation_invocation_definition_idempotency",
        "automation_invocations",
        type_="unique",
    )
    op.create_unique_constraint(
        "automation_invocations_idempotency_key_key",
        "automation_invocations",
        ["idempotency_key"],
    )
