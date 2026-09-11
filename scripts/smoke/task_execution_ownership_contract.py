from __future__ import annotations

import inspect

from nevolium_core import assistant, documents, research
from nevolium_core.auth import require_nevolium_user
from nevolium_core.workflows import router, run_task


def main() -> None:
    signature = inspect.signature(run_task)
    assert signature.parameters["session"].default is inspect.Parameter.empty, signature
    assert signature.parameters["actor_id"].default is None, signature
    assert assistant.run_task is run_task
    assert documents.run_task is run_task
    assert research.run_task is run_task

    public = {
        (route.path, method): route
        for route in router.routes
        if getattr(route, "path", "").startswith("/v1/tasks/")
        for method in (route.methods or set())
    }
    run_route = public[("/v1/tasks/{task_id}/run", "POST")]
    artifact_route = public[("/v1/tasks/{task_id}/artifacts", "GET")]

    for route in (run_route, artifact_route):
        dependency_calls = {dependency.call for dependency in route.dependant.dependencies}
        assert require_nevolium_user in dependency_calls, (route.path, dependency_calls)

    assert run_route.endpoint is not run_task

    print(
        "PASS: public Task execution/artifact routes require user identity while internal Core modules "
        "retain the transport-agnostic run_task function"
    )


if __name__ == "__main__":
    main()
