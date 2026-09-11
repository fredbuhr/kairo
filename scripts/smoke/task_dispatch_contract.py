"""Exercise the public schema and resource bindings without a database or Temporal server."""

from __future__ import annotations

import unittest
import uuid

from fastapi import HTTPException
from pydantic import ValidationError

from kairo_core.command_models import CommandRecord
from kairo_core.document_models import DocumentVersion
from kairo_core.memory import MEMORY_PROJECT_ID, _task_id
from kairo_core.models import Project, Task
from kairo_core.schemas import TaskCreate
from kairo_core.tool_models import ToolInvocation
from kairo_core.workflows import _require_execution_binding

RESERVED = (
    "tool.invoke", "document.ingest", "assistant.route.semantic", "memory.project",
    "news.brief", "research.autonomous", "unknown.future-capability",
)


class Session:
    def __init__(self, *rows: object) -> None:
        self.rows = {(type(row), row.id): row for row in rows}

    async def get(self, model: type, key: uuid.UUID) -> object | None:
        return self.rows.get((model, key))


class PublicTaskContract(unittest.TestCase):
    def test_user_and_foundation_tasks_remain_available(self) -> None:
        for task_input in ({}, {"capability": "foundation"}, {"note": "user metadata"}):
            task = TaskCreate(project_id=uuid.uuid4(), title="User task", input=task_input)
            self.assertEqual(task.owner_type, "user")
            self.assertEqual(task.input, task_input)

    def test_specialist_dispatch_cannot_enter_through_public_schema(self) -> None:
        for capability in (*RESERVED, {"nested": "tool.invoke"}, ["tool.invoke"]):
            with self.subTest(capability=capability), self.assertRaises(ValidationError):
                TaskCreate(project_id=uuid.uuid4(), title="Forged", input={"capability": capability})

    def test_public_task_cannot_claim_internal_identity(self) -> None:
        for owner_type in ("system", "agent"):
            with self.subTest(owner_type=owner_type), self.assertRaises(ValidationError):
                TaskCreate(project_id=uuid.uuid4(), title="Forged", owner_type=owner_type)


class ExecutionBindingContract(unittest.IsolatedAsyncioTestCase):
    async def rejected(self, task: Task, session: Session) -> None:
        with self.assertRaises(HTTPException) as caught:
            await _require_execution_binding(task, session)
        self.assertEqual(caught.exception.status_code, 409)

    async def test_resource_must_point_back_to_executing_task(self) -> None:
        for capability, field, model in (
            ("tool.invoke", "tool_invocation_id", ToolInvocation),
            ("document.ingest", "document_version_id", DocumentVersion),
            ("assistant.route.semantic", "command_id", CommandRecord),
        ):
            task_id, resource_id = uuid.uuid4(), uuid.uuid4()
            task = Task(id=task_id, input={"capability": capability, field: str(resource_id)})
            binding = (
                {"result_json": {"routing_task_id": str(task_id)}}
                if model is CommandRecord else {"task_id": task_id}
            )
            row = model(id=resource_id, **binding)
            with self.subTest(capability=capability):
                await _require_execution_binding(task, Session(row))
                task.id = uuid.uuid4()  # Same resource, different (possibly legacy) caller.
                await self.rejected(task, Session(row))
                await self.rejected(task, Session())
                task.input = {"capability": capability, field: "malformed"}
                await self.rejected(task, Session(row))

    async def test_memory_identity_project_and_system_owner_are_all_required(self) -> None:
        source = uuid.uuid4()
        for generation in (1, 2):
            task = Task(
                id=_task_id(source, generation), project_id=MEMORY_PROJECT_ID, owner_type="system",
                input={"capability": "memory.project", "source_id": str(source), "projection_generation": generation},
            )
            await _require_execution_binding(task, Session())
            for field, invalid in (("id", uuid.uuid4()), ("project_id", uuid.uuid4()), ("owner_type", "user")):
                original = getattr(task, field)
                setattr(task, field, invalid)
                await self.rejected(task, Session())
                setattr(task, field, original)

    async def test_requester_must_match_project_owner(self) -> None:
        project = Project(id=uuid.uuid4(), owner_subject="owner-a")
        for capability in ("news.brief", "research.autonomous"):
            task = Task(project_id=project.id, input={"capability": capability, "requester_subject": "owner-a"})
            await _require_execution_binding(task, Session(project))
            for subject in ("owner-b", "", None):
                task.input = {"capability": capability, "requester_subject": subject}
                await self.rejected(task, Session(project))

    async def test_unknown_capability_fails_closed_but_foundation_needs_no_resource(self) -> None:
        await self.rejected(Task(input={"capability": "unknown.future-capability"}), Session())
        await _require_execution_binding(Task(input={}), Session())
        await _require_execution_binding(Task(input={"capability": "foundation"}), Session())


if __name__ == "__main__":
    unittest.main()
