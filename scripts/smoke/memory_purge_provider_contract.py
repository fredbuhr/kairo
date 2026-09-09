#!/usr/bin/env python3
"""Fail fast if pinned Mem0/Graphiti APIs drift away from KAIRO's purge boundary."""

from __future__ import annotations

import inspect

from graphiti_core.driver.operations.episode_node_ops import EpisodeNodeOperations
from mem0 import Memory


def require_parameter(callable_object, parameter: str, label: str) -> None:
    signature = inspect.signature(callable_object)
    if parameter not in signature.parameters:
        raise AssertionError(f"{label} no longer exposes required parameter {parameter}: {signature}")


def main() -> None:
    # KAIRO owns one Mem0 user scope per authenticated subject. Account purge must remain able to
    # delete that scope without enumerating/read-backing individual memories.
    require_parameter(Memory.delete_all, "user_id", "Mem0 Memory.delete_all")
    require_parameter(Memory.get_all, "filters", "Mem0 Memory.get_all")

    # Current KAIRO Graphiti projection is intentionally non-generative and writes one EpisodicNode
    # per canonical message into a conversation group. Purge deletes those groups and verifies none
    # remain. Enabling generative extraction requires widening this contract first.
    require_parameter(
        EpisodeNodeOperations.delete_by_group_id,
        "group_id",
        "Graphiti EpisodeNodeOperations.delete_by_group_id",
    )
    require_parameter(
        EpisodeNodeOperations.get_by_group_ids,
        "group_ids",
        "Graphiti EpisodeNodeOperations.get_by_group_ids",
    )
    require_parameter(
        EpisodeNodeOperations.get_by_group_ids,
        "limit",
        "Graphiti EpisodeNodeOperations.get_by_group_ids",
    )

    print("KAIRO derived-memory provider purge API contract passed")


if __name__ == "__main__":
    main()
