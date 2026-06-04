from __future__ import annotations

from pathlib import Path
from typing import Any

import quill_glow_core.services as services_module
from quill_glow_core.models import AuditResult, Finding, VersionManifest
from quill_glow_core.services import DispatchCoreServices, NoOpCoreServices, StartupTelemetry


def test_dispatch_audit_handler_returns_normalized_audit_result() -> None:
    class RawFinding:
        rule_id = "RULE-1"
        severity = "High"
        message = "Example"
        location = "Paragraph 1"
        auto_fixable = True
        acb_reference = "ACB 1.2"

    class RawResult:
        file_path = "sample.docx"
        score = 88
        grade = "B"
        findings = [RawFinding()]

    def _audit(_path: Path, **_kwargs: Any) -> RawResult:
        return RawResult()

    services = DispatchCoreServices(audit_handlers={".docx": _audit})

    result = services.audit_by_extension("sample.docx")

    assert isinstance(result, AuditResult)
    assert result.score == 88
    assert result.grade == "B"
    assert result.findings[0] == Finding(
        rule_id="RULE-1",
        severity="High",
        message="Example",
        description="ACB 1.2",
        location="Paragraph 1",
        auto_fixable=True,
        metadata={"acb_reference": "ACB 1.2"},
    )


def test_dispatch_fix_handler_converts_glow_tuple_contract() -> None:
    base_audit = AuditResult(file_path=Path("sample.docx"), score=92, grade="A", findings=())

    def _audit(_path: Path, **_kwargs: Any) -> AuditResult:
        return base_audit

    def _fix(
        _path: Path,
        output_path: str | Path | None = None,
        **_kwargs: Any,
    ) -> tuple[Path, int, list[Any], AuditResult, list[str]]:
        return (
            Path(output_path) if output_path is not None else Path("sample-fixed.docx"),
            3,
            [],
            base_audit,
            ["one warning"],
        )

    services = DispatchCoreServices(audit_handlers={".docx": _audit}, fix_handlers={".docx": _fix})

    result = services.fix_by_extension("sample.docx")

    assert result.total_fixes == 3
    assert result.audit_result.score == 92
    assert result.warnings == ("one warning",)


def test_dispatch_fix_without_handler_returns_manual_warning() -> None:
    def _audit_md(_path: Path, **_kwargs: Any) -> AuditResult:
        return AuditResult(file_path=Path("sample.md"), score=70, grade="C", findings=())

    services = DispatchCoreServices(
        audit_handlers={".md": _audit_md}
    )

    result = services.fix_by_extension("sample.md")

    assert result.total_fixes == 0
    assert "Auto-fix is not available" in result.warnings[0]


def test_dispatch_version_provider_dict_normalizes_manifest() -> None:
    services = DispatchCoreServices(
        version_provider=lambda: {
            "release_version": "4.0.0",
            "desktop_package": "4.0.0",
            "markitdown": "0.1.0",
        }
    )

    versions = services.get_component_versions()

    assert versions == VersionManifest(
        release_version="4.0.0",
        core_version="4.0.0",
        components={
            "release_version": "4.0.0",
            "desktop_package": "4.0.0",
            "markitdown": "0.1.0",
        },
    )


def test_configure_default_services_uses_safe_mode_when_glow_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(services_module, "_active_services", None)
    services_module.reset_startup_telemetry()

    def _raise_runtime_error():
        raise RuntimeError("backend unavailable")

    monkeypatch.setattr(services_module, "from_glow_backend", _raise_runtime_error)

    services = services_module.configure_default_services(force=True)

    assert isinstance(services, NoOpCoreServices)
    assert services_module.get_startup_telemetry() == StartupTelemetry(
        backend="safe-mode",
        configured_by="configure_default_services",
        auto_selected=True,
    )


def test_configure_default_services_honors_disable_env(monkeypatch) -> None:
    monkeypatch.setattr(services_module, "_active_services", None)
    monkeypatch.setenv("QUILL_GLOW_CORE_DISABLE_GLOW", "1")
    services_module.reset_startup_telemetry()

    services = services_module.configure_default_services(force=True)

    assert isinstance(services, NoOpCoreServices)
    assert services_module.get_startup_telemetry() == StartupTelemetry(
        backend="safe-mode",
        configured_by="configure_default_services",
        auto_selected=True,
    )


def test_configure_services_records_manual_telemetry(monkeypatch) -> None:
    monkeypatch.setattr(services_module, "_active_services", None)
    services_module.reset_startup_telemetry()

    services_module.configure_services(NoOpCoreServices())

    assert services_module.get_startup_telemetry() == StartupTelemetry(
        backend="safe-mode",
        configured_by="configure_services",
        auto_selected=False,
    )


def test_get_startup_telemetry_dict_when_unset(monkeypatch) -> None:
    monkeypatch.setattr(services_module, "_active_services", None)
    services_module.reset_startup_telemetry()

    assert services_module.get_startup_telemetry_dict() == {
        "backend": "unknown",
        "configured_by": "unknown",
        "auto_selected": None,
    }


def test_get_startup_telemetry_dict_when_set(monkeypatch) -> None:
    monkeypatch.setattr(services_module, "_active_services", None)
    services_module.reset_startup_telemetry()

    services_module.configure_services(NoOpCoreServices())

    assert services_module.get_startup_telemetry_dict() == {
        "backend": "safe-mode",
        "configured_by": "configure_services",
        "auto_selected": False,
    }
