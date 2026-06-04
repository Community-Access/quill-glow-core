# QUILL Integration Migration Guide

This guide shows practical migration patterns for QUILL to consume quill-glow-core in a consistent way.

## Scope

Use this package for shared audit, fix, markdown conversion, and version metadata contracts across applications.

## Startup Pattern

Initialize services once during process startup.

```python
from quill_glow_core import configure_default_services

services = configure_default_services()
```

Startup behavior:

- If GLOW backend is available, it is selected automatically.
- If not, NoOpCoreServices is selected as a safe fallback.
- Safe fallback avoids destructive behavior and returns actionable diagnostics.

The runtime startup decision is recorded and can be exposed through health/status endpoints.

Optional environment override:

```bash
set QUILL_GLOW_CORE_DISABLE_GLOW=1
```

## Health Endpoint Pattern

Use startup telemetry in status endpoints to report whether startup selected GLOW or safe mode.

```python
from flask import Flask, jsonify

from quill_glow_core import configure_default_services, get_startup_telemetry_dict


def create_app() -> Flask:
    app = Flask(__name__)
    configure_default_services()

    @app.get("/health/core")
    def core_health():
        return jsonify(get_startup_telemetry_dict())

    return app
```

## CLI Pattern

Use the package-level functions in command handlers, not backend internals.

```python
from quill_glow_core import audit_by_extension, configure_default_services


def main(file_path: str) -> int:
    configure_default_services()
    result = audit_by_extension(file_path)
    print(f"score={result.score} grade={result.grade}")
    return 0 if result.passed else 2
```

## Web Route Pattern

Bind services at application startup, then call package APIs in route handlers.

```python
from flask import Flask, jsonify, request

from quill_glow_core import audit_by_extension, configure_default_services


def create_app() -> Flask:
    app = Flask(__name__)
    configure_default_services()

    @app.post("/audit")
    def audit_route():
        payload = request.get_json(force=True)
        result = audit_by_extension(payload["file_path"])
        return jsonify(
            {
                "file_path": str(result.file_path),
                "score": result.score,
                "grade": result.grade,
                "passed": result.passed,
                "findings": [
                    {
                        "rule_id": f.rule_id,
                        "severity": f.severity,
                        "message": f.message,
                        "location": f.location,
                    }
                    for f in result.findings
                ],
            }
        )

    return app
```

## Background Worker Pattern

Use the same initialization in worker process boot and call shared APIs inside job handlers.

```python
from quill_glow_core import configure_default_services, fix_by_extension


configure_default_services()


def process_fix_job(file_path: str, output_path: str | None = None) -> dict:
    result = fix_by_extension(file_path, output_path=output_path)
    return {
        "output_path": str(result.output_path),
        "total_fixes": result.total_fixes,
        "score": result.audit_result.score,
        "warnings": list(result.warnings),
    }
```

## Rollout Checklist

1. Add quill-glow-core dependency to QUILL with pinned version.
2. Add startup bind call: configure_default_services().
3. Replace direct backend imports with package-level APIs.
4. Validate safe fallback behavior in an environment without GLOW backend.
5. Add integration tests for CLI, route, and worker entry points.
