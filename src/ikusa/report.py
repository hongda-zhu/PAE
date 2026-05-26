"""PDF compliance report generator.

WeasyPrint runs in a sandboxed Docker container (``ikusa-weasyprint:latest``)
so the host does not need libpango / libgdk-pixbuf installed. This module
renders the Jinja2 template to HTML, writes it to a temp dir, then shells
out to ``docker run`` to convert HTML -> PDF.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from ikusa.cra import CraMapper
from ikusa.models import (
    MasvsCategory,
    ScanResult,
    Severity,
    TriagedFinding,
)

_BASE = Path(__file__).parent
_TEMPLATES = _BASE / "templates"
_STATIC = _BASE / "static"
_DOCKER_IMAGE = "ikusa-weasyprint:latest"

_ENV = Environment(
    loader=FileSystemLoader(_TEMPLATES),
    autoescape=select_autoescape(["html", "xml"]),
)


class PdfRenderError(RuntimeError):
    pass


def _severity_label(sev: Severity) -> str:
    return {
        Severity.HIGH: "Alto",
        Severity.MEDIUM: "Medio",
        Severity.LOW: "Bajo",
        Severity.INFO: "Info",
    }[sev]


def _status_for(findings: list[TriagedFinding]) -> tuple[str, str]:
    """Return (label, css_class) for the MASVS row."""
    if not findings:
        return ("CUMPLE", "ok")
    max_sev = max(f.severity for f in findings)
    if max_sev == Severity.HIGH:
        return ("NO CUMPLE", "alto")
    return ("PARCIAL", "medio")


def _build_masvs_summary(findings: list[TriagedFinding]) -> list[dict[str, Any]]:
    buckets: dict[MasvsCategory, list[TriagedFinding]] = {}
    for f in findings:
        buckets.setdefault(f.masvs_category, []).append(f)
    rows = []
    for cat in sorted(buckets.keys(), key=lambda c: c.value):
        fs = buckets[cat]
        status, css = _status_for(fs)
        max_sev = max(f.severity for f in fs)
        rows.append(
            {
                "category": cat.value,
                "count": len(fs),
                "severity_label": _severity_label(max_sev),
                "status": status,
                "css_class": css,
            }
        )
    return rows


def _build_cra_rows(
    findings: list[TriagedFinding],
    cra: CraMapper,
) -> list[dict[str, str]]:
    grouped: dict[str, list[TriagedFinding]] = {}
    for f in findings:
        label = cra.short_label_for(f.masvs_category)
        grouped.setdefault(label, []).append(f)

    color_for = {
        "NO CUMPLE": "#E15759",
        "PARCIAL": "#F28E2B",
        "CUMPLE": "#59A14F",
    }
    rows = []
    for label in sorted(grouped.keys()):
        status, _ = _status_for(grouped[label])
        rows.append(
            {
                "label": label,
                "status": status,
                "color": color_for[status],
            }
        )
    return rows


def _render_html(result: ScanResult) -> str:
    cra = CraMapper.load_default()
    all_categories = {c.value for c in MasvsCategory}
    covered = {c.value for c in result.categories_covered}
    not_covered = sorted(all_categories - covered)

    top_findings = sorted(result.findings, key=lambda f: (f.priority, -f.severity._order))
    top_findings = top_findings[:3]

    template = _ENV.get_template("report.html.j2")
    inline_css = (_STATIC / "style.css").read_text()
    return template.render(
        inline_css=inline_css,
        app_name=result.app_name,
        package_name=result.package_name,
        scan_date=date.today().strftime("%d/%m/%Y"),
        cra_score=result.cra_score,
        masvs_summary=_build_masvs_summary(result.findings),
        not_covered=not_covered,
        top_findings=top_findings,
        cra_rows=_build_cra_rows(result.findings, cra),
    )


def _run_weasyprint(html_path: Path, pdf_path: Path) -> None:
    """Invoke WeasyPrint locally if available on PATH, otherwise fallback to Docker."""
    if shutil.which("weasyprint") is not None:
        cmd = [
            "weasyprint",
            str(html_path),
            str(pdf_path),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise PdfRenderError(
                f"Local WeasyPrint exited {proc.returncode}: {proc.stderr.strip()}"
            )
        return

    if shutil.which("docker") is None:
        raise PdfRenderError("Neither 'weasyprint' nor 'docker' is on PATH; cannot render PDF")

    workdir = html_path.parent.resolve()
    cmd = [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{workdir}:/work",
        _DOCKER_IMAGE,
        f"/work/{html_path.name}",
        f"/work/{pdf_path.name}",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise PdfRenderError(
            f"WeasyPrint container exited {proc.returncode}: {proc.stderr.strip()}"
        )


def generate_pdf(result: ScanResult, output_path: Path) -> Path:
    """Render a ScanResult into a compliance PDF at ``output_path``."""
    html_str = _render_html(result)
    output_path = output_path.resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        html_path = tmp / "report.html"
        pdf_path = tmp / "report.pdf"
        html_path.write_text(html_str, encoding="utf-8")
        _run_weasyprint(html_path, pdf_path)
        shutil.copy2(pdf_path, output_path)

    return output_path
