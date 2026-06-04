from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .models import AuditResult, Finding, FixResult, VersionManifest

SUPPORTED_AUDIT_EXTENSIONS = {".docx", ".xlsx", ".pptx", ".md", ".pdf", ".epub"}
SUPPORTED_FIX_EXTENSIONS = set(SUPPORTED_AUDIT_EXTENSIONS)

# Conversion extension support is delegated to the active adapter backend. This keeps
# the core package lightweight while letting host apps expose richer conversion support.


AuditHandler = Callable[..., Any]
FixHandler = Callable[..., Any]
ConvertHandler = Callable[..., tuple[Path, str]]


@dataclass(frozen=True, slots=True)
class StartupTelemetry:
    backend: str
    configured_by: str
    auto_selected: bool


_startup_telemetry: StartupTelemetry | None = None


def _set_startup_telemetry(
    *,
    backend: str,
    configured_by: str,
    auto_selected: bool,
) -> None:
    global _startup_telemetry
    _startup_telemetry = StartupTelemetry(
        backend=backend,
        configured_by=configured_by,
        auto_selected=auto_selected,
    )


def get_startup_telemetry() -> StartupTelemetry | None:
    """Return the latest startup backend selection telemetry."""
    return _startup_telemetry


def get_startup_telemetry_dict() -> dict[str, Any]:
    """Return startup telemetry as a JSON-serializable dictionary."""
    telemetry = get_startup_telemetry()
    if telemetry is None:
        return {
            "backend": "unknown",
            "configured_by": "unknown",
            "auto_selected": None,
        }
    return {
        "backend": telemetry.backend,
        "configured_by": telemetry.configured_by,
        "auto_selected": telemetry.auto_selected,
    }


def reset_startup_telemetry() -> None:
    """Clear in-memory startup telemetry, mainly for tests."""
    global _startup_telemetry
    _startup_telemetry = None


def _coerce_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


def _coerce_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_finding(finding: Any) -> Finding:
    severity = str(getattr(finding, "severity", "low"))
    description = str(
        getattr(finding, "description", "") or getattr(finding, "acb_reference", "") or ""
    )
    metadata: dict[str, Any] = {}
    acb_reference = getattr(finding, "acb_reference", None)
    if acb_reference:
        metadata["acb_reference"] = str(acb_reference)

    return Finding(
        rule_id=str(getattr(finding, "rule_id", "unknown-rule")),
        severity=severity,
        message=str(getattr(finding, "message", "")),
        description=description,
        location=str(getattr(finding, "location", "")),
        auto_fixable=bool(getattr(finding, "auto_fixable", False)),
        metadata=metadata,
    )


def _normalize_audit_result(value: Any, file_path_hint: str | Path | None = None) -> AuditResult:
    if isinstance(value, AuditResult):
        return value

    file_path = getattr(value, "file_path", file_path_hint)
    if file_path is None:
        raise TypeError("Audit result is missing file_path and no file path hint was provided.")

    findings_raw = getattr(value, "findings", ())
    findings = tuple(_normalize_finding(f) for f in findings_raw)

    score = getattr(value, "score", None)
    if callable(score):
        score = score()
    if score is None:
        score = 100 if not findings else 0
    score_int = _coerce_int(score, default=0)

    grade = getattr(value, "grade", None)
    if callable(grade):
        grade = grade()
    if grade is None:
        grade = "A" if score_int >= 90 else "F"

    return AuditResult(
        file_path=_coerce_path(file_path),
        score=score_int,
        grade=str(grade),
        findings=findings,
    )


def _normalize_fix_result(value: Any, file_path_hint: str | Path | None = None) -> FixResult:
    if isinstance(value, FixResult):
        return value

    # GLOW-compatible tuple contract: (output_path, total_fixes, fix_records, post_audit, warnings)
    if isinstance(value, tuple):
        tuple_value = cast(tuple[Any, ...], value)
        if len(tuple_value) < 5:
            tuple_value = ()
    else:
        tuple_value = ()

    if tuple_value:
        output_path = cast(str | Path, tuple_value[0])
        total_fixes = tuple_value[1]
        post_audit = tuple_value[3]
        warnings = tuple_value[4]
        return FixResult(
            output_path=_coerce_path(output_path),
            total_fixes=_coerce_int(total_fixes, default=0),
            audit_result=_normalize_audit_result(post_audit, file_path_hint=file_path_hint),
            warnings=tuple(str(w) for w in warnings),
        )

    obj = cast(Any, value)
    output_path = getattr(obj, "output_path", None)
    if output_path is None:
        output_path = file_path_hint
    if output_path is None:
        raise TypeError("Fix result is missing output_path and no file path hint was provided.")

    audit_result = getattr(obj, "audit_result", None)
    if audit_result is None:
        audit_result = getattr(obj, "post_audit", None)
    if audit_result is None:
        raise TypeError("Fix result is missing audit_result/post_audit.")

    return FixResult(
        output_path=_coerce_path(output_path),
        total_fixes=_coerce_int(getattr(obj, "total_fixes", 0), default=0),
        audit_result=_normalize_audit_result(audit_result, file_path_hint=file_path_hint),
        warnings=tuple(str(w) for w in getattr(obj, "warnings", ())),
    )


def _normalize_version_manifest(value: Any) -> VersionManifest:
    if isinstance(value, VersionManifest):
        return value

    if isinstance(value, Mapping):
        raw_components = cast(Mapping[Any, Any], value)
        components = {str(k): str(v) for k, v in raw_components.items()}
        release_version = str(components.get("release_version", "unknown"))
        core_version = str(
            components.get("core_version")
            or components.get("desktop_package")
            or components.get("quill_glow_core")
            or "unknown"
        )
        return VersionManifest(
            release_version=release_version,
            core_version=core_version,
            components=components,
        )

    release_version = str(getattr(value, "release_version", "unknown"))
    core_version = str(getattr(value, "core_version", "unknown"))
    components = getattr(value, "components", {})
    if not isinstance(components, dict):
        components = {}
    normalized_components = cast(dict[Any, Any], components)
    return VersionManifest(
        release_version=release_version,
        core_version=core_version,
        components={str(k): str(v) for k, v in normalized_components.items()},
    )


class CoreServices(ABC):
    """Stable shared-core contract for host apps (GLOW, QUILL)."""

    @abstractmethod
    def audit_by_extension(self, file_path: str | Path, **kwargs: Any) -> AuditResult:
        raise NotImplementedError

    @abstractmethod
    def fix_by_extension(
        self,
        file_path: str | Path,
        output_path: str | Path | None = None,
        **kwargs: Any,
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


class DispatchCoreServices(CoreServices):
    """Concrete shared-core dispatch service.

    Host applications can register extension handlers directly, or use
    `from_glow_backend()` to bridge to GLOW's existing dispatcher modules.
    """

    def __init__(
        self,
        *,
        audit_handlers: dict[str, AuditHandler] | None = None,
        fix_handlers: dict[str, FixHandler] | None = None,
        convert_handler: ConvertHandler | None = None,
        version_provider: Callable[[], Any] | None = None,
    ) -> None:
        self._audit_handlers = {
            ext.lower(): handler for ext, handler in (audit_handlers or {}).items()
        }
        self._fix_handlers = {ext.lower(): handler for ext, handler in (fix_handlers or {}).items()}
        self._convert_handler = convert_handler
        self._version_provider = version_provider

    def register_audit_handler(self, extension: str, handler: AuditHandler) -> None:
        self._audit_handlers[extension.lower()] = handler

    def register_fix_handler(self, extension: str, handler: FixHandler) -> None:
        self._fix_handlers[extension.lower()] = handler

    def set_convert_handler(self, handler: ConvertHandler) -> None:
        self._convert_handler = handler

    def set_version_provider(self, provider: Callable[[], Any]) -> None:
        self._version_provider = provider

    def audit_by_extension(self, file_path: str | Path, **kwargs: Any) -> AuditResult:
        path = _coerce_path(file_path)
        ext = path.suffix.lower()
        handler = self._audit_handlers.get(ext)
        if handler is None:
            supported = ", ".join(sorted(self._audit_handlers)) or "none"
            raise ValueError(
                f"Unsupported audit extension '{ext}'. Registered extensions: {supported}."
            )
        return _normalize_audit_result(handler(path, **kwargs), file_path_hint=path)

    def fix_by_extension(
        self,
        file_path: str | Path,
        output_path: str | Path | None = None,
        **kwargs: Any,
    ) -> FixResult:
        path = _coerce_path(file_path)
        ext = path.suffix.lower()
        handler = self._fix_handlers.get(ext)
        if handler is None:
            post_audit = self.audit_by_extension(path, **kwargs)
            return FixResult(
                output_path=path,
                total_fixes=0,
                audit_result=post_audit,
                warnings=(
                    (
                        f"Auto-fix is not available for '{ext}' in the active services backend. "
                        "Review audit findings and apply manual remediation."
                    ),
                ),
            )

        result = handler(path, output_path=output_path, **kwargs)
        return _normalize_fix_result(result, file_path_hint=path)

    def convert_to_markdown(
        self,
        src_path: str | Path,
        output_path: str | Path | None = None,
    ) -> tuple[Path, str]:
        if self._convert_handler is None:
            raise RuntimeError("No markdown conversion handler is configured.")

        out_path, text = self._convert_handler(_coerce_path(src_path), output_path=output_path)
        return _coerce_path(out_path), str(text)

    def get_component_versions(self) -> VersionManifest:
        if self._version_provider is None:
            return VersionManifest(
                release_version="unknown",
                core_version="unknown",
                components={"quill_glow_core": "unknown"},
            )
        return _normalize_version_manifest(self._version_provider())


class NoOpCoreServices(CoreServices):
    """Safe-mode service that avoids hard failures when no backend is installed."""

    def audit_by_extension(self, file_path: str | Path, **kwargs: Any) -> AuditResult:
        del kwargs
        path = _coerce_path(file_path)
        ext = path.suffix.lower()
        finding = Finding(
            rule_id="CORE-NO-BACKEND",
            severity="high",
            message=(
                "No shared-core backend is configured. "
                "Install optional GLOW support or register custom handlers."
            ),
            description="Operation ran in safe mode.",
            location=str(path),
            auto_fixable=False,
            metadata={"extension": ext},
        )
        return AuditResult(file_path=path, score=0, grade="F", findings=(finding,))

    def fix_by_extension(
        self,
        file_path: str | Path,
        output_path: str | Path | None = None,
        **kwargs: Any,
    ) -> FixResult:
        del kwargs
        path = _coerce_path(file_path)
        out = path if output_path is None else _coerce_path(output_path)
        return FixResult(
            output_path=out,
            total_fixes=0,
            audit_result=self.audit_by_extension(path),
            warnings=(
                "No-op safe mode is active. No changes were applied.",
                "Install optional GLOW support or register custom handlers.",
            ),
        )

    def convert_to_markdown(
        self,
        src_path: str | Path,
        output_path: str | Path | None = None,
    ) -> tuple[Path, str]:
        del output_path
        path = _coerce_path(src_path)
        raise RuntimeError(
            "No backend conversion handler is configured. "
            "Install optional GLOW support or register a convert handler. "
            f"Source: {path}"
        )

    def get_component_versions(self) -> VersionManifest:
        return VersionManifest(
            release_version="unknown",
            core_version="safe-mode",
            components={
                "quill_glow_core": "safe-mode",
                "backend": "none",
            },
        )


def from_glow_backend() -> DispatchCoreServices:
    """Create a dispatch service backed by GLOW's canonical core modules."""
    try:
        from acb_large_print_core import services as glow_services  # type: ignore[import-not-found]
        from acb_large_print_core import versions as glow_versions  # type: ignore[import-not-found]
    except Exception as exc:
        raise RuntimeError(
            "GLOW backend is unavailable. Install optional dependency 'quill-glow-core[glow]' "
            "or provide custom handlers via DispatchCoreServices."
        ) from exc

    audit_handlers: dict[str, AuditHandler] = {
        ext: glow_services.audit_by_extension for ext in SUPPORTED_AUDIT_EXTENSIONS
    }
    glow_services_any = cast(Any, glow_services)
    glow_fix_handler = cast(FixHandler, glow_services_any.fix_by_extension)
    fix_handlers: dict[str, FixHandler] = {
        ext: glow_fix_handler for ext in SUPPORTED_FIX_EXTENSIONS
    }

    service = DispatchCoreServices(
        audit_handlers=audit_handlers,
        fix_handlers=fix_handlers,
        convert_handler=glow_services.convert_to_markdown,
        version_provider=glow_versions.get_component_versions,
    )
    return service


def configure_default_services(force: bool = False) -> CoreServices:
    """Configure services by auto-selecting GLOW backend, else safe mode."""
    global _active_services
    if _active_services is not None and not force:
        return _active_services

    disable_glow = os.getenv("QUILL_GLOW_CORE_DISABLE_GLOW", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    if not disable_glow:
        try:
            _active_services = from_glow_backend()
            _set_startup_telemetry(
                backend="glow",
                configured_by="configure_default_services",
                auto_selected=True,
            )
            return _active_services
        except RuntimeError:
            pass

    _active_services = NoOpCoreServices()
    _set_startup_telemetry(
        backend="safe-mode",
        configured_by="configure_default_services",
        auto_selected=True,
    )
    return _active_services


def audit_by_extension(file_path: str | Path, **kwargs: Any) -> AuditResult:
    return get_services().audit_by_extension(file_path, **kwargs)


def fix_by_extension(
    file_path: str | Path,
    output_path: str | Path | None = None,
    **kwargs: Any,
) -> FixResult:
    return get_services().fix_by_extension(file_path=file_path, output_path=output_path, **kwargs)


def convert_to_markdown(
    src_path: str | Path,
    output_path: str | Path | None = None,
) -> tuple[Path, str]:
    return get_services().convert_to_markdown(src_path=src_path, output_path=output_path)


def get_component_versions() -> VersionManifest:
    return get_services().get_component_versions()


_active_services: CoreServices | None = None


def configure_services(services: CoreServices) -> None:
    global _active_services
    _active_services = services
    _set_startup_telemetry(
        backend=(
            "glow"
            if services.__class__.__name__ == "DispatchCoreServices"
            else "safe-mode"
            if isinstance(services, NoOpCoreServices)
            else services.__class__.__name__
        ),
        configured_by="configure_services",
        auto_selected=False,
    )


def get_services() -> CoreServices:
    if _active_services is None:
        return configure_default_services()
    return _active_services
