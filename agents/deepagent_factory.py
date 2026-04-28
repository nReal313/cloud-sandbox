from __future__ import annotations

import json
from typing import Any

from .sandbox_backend import CloudSandboxBackend
from .tools import make_run_injected_python_tool


DEFAULT_SYSTEM_PROMPT = """
You are an autonomous machine learning engineer working inside a client-cloud
sandbox. Plan before acting, execute code in the sandbox, inspect outputs after
each command, debug failures, and verify results before finalizing.

Use the sandbox filesystem and shell tools for all code, data inspection,
experiments, and artifact creation. Do not assume data shape or schema. Inspect
first, then build.
""".strip()


def create_cloud_sandbox_deep_agent(
    *,
    sandbox_url: str,
    thread_id: str,
    model: Any,
    connectors: dict[str, Any] | None = None,
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    ttl_seconds: float | int = 3600,
    tools: list[Any] | None = None,
):
    from deepagents import create_deep_agent

    backend = CloudSandboxBackend.for_thread(
        sandbox_url=sandbox_url,
        thread_id=thread_id,
        ttl_seconds=ttl_seconds,
        connectors=connectors,
    )
    capabilities = backend.client.get_capabilities(backend.session_id)
    prompt_with_capabilities = build_system_prompt_with_capabilities(
        system_prompt=system_prompt,
        session_id=backend.session_id,
        created=backend.created,
        capabilities=capabilities,
    )
    agent_tools = [make_run_injected_python_tool(backend)]
    if tools:
        agent_tools.extend(tools)
    return create_deep_agent(
        model=model,
        tools=agent_tools,
        backend=backend,
        system_prompt=prompt_with_capabilities,
    )


def build_system_prompt_with_capabilities(
    *,
    system_prompt: str,
    session_id: str,
    created: bool,
    capabilities: dict[str, Any],
) -> str:
    return (
        f"{system_prompt.strip()}\n\n"
        "Cloud sandbox session context:\n"
        f"- session_id: {session_id}\n"
        f"- session_created_for_this_run: {str(created).lower()}\n"
        "- all shell/file operations run in this remote cloud-sandbox session\n"
        "- Deep Agents filesystem and shell operations use backend.execute() for command/file workflows\n"
        "- use the `run_injected_python` tool for Python code that needs `sandbox`, `sandbox_capabilities`, BigQuery, Firestore, or GCS\n"
        "- normal shell-launched Python, such as `python script.py`, does not receive injected Python globals\n"
        "- Python run through `run_injected_python` has injected globals: `sandbox` and `sandbox_capabilities`\n"
        "- inspect `sandbox_capabilities` or call `sandbox.capabilities()` inside injected Python when unsure\n\n"
        "Available cloud-sandbox capabilities JSON:\n"
        f"```json\n{json.dumps(capabilities, indent=2, sort_keys=True)}\n```\n\n"
        "Connector usage guidance:\n"
        "- Prefer the `run_injected_python` tool for data access, modeling code that touches cloud resources, and artifact metadata writes.\n"
        "- For BigQuery, use `sandbox.bigquery.query_df(sql)` or `sandbox.bigquery.query_rows(sql)`.\n"
        "- For Firestore metadata, use `sandbox.firestore.write_metadata(path, data)`.\n"
        "- For GCS artifacts, use `sandbox.gcs.upload_file(local_path, object_path)` or `sandbox.gcs.upload_bytes(data, object_path)`.\n"
        "- After every execution, inspect stdout, stderr, exit status, and any artifact paths before deciding the next step."
    )
