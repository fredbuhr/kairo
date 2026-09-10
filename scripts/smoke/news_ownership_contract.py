#!/usr/bin/env python3
"""Deterministic ownership contract proof for KAIRO News.

The contract exercises the Core boundary directly with lightweight fake sessions so ownership,
authentication wiring and replay safety can be validated without Docker, Keycloak or a TTS service.
"""

from __future__ import annotations

import asyncio
import inspect
import uuid

from fastapi import HTTPException

from kairo_core import news as news_module
from kairo_core.auth import Principal, require_kairo_user
from kairo_core.models import Project, Task, WorkflowExecution
from kairo_core.schemas import NewsBriefCreate, NewsBriefRunResponse


def principal(subject: str) -> Principal:
    return Principal(
        subject=subject,
        username=subject,
        email=None,
        roles=frozenset({"kairo-user"}),
        claims={},
    )


async def expect_http(status_code: int, awaitable) -> None:
    try:
        await awaitable
    except HTTPException as exc:
        assert exc.status_code == status_code, exc
    else:
        raise AssertionError(f"Expected HTTP {status_code}")


def news_project(subject: str) -> Project:
    return Project(
        id=news_module._news_project_id(subject),
        owner_subject=subject,
        name="KAIRO News",
        status="active",
        summary=None,
        parent_id=None,
    )


def news_task(
    subject: str,
    project_id: uuid.UUID,
    body: NewsBriefCreate,
    *,
    task_id: uuid.UUID | None = None,
    command_id: uuid.UUID | None = None,
) -> Task:
    task_input = body.model_dump(mode="json")
    task_input["capability"] = "news.brief"
    task_input["requester_subject"] = subject
    if command_id is not None:
        task_input["command_id"] = str(command_id)
    return Task(
        id=task_id or uuid.uuid4(),
        project_id=project_id,
        title=f"News brief — {body.query}",
        description="Ownership contract fixture",
        status="completed",
        owner_type="user",
        owner_ref=subject,
        authority_ceiling=1,
        input=task_input,
    )


class OwnedTaskSession:
    """Evaluate only the two SELECT shapes used by public News reads."""

    def __init__(self, projects: list[Project], tasks: list[Task]) -> None:
        self.projects = {project.id: project for project in projects}
        self.tasks = {task.id: task for task in tasks}

    async def scalar(self, statement):
        sql = " ".join(str(statement).lower().split())
        if "from tasks" in sql and "join projects" in sql:
            assert "projects.owner_subject" in sql, sql
            assert "tasks.owner_type" in sql, sql
            assert "tasks.owner_ref" in sql, sql

            params = {str(value) for value in statement.compile().params.values()}
            task = next(
                (candidate for task_id, candidate in self.tasks.items() if str(task_id) in params),
                None,
            )
            requester_subject = next(
                (
                    str(project.owner_subject)
                    for project in self.projects.values()
                    if project.owner_subject and str(project.owner_subject) in params
                ),
                None,
            )
            assert requester_subject is not None, params
            assert "user" in params, params
            if task is None:
                return None

            project = self.projects.get(task.project_id)
            if (
                project is not None
                and project.owner_subject == requester_subject
                and task.owner_type == "user"
                and task.owner_ref == requester_subject
            ):
                return task
            return None

        if "from artifacts" in sql:
            return None

        raise AssertionError(f"Unexpected scalar query: {sql}")


class ReplaySession:
    def __init__(self, task: Task, execution: WorkflowExecution) -> None:
        self.task = task
        self.execution = execution

    async def get(self, model, key):
        if model is Task:
            return self.task if key == self.task.id else None
        raise AssertionError(f"Unexpected model lookup: {model}")

    async def scalar(self, statement):
        sql = " ".join(str(statement).lower().split())
        if "from workflow_executions" in sql:
            return self.execution
        raise AssertionError(f"Unexpected scalar query: {sql}")


def assert_requires_kairo_user(endpoint) -> None:
    dependency = inspect.signature(endpoint).parameters["principal"].default
    assert getattr(dependency, "dependency", None) is require_kairo_user, dependency


async def prove_create_is_bound_to_principal(body: NewsBriefCreate, owner: Principal) -> None:
    captured: dict[str, object] = {}
    original_start = news_module.start_news_brief

    async def fake_start_news_brief(request, session, **kwargs):
        captured.update(kwargs)
        return NewsBriefRunResponse(
            task_id=uuid.uuid4(),
            workflow_execution_id=uuid.uuid4(),
            workflow_id="news-ownership-contract",
            status="running",
            query=request.query,
            mode=request.mode,
            output=request.output,
        )

    news_module.start_news_brief = fake_start_news_brief
    try:
        await news_module.create_news_brief(body, principal=owner, session=object())
    finally:
        news_module.start_news_brief = original_start

    assert captured["requester_subject"] == owner.subject, captured
    assert captured["actor_type"] == "user", captured
    assert captured["actor_id"] == owner.subject, captured


async def prove_public_read_boundaries(
    body: NewsBriefCreate,
    owner: Principal,
    stranger: Principal,
) -> None:
    owner_project = news_project(owner.subject)
    stranger_project = news_project(stranger.subject)
    task = news_task(owner.subject, owner_project.id, body)
    session = OwnedTaskSession([owner_project, stranger_project], [task])

    readable = await news_module.get_news_brief(task.id, principal=owner, session=session)
    assert readable.task_id == task.id, readable
    assert readable.query == body.query, readable

    await expect_http(
        404,
        news_module.get_news_brief(task.id, principal=stranger, session=session),
    )
    await expect_http(
        404,
        news_module.news_brief_audio(task.id, principal=stranger, session=session),
    )

    legacy = news_task(owner.subject, owner_project.id, body)
    legacy.input = {
        key: value
        for key, value in (legacy.input or {}).items()
        if key != "requester_subject"
    }
    session.tasks[legacy.id] = legacy
    await expect_http(
        404,
        news_module.get_news_brief(legacy.id, principal=owner, session=session),
    )

    foreign_project_task = news_task(owner.subject, stranger_project.id, body)
    session.tasks[foreign_project_task.id] = foreign_project_task
    await expect_http(
        404,
        news_module.get_news_brief(foreign_project_task.id, principal=owner, session=session),
    )


async def prove_replay_is_owner_and_parameter_bound(
    body: NewsBriefCreate,
    owner: Principal,
    stranger: Principal,
) -> None:
    owner_project = news_project(owner.subject)
    stranger_project = news_project(stranger.subject)
    command_id = uuid.uuid4()
    task_id = uuid.uuid4()
    task = news_task(
        owner.subject,
        owner_project.id,
        body,
        task_id=task_id,
        command_id=command_id,
    )
    execution = WorkflowExecution(
        id=uuid.uuid4(),
        task_id=task.id,
        workflow_id="news-ownership-replay",
        status="running",
        correlation_id=uuid.uuid4(),
    )
    session = ReplaySession(task, execution)
    original_ensure = news_module._ensure_news_project

    async def fake_ensure_news_project(_session, subject: str) -> Project:
        if subject == owner.subject:
            return owner_project
        if subject == stranger.subject:
            return stranger_project
        raise AssertionError(f"Unexpected subject: {subject}")

    news_module._ensure_news_project = fake_ensure_news_project
    try:
        replayed = await news_module.start_news_brief(
            body,
            session,
            requester_subject=owner.subject,
            actor_type="user",
            actor_id=owner.subject,
            command_id=command_id,
            task_id=task.id,
        )
        assert replayed.task_id == task.id, replayed
        assert replayed.workflow_execution_id == execution.id, replayed

        await expect_http(
            409,
            news_module.start_news_brief(
                body,
                session,
                requester_subject=stranger.subject,
                actor_type="user",
                actor_id=stranger.subject,
                command_id=command_id,
                task_id=task.id,
            ),
        )
        await expect_http(
            409,
            news_module.start_news_brief(
                body.model_copy(update={"query": "A different deterministic request"}),
                session,
                requester_subject=owner.subject,
                actor_type="user",
                actor_id=owner.subject,
                command_id=command_id,
                task_id=task.id,
            ),
        )
        await expect_http(
            409,
            news_module.start_news_brief(
                body,
                session,
                requester_subject=owner.subject,
                actor_type="user",
                actor_id=owner.subject,
                command_id=uuid.uuid4(),
                task_id=task.id,
            ),
        )
    finally:
        news_module._ensure_news_project = original_ensure


async def main() -> None:
    owner = principal("user-a")
    stranger = principal("user-b")
    body = NewsBriefCreate(
        query="Quelles nouvelles peuvent impacter les marchés aujourd'hui ?",
        mode="market_impact",
        language="fr",
        time_range="day",
        max_sources=10,
        output="both",
        voice="ff_siwis",
    )

    assert news_module._news_project_id(owner.subject) == news_module._news_project_id(owner.subject)
    assert news_module._news_project_id(owner.subject) != news_module._news_project_id(stranger.subject)

    for endpoint in (
        news_module.create_news_brief,
        news_module.get_news_brief,
        news_module.news_brief_audio,
    ):
        assert_requires_kairo_user(endpoint)

    await prove_create_is_bound_to_principal(body, owner)
    await prove_public_read_boundaries(body, owner, stranger)
    await prove_replay_is_owner_and_parameter_bound(body, owner, stranger)

    print(
        "PASS: News creation, reads, audio and deterministic replay are bound to the authenticated "
        "requester; foreign and legacy/unowned access fails closed"
    )


if __name__ == "__main__":
    asyncio.run(main())
