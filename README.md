# quill-glow-core

Shared audit/fix/convert core contracts for **GLOW** and **QUILL**.

## Purpose

This repository defines the stable shared-service interface used by host apps:

- `audit_by_extension(...)`
- `fix_by_extension(...)`
- `convert_to_markdown(...)`
- `get_component_versions()`

GLOW and QUILL can each provide concrete adapters that implement these contracts while preserving local UX and deployment behavior.

## Initial package

The package exports:

- data models (`Finding`, `AuditResult`, `FixResult`, `VersionManifest`)
- abstract service contract (`CoreServices`)
- service configuration helpers (`configure_services`, `get_services`)

## Next migration step

1. Move GLOW's `acb_large_print_core` implementation into this repo.
2. Publish a versioned package.
3. Update GLOW and QUILL to consume this package via pinned versions.
Shared document audit/fix/convert core for GLOW and QUILL
