from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)

try:
    import docker
    from docker.errors import DockerException

    _DOCKER_AVAILABLE = True
except ImportError:
    _DOCKER_AVAILABLE = False
    DockerException = Exception  # type: ignore[misc,assignment]

SANDBOX_IMAGE = "python:3.12-slim"
SANDBOX_TIMEOUT = 30
SANDBOX_MEMORY_LIMIT = "256m"
SANDBOX_CPU_QUOTA = 50000

_VALIDATION_SCRIPT = r"""
import json, re, sys, os

schema = json.loads(os.environ.get("SCHEMA_GRAPH", "{}"))
code = os.environ.get("SQL_CODE", "")

errors = []

dangerous = [
    (r'\bDROP\b', 'DROP operations not permitted'),
    (r'\bTRUNCATE\b', 'TRUNCATE operations not permitted'),
    (r'\bALTER\b', 'ALTER operations not permitted'),
    (r'\bCREATE\b', 'CREATE operations not permitted'),
    (r'\bGRANT\b', 'GRANT operations not permitted'),
    (r'\bREVOKE\b', 'REVOKE operations not permitted'),
    (r'COPY\s+.*\s+FROM', 'COPY FROM operations not permitted'),
    (r';\s*--', 'Potential SQL injection via comment'),
    (r'\bOR\s+1\s*=\s*1\b', 'Tautology injection pattern detected'),
    (r"\bOR\s+'[^']*'\s*=\s*'[^']*'\b", 'Tautology string injection pattern detected'),
]

for pattern, msg in dangerous:
    if re.search(pattern, code, re.IGNORECASE):
        errors.append(msg)

is_select = re.search(r'\bSELECT\b', code, re.IGNORECASE)
is_write = re.search(r'(INSERT|UPDATE|DELETE)', code, re.IGNORECASE)

if is_write and not re.search(r'\$\d+', code):
    errors.append("Non-parameterized write query. Use $1, $2 notation for values.")

if schema.get("tables"):
    valid_cols = {}
    for t in schema["tables"]:
        valid_cols[t["name"].lower()] = {c["name"].lower() for c in t.get("columns", [])}
    refs = re.findall(r'\b(\w+)\.(\w+)\b', code)
    refs += re.findall(r'"(\w+)"\s*\.\s*"(\w+)"', code)
    for tbl, col in refs:
        if tbl.lower() in valid_cols and col.lower() not in valid_cols[tbl.lower()]:
            errors.append(
                f"Column '{col}' does not exist in table '{tbl}'. "
                f"Available: {sorted(valid_cols[tbl.lower()])}"
            )

print(json.dumps({"passed": len(errors) == 0, "errors": errors}))
"""


@dataclass
class SandboxResult:
    passed: bool
    errors: list[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""


class DockerSandboxService:
    def __init__(self) -> None:
        self._client: Any = None
        self._init_attempted = False

    def _ensure_client(self) -> bool:
        if self._init_attempted:
            return self._client is not None
        self._init_attempted = True
        if not _DOCKER_AVAILABLE:
            logger.info("sandbox_fallback", reason="docker_package_not_installed")
            return False
        try:
            self._client = docker.from_env()
            self._client.ping()
            logger.info("sandbox_docker_ready")
            return True
        except Exception:
            logger.info("sandbox_fallback", reason="docker_unavailable")
            self._client = None
            return False

    async def validate_sql(
        self,
        tenant_id: str,
        code: str,
        schema_graph: dict[str, Any],
    ) -> SandboxResult:
        if not self._ensure_client():
            return _validate_fallback(code, schema_graph)

        schema_json = json.dumps(schema_graph)
        container = None
        try:
            loop = __import__("asyncio").get_event_loop()
            container = await loop.run_in_executor(
                None,
                lambda: self._client.containers.run(
                    SANDBOX_IMAGE,
                    command=["python", "-c", _VALIDATION_SCRIPT],
                    environment={
                        "SCHEMA_GRAPH": schema_json,
                        "SQL_CODE": code,
                    },
                    network_disabled=True,
                    mem_limit=SANDBOX_MEMORY_LIMIT,
                    cpu_quota=SANDBOX_CPU_QUOTA,
                    read_only=True,
                    tmpfs={"/tmp": "size=64m"},
                    security_opt=["no-new-privileges:true"],
                    cap_drop=["ALL"],
                    remove=True,
                    labels={
                        "tenant_id": tenant_id,
                        "purpose": "sql-validation",
                    },
                    stdout=True,
                    stderr=True,
                ),
            )
            logs = container.decode("utf-8", errors="replace") if isinstance(container, bytes) else ""
            for line in reversed(logs.strip().split("\n")):
                try:
                    result = json.loads(line)
                    return SandboxResult(
                        passed=result.get("passed", False),
                        errors=result.get("errors", []),
                        stdout=logs,
                    )
                except json.JSONDecodeError:
                    continue
            return SandboxResult(False, [f"Sandbox output parse error: {logs[:200]}"], stdout=logs)
        except DockerException as e:
            logger.warning("sandbox_docker_error", error=str(e)[:200])
            return _validate_fallback(code, schema_graph)
        except Exception as e:
            logger.warning("sandbox_unexpected_error", error=str(e)[:200])
            return _validate_fallback(code, schema_graph)

    async def execute_code(
        self,
        tenant_id: str,
        code: str,
        language: str = "python",
        timeout: int = SANDBOX_TIMEOUT,
    ) -> SandboxResult:
        if not self._ensure_client():
            return SandboxResult(False, ["Docker not available for code execution"])

        try:
            loop = __import__("asyncio").get_event_loop()
            logs = await loop.run_in_executor(
                None,
                lambda: self._client.containers.run(
                    SANDBOX_IMAGE,
                    command=["python", "-c", code],
                    network_disabled=True,
                    mem_limit=SANDBOX_MEMORY_LIMIT,
                    cpu_quota=SANDBOX_CPU_QUOTA,
                    read_only=True,
                    tmpfs={"/tmp": "size=64m"},
                    security_opt=["no-new-privileges:true"],
                    cap_drop=["ALL"],
                    remove=True,
                    labels={
                        "tenant_id": tenant_id,
                        "purpose": "code-execution",
                    },
                    stdout=True,
                    stderr=True,
                ),
            )
            decoded = logs.decode("utf-8", errors="replace") if isinstance(logs, bytes) else logs
            return SandboxResult(passed=True, errors=[], stdout=decoded)
        except DockerException as e:
            return SandboxResult(False, [f"Execution error: {e!s}"], stderr=str(e))
        except Exception as e:
            return SandboxResult(False, [f"Execution error: {e!s}"], stderr=str(e))


def _validate_fallback(code: str, schema_graph: dict[str, Any]) -> SandboxResult:
    import re

    errors: list[str] = []

    dangerous = [
        (r"\bDROP\b", "DROP operations not permitted"),
        (r"\bTRUNCATE\b", "TRUNCATE operations not permitted"),
        (r"\bALTER\b", "ALTER operations not permitted"),
        (r"\bCREATE\b", "CREATE operations not permitted"),
        (r"\bGRANT\b", "GRANT operations not permitted"),
        (r"\bREVOKE\b", "REVOKE operations not permitted"),
        (r"COPY\s+.*\s+FROM", "COPY FROM operations not permitted"),
        (r";\s*--", "Potential SQL injection via comment"),
        (r"\bOR\s+1\s*=\s*1\b", "Tautology injection pattern detected"),
        (
            r"\bOR\s+'[^']*'\s*=\s*'[^']*'\b",
            "Tautology string injection pattern detected",
        ),
    ]

    for pattern, msg in dangerous:
        if re.search(pattern, code, re.IGNORECASE):
            errors.append(msg)

    if re.search(r"(INSERT|UPDATE|DELETE)", code, re.IGNORECASE) and not re.search(r"\$\d+", code):
        errors.append(
            "Non-parameterized write query. Use $1, $2 notation for values."
        )

    if schema_graph.get("tables"):
        valid_cols: dict[str, set[str]] = {}
        for t in schema_graph["tables"]:
            valid_cols[t["name"].lower()] = {
                c["name"].lower() for c in t.get("columns", [])
            }
        refs = re.findall(r"\b(\w+)\.(\w+)\b", code)
        refs += re.findall(r'"(\w+)"\s*\.\s*"(\w+)"', code)
        for tbl, col in refs:
            if tbl.lower() in valid_cols and col.lower() not in valid_cols[tbl.lower()]:
                errors.append(
                    f"Column '{col}' does not exist in table '{tbl}'. "
                    f"Available: {sorted(valid_cols[tbl.lower()])}"
                )

    return SandboxResult(passed=len(errors) == 0, errors=errors)


sandbox_service = DockerSandboxService()
