from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from .models import AuditResult, FixResult, VersionManifest


class CoreServices(ABC):
    """Stable shared-core contract for host apps (GLOW, QUILL)."""

    @abstractmethod
    def audit_by_extension(self, file_path: str | Path, **kwargs) -> AuditResult:
        raise NotImplementedError

    @abstractmethod
    def fix_by_extension(
        self,
        file_path: str | Path,
        output_path: str | Path | None = None,
        **kwargs,
    ) -> FixResult:
        raise NotImplementedError

    @abstractmethod
    def convert_to_markdown(
        self,
        src_path: str | Path,
        output_path: str | Path | None = None,
    ) -> tuple[Path, str]:
        raise NotImplementedError

    @abstractmethod
    def get_component_versions(self) -> VersionManifest:
        raise NotImplementedError


_active_services: CoreServices | None = None


def configure_services(services: CoreServices) -> None:
    global _active_services
    _active_services = services


def get_services() -> CoreServices:
    if _active_services is None:
        raise RuntimeError("Shared core services are not configured.")
    return _active_services
