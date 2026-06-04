# quill-glow-core

Shared audit/fix/convert core for GLOW and QUILL with a stable host-facing API.

## What is included

This package now includes both:

1. Stable contracts and data models for host applications.
2. A concrete dispatch implementation aligned with GLOW's extension-based shared core.

Primary host APIs:

- `audit_by_extension(...)`
- `fix_by_extension(...)`
- `convert_to_markdown(...)`
- `get_component_versions()`

## Architecture

Core building blocks:

- `CoreServices`: abstract service contract.
- `DispatchCoreServices`: concrete extension-based dispatcher.
- `NoOpCoreServices`: safe fallback used when no backend is available.
- `configure_services(...)` and `get_services()`: process-level service binding.
- `configure_default_services(...)`: auto-binds GLOW when available, otherwise safe mode.
- `from_glow_backend()`: adapter factory for direct interoperability with GLOW core modules.
- `get_startup_telemetry()`: returns runtime startup backend selection details.

Model surface:

- `Finding`
- `AuditResult`
- `FixResult`
- `VersionManifest`

## Install

Base package:

```bash
pip install quill-glow-core
```

With GLOW adapter support:

```bash
pip install "quill-glow-core[glow]"
```

## Quick start

### Use the GLOW backend directly

```python
from quill_glow_core import configure_services, from_glow_backend, audit_by_extension

configure_services(from_glow_backend())
result = audit_by_extension("example.docx")
print(result.score, result.grade)
```

### Use automatic startup binding (recommended)

```python
from quill_glow_core import configure_default_services

services = configure_default_services()
print(type(services).__name__)
```

Behavior:

- If GLOW backend modules are importable, GLOW dispatch is activated.
- If not, safe mode is activated and calls remain non-destructive.

To force safe mode even when GLOW is installed:

```bash
set QUILL_GLOW_CORE_DISABLE_GLOW=1
```

### Startup telemetry for health/status endpoints

```python
from quill_glow_core import (
    configure_default_services,
    get_startup_telemetry,
    get_startup_telemetry_dict,
)

configure_default_services()
telemetry = get_startup_telemetry()
print(telemetry)

# JSON-ready payload for web frameworks
payload = get_startup_telemetry_dict()
print(payload)
```

Telemetry includes:

- backend: selected backend name, such as `glow` or `safe-mode`
- configured_by: startup path that configured services
- auto_selected: whether selection was automatic or manual

### Register custom handlers for QUILL or other hosts

```python
from pathlib import Path

from quill_glow_core import DispatchCoreServices, configure_services
from quill_glow_core.models import AuditResult


def audit_docx(path: Path, **_kwargs) -> AuditResult:
    return AuditResult(file_path=path, score=100, grade="A", findings=())


services = DispatchCoreServices()
services.register_audit_handler(".docx", audit_docx)
configure_services(services)
```

## Cross-utilization hardening

The dispatcher includes normalization logic so host apps receive stable output types even when
backend libraries return different shapes.

Examples:

- GLOW tuple fix return values are normalized into `FixResult`.
- Third-party finding objects are normalized into `Finding`.
- Dictionary version manifests are normalized into `VersionManifest`.

This isolates host apps from backend drift and preserves a consistent public contract.

## Supported extensions

The following table lists default extension scopes exposed by this package.

| API | Extension set |
| --- | --- |
| Audit | `.docx`, `.xlsx`, `.pptx`, `.md`, `.pdf`, `.epub` |
| Fix | `.docx`, `.xlsx`, `.pptx`, `.md`, `.pdf`, `.epub` |
| Convert | Backend-defined via the active service adapter |

## Migration guidance for host apps

1. Bind services at process startup with `configure_services(...)`.
2. Prefer top-level function APIs in route/CLI code.
3. Keep host-specific policy and UX behavior outside this package.
4. Pin `quill-glow-core` with semantic versions in consuming apps.

See also: [docs/quill-integration-migration.md](docs/quill-integration-migration.md) for
QUILL-focused migration examples (CLI, web route, and background worker).
