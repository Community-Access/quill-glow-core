from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    severity: str
    message: str
    description: str = ""
    location: str = ""
    auto_fixable: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class AuditResult:
    file_path: Path
    score: int
    grade: str
    findings: tuple[Finding, ...]

    @property
    def passed(self) -> bool:
        return self.score >= 90 and not any(f.severity.lower() == "critical" for f in self.findings)


@dataclass(frozen=True, slots=True)
class FixResult:
    output_path: Path
    total_fixes: int
    audit_result: AuditResult
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class VersionManifest:
    release_version: str
    core_version: str
    components: dict[str, str]
