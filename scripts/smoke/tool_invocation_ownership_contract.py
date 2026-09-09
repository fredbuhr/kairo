#!/usr/bin/env python3
"""Static contract proof for subject-owned ToolInvocation construction and idempotency.

This does not replace the future two-user runtime proof. It provides a cheap fail-fast guard that all
current ToolInvocation constructors propagate an owner and that the 0017 migration/model no longer
use a deployment-global caller idempotency namespace.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORE = ROOT / "services" / "core" / "src" / "kairo_core"
MIGRATIONS = ROOT / "services" / "core" / "migrations" / "versions"


def source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def tool_invocation_calls(path: Path) -> list[ast.Call]:
    tree = ast.parse(source(path), filename=str(path))
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if isinstance(function, ast.Name) and function.id == "ToolInvocation":
            calls.append(node)
    return calls


def main() -> None:
    model_path = CORE / "tool_models.py"
    tools_path = CORE / "tools.py"
    research_path = CORE / "research.py"
    migration_path = MIGRATIONS / "0017_tool_invocation_ownership.py"

    model_tree = ast.parse(source(model_path), filename=str(model_path))
    invocation_class = next(
        node
        for node in model_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "ToolInvocation"
    )
    attributes = {
        node.target.id
        for node in invocation_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "keycloak_subject" in attributes, attributes

    table_args_text = ast.get_source_segment(source(model_path), invocation_class) or ""
    assert "uq_tool_invocation_subject_idempotency" in table_args_text
    assert '"keycloak_subject",\n            "idempotency_key"' in table_args_text

    constructors = []
    for path in (tools_path, research_path):
        calls = tool_invocation_calls(path)
        assert calls, f"Expected at least one ToolInvocation constructor in {path.name}"
        for call in calls:
            keyword_names = {keyword.arg for keyword in call.keywords if keyword.arg}
            assert "keycloak_subject" in keyword_names, (
                f"ToolInvocation constructor in {path.name}:{call.lineno} does not propagate ownership"
            )
            constructors.append((path.name, call.lineno))

    tools_text = source(tools_path)
    research_text = source(research_path)
    assert "ToolInvocation.keycloak_subject == principal.subject" in tools_text
    assert "ToolInvocation.keycloak_subject == owner_subject" in research_text
    assert "project.keycloak_subject != invocation.keycloak_subject" in tools_text

    migration_text = source(migration_path)
    assert 'revision = "0017_tool_invocation_ownership"' in migration_text
    assert 'down_revision = "0016_automation_idempotency_scope"' in migration_text
    assert "DROP CONSTRAINT IF EXISTS tool_invocations_idempotency_key_key" in migration_text
    assert "uq_tool_invocation_subject_idempotency" in migration_text
    assert "ToolInvocation ownership could not be derived from Task -> Project" in migration_text
    assert "kairo_enforce_tool_invocation_task_owner" in migration_text
    assert "trg_tool_invocation_task_owner" in migration_text
    assert "project.keycloak_subject = NEW.keycloak_subject" in migration_text

    print(
        "KAIRO ToolInvocation ownership contract proof passed: "
        + ", ".join(f"{name}:{line}" for name, line in constructors)
    )


if __name__ == "__main__":
    main()
