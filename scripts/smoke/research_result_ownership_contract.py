from __future__ import annotations

from fastapi import HTTPException

from nevolium_core.auth import Principal
from nevolium_core.research_results import _require_research_owner


def principal(subject: str) -> Principal:
    return Principal(
        subject=subject,
        username=subject,
        email=None,
        roles=frozenset({"nevolium-user"}),
        claims={},
    )


def expect_not_found(task_input: dict, subject: str) -> None:
    try:
        _require_research_owner(task_input, principal(subject))
    except HTTPException as exc:
        assert exc.status_code == 404, exc
        assert exc.detail == "Research run not found", exc
    else:
        raise AssertionError("Foreign or unowned Research result must fail closed")


def main() -> None:
    _require_research_owner({"requester_subject": "user-a"}, principal("user-a"))
    expect_not_found({"requester_subject": "user-a"}, "user-b")
    expect_not_found({}, "user-a")
    expect_not_found({"requester_subject": ""}, "user-a")

    print(
        "PASS: Research result reads require the exact authenticated requester subject and expose the "
        "same not-found surface for foreign and legacy unowned runs"
    )


if __name__ == "__main__":
    main()
