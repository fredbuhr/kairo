from __future__ import annotations

import asyncio
import uuid

from fastapi import HTTPException

from nevolium_core.assistant import _conversation_for_command, _owned_conversation
from nevolium_core.auth import Principal
from nevolium_core.command_models import Conversation
from nevolium_core.schemas import AssistantCommandCreate


def principal(subject: str) -> Principal:
    return Principal(
        subject=subject,
        username=subject,
        email=None,
        roles=frozenset({"nevolium-user"}),
        claims={},
    )


class FakeSession:
    def __init__(self) -> None:
        self.conversations: dict[uuid.UUID, Conversation] = {}
        self.pending: Conversation | None = None

    async def get(self, model, key):
        if model is Conversation:
            return self.conversations.get(key)
        raise AssertionError(f"Unexpected model lookup: {model}")

    def add(self, value) -> None:
        assert isinstance(value, Conversation), value
        self.pending = value

    async def flush(self) -> None:
        if self.pending is None:
            return
        if self.pending.id is None:
            self.pending.id = uuid.uuid4()
        self.conversations[self.pending.id] = self.pending
        self.pending = None


async def expect_http(status_code: int, awaitable) -> None:
    try:
        await awaitable
    except HTTPException as exc:
        assert exc.status_code == status_code, exc
    else:
        raise AssertionError(f"Expected HTTP {status_code}")


async def main() -> None:
    owner = principal("user-a")
    stranger = principal("user-b")
    session = FakeSession()

    created = await _conversation_for_command(
        AssistantCommandCreate(text="Create an owned Nevolium conversation", locale="fr-FR", output="text"),
        owner,
        session,
    )
    assert created.subject_ref == owner.subject, created
    assert created.id in session.conversations, created

    reused = await _conversation_for_command(
        AssistantCommandCreate(
            text="Continue the owned conversation",
            conversation_id=created.id,
            locale="fr-FR",
            output="text",
        ),
        owner,
        session,
    )
    assert reused.id == created.id, reused

    await expect_http(
        404,
        _conversation_for_command(
            AssistantCommandCreate(
                text="Try a foreign conversation",
                conversation_id=created.id,
                locale="fr-FR",
                output="text",
            ),
            stranger,
            session,
        ),
    )
    await expect_http(404, _owned_conversation(created.id, stranger, session))

    legacy_id = uuid.uuid4()
    session.conversations[legacy_id] = Conversation(
        id=legacy_id,
        subject_ref=None,
        locale="fr-FR",
        title="Legacy unowned conversation",
        status="active",
    )
    await expect_http(404, _owned_conversation(legacy_id, owner, session))

    inactive_id = uuid.uuid4()
    session.conversations[inactive_id] = Conversation(
        id=inactive_id,
        subject_ref=owner.subject,
        locale="fr-FR",
        title="Inactive conversation",
        status="closed",
    )
    await expect_http(
        409,
        _conversation_for_command(
            AssistantCommandCreate(
                text="Try a closed conversation",
                conversation_id=inactive_id,
                locale="fr-FR",
                output="text",
            ),
            owner,
            session,
        ),
    )

    print(
        "PASS: Assistant conversations are stamped with the authenticated subject, reusable only "
        "by that subject, and foreign/unowned conversations fail closed"
    )


if __name__ == "__main__":
    asyncio.run(main())
