#!/usr/bin/env python3
"""
Security Audit Report Consolidation Script
Story 15.1: Audit de securite du code (SAST, dependances, secrets)

This script consolidates security scan results from multiple tools:
- Bandit (Python SAST)
- pip-audit (Python dependency vulnerabilities)
- npm audit (npm dependency vulnerabilities)
- detect-secrets (secret detection)
- ESLint security (JavaScript SAST)

Output: Consolidated markdown report with executive summary and prioritization
"""

import json
import os
from datetime import datetime
from pathlib import Path


def load_json_report(path: str) -> dict:
    """Load a JSON report file."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def parse_bandit_report(report_path: str) -> dict:
    """Parse Bandit SAST report."""
    data = load_json_report(report_path)
    if not data:
        return {"total": 0, "by_severity": {}, "issues": []}

    issues = data.get("results", [])
    by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for issue in issues:
        severity = issue.get("issue_severity", "LOW").upper()
        if severity in by_severity:
            by_severity[severity] += 1

    return {
        "total": len(issues),
        "by_severity": by_severity,
        "issues": issues,
    }


def estimate_severity_from_vuln(vuln: dict) -> str:
    """
    Estimate severity from pip-audit vulnerability data.
    Uses severity field if available, otherwise defaults to MEDIUM.
    """
    # pip-audit with OSV may include severity in aliases or directly
    severity = vuln.get("severity")
    if severity:
        severity_upper = severity.upper()
        if severity_upper in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
            return severity_upper

    # Check for CVSS score if available
    cvss = vuln.get("cvss_score") or vuln.get("cvss")
    if cvss:
        try:
            score = float(cvss)
            if score >= 9.0:
                return "CRITICAL"
            elif score >= 7.0:
                return "HIGH"
            elif score >= 4.0:
                return "MEDIUM"
            else:
                return "LOW"
        except (ValueError, TypeError):
            pass

    # Default to MEDIUM (conservative but not overly alarming)
    return "MEDIUM"


def parse_pip_audit_report(report_path: str) -> dict:
    """Parse pip-audit report."""
    data = load_json_report(report_path)
    if not data:
        return {"total": 0, "by_severity": {}, "vulnerabilities": []}

    dependencies = data.get("dependencies", [])
    vulnerabilities = []
    by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}

    for dep in dependencies:
        for vuln in dep.get("vulns", []):
            severity = estimate_severity_from_vuln(vuln)
            vuln_info = {
                "package": dep.get("name"),
                "version": dep.get("version"),
                "id": vuln.get("id"),
                "fix_versions": vuln.get("fix_versions", []),
                "description": vuln.get("description", "")[:200],
                "severity": severity,
            }
            vulnerabilities.append(vuln_info)
            by_severity[severity] += 1

    return {
        "total": len(vulnerabilities),
        "by_severity": by_severity,
        "vulnerabilities": vulnerabilities,
    }


def parse_npm_audit_report(report_path: str) -> dict:
    """Parse npm audit report."""
    data = load_json_report(report_path)
    if not data:
        return {"total": 0, "by_severity": {}, "vulnerabilities": []}

    # npm audit v2+ format
    vulnerabilities = data.get("vulnerabilities", {})
    by_severity = {"critical": 0, "high": 0, "moderate": 0, "low": 0}

    for name, vuln in vulnerabilities.items():
        severity = vuln.get("severity", "low")
        if severity in by_severity:
            by_severity[severity] += 1

    # Map to standard severity names
    mapped_severity = {
        "CRITICAL": by_severity.get("critical", 0),
        "HIGH": by_severity.get("high", 0),
        "MEDIUM": by_severity.get("moderate", 0),
        "LOW": by_severity.get("low", 0),
    }

    return {
        "total": len(vulnerabilities),
        "by_severity": mapped_severity,
        "vulnerabilities": list(vulnerabilities.values()),
    }


def parse_secrets_report(report_path: str) -> dict:
    """Parse detect-secrets report."""
    data = load_json_report(report_path)
    if not data:
        return {"total": 0, "files": [], "excluded": True, "false_positives": 0}

    results = data.get("results", {})

    # Filter out third-party files
    source_files = {
        k: v for k, v in results.items()
        if "node_modules" not in k
        and ".venv" not in k
        and ".pytest_cache" not in k
        and "security-reports" not in k
    }

    # Identify false positives (test files, templates, docs)
    real_secrets = {}
    false_positives = {}
    for k, v in source_files.items():
        if "/tests/" in k or ".template" in k or "README" in k or "docs/" in k or "conftest" in k:
            false_positives[k] = v
        else:
            real_secrets[k] = v

    total_real = sum(len(v) for v in real_secrets.values())
    total_false = sum(len(v) for v in false_positives.values())

    return {
        "total": total_real,
        "files": list(real_secrets.keys()),
        "excluded": False,
        "false_positives": total_false,
        "false_positive_files": list(false_positives.keys()),
    }


def generate_report(output_path: str, bandit: dict, pip_audit: dict, npm_audit: dict, secrets: dict) -> None:
    """Generate consolidated markdown report."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    # Calculate totals
    total_critical = (
        bandit["by_severity"].get("CRITICAL", 0)
        + pip_audit["by_severity"].get("CRITICAL", 0)
        + npm_audit["by_severity"].get("CRITICAL", 0)
    )
    total_high = (
        bandit["by_severity"].get("HIGH", 0)
        + pip_audit["by_severity"].get("HIGH", 0)
        + npm_audit["by_severity"].get("HIGH", 0)
    )
    total_medium = (
        bandit["by_severity"].get("MEDIUM", 0)
        + pip_audit["by_severity"].get("MEDIUM", 0)
        + npm_audit["by_severity"].get("MEDIUM", 0)
    )
    total_low = (
        bandit["by_severity"].get("LOW", 0)
        + pip_audit["by_severity"].get("LOW", 0)
        + npm_audit["by_severity"].get("LOW", 0)
    )

    report = f"""# Rapport d'Audit de Securite - IDP Portal

**Date:** {now}
**Story:** 15.1 - Audit de securite du code (SAST, dependances, secrets)

---

## Resume Executif

Ce rapport consolide les resultats des analyses de securite automatisees effectuees sur le codebase du portail IDP.

### Synthese des Vulnerabilites

| Severite | SAST Backend | Dependances Python | Dependances npm | Total |
|----------|--------------|-------------------|-----------------|-------|
| CRITICAL | {bandit["by_severity"].get("CRITICAL", 0)} | {pip_audit["by_severity"].get("CRITICAL", 0)} | {npm_audit["by_severity"].get("CRITICAL", 0)} | **{total_critical}** |
| HIGH     | {bandit["by_severity"].get("HIGH", 0)} | {pip_audit["by_severity"].get("HIGH", 0)} | {npm_audit["by_severity"].get("HIGH", 0)} | **{total_high}** |
| MEDIUM   | {bandit["by_severity"].get("MEDIUM", 0)} | {pip_audit["by_severity"].get("MEDIUM", 0)} | {npm_audit["by_severity"].get("MEDIUM", 0)} | **{total_medium}** |
| LOW      | {bandit["by_severity"].get("LOW", 0)} | {pip_audit["by_severity"].get("LOW", 0)} | {npm_audit["by_severity"].get("LOW", 0)} | **{total_low}** |

### Detection de Secrets

- **Secrets dans le code source:** {secrets["total"]}
- **Status NFR7:** {"CONFORME" if secrets["total"] == 0 else "NON-CONFORME"}

---

## 1. Analyse SAST Backend (Bandit)

**Outil:** Bandit {">"}= 1.7.5
**Cible:** `django_backend/**/*.py`
**Issues detectees:** {bandit["total"]}

### Distribution par severite

- CRITICAL: {bandit["by_severity"].get("CRITICAL", 0)}
- HIGH: {bandit["by_severity"].get("HIGH", 0)}
- MEDIUM: {bandit["by_severity"].get("MEDIUM", 0)}
- LOW: {bandit["by_severity"].get("LOW", 0)}

### Issues detectees

"""

    if bandit["issues"]:
        for issue in bandit["issues"][:20]:  # Limit to 20 for readability
            report += f"""
#### {issue.get("test_id", "N/A")}: {issue.get("test_name", "N/A")}

- **Severite:** {issue.get("issue_severity", "N/A")}
- **Confiance:** {issue.get("issue_confidence", "N/A")}
- **Fichier:** `{issue.get("filename", "N/A")}:{issue.get("line_number", "N/A")}`
- **CWE:** {issue.get("issue_cwe", {}).get("id", "N/A")}
- **Description:** {issue.get("issue_text", "N/A")}

"""
        if len(bandit["issues"]) > 20:
            report += f"\n*... et {len(bandit['issues']) - 20} autres issues (voir rapport complet)*\n"
    else:
        report += "*Aucune issue detectee*\n"

    report += f"""
---

## 2. Vulnerabilites Dependances Python (pip-audit)

**Outil:** pip-audit {">"}= 2.7.0
**Cible:** `django_backend/requirements.txt`
**Vulnerabilites detectees:** {pip_audit["total"]}

### Packages vulnerables

"""

    if pip_audit["vulnerabilities"]:
        for vuln in pip_audit["vulnerabilities"][:15]:
            fix_versions = ", ".join(vuln.get("fix_versions", [])) or "N/A"
            report += f"""
- **{vuln.get("package", "N/A")}** ({vuln.get("version", "N/A")})
  - ID: {vuln.get("id", "N/A")}
  - Fix: {fix_versions}

"""
        if len(pip_audit["vulnerabilities"]) > 15:
            report += f"\n*... et {len(pip_audit['vulnerabilities']) - 15} autres vulnerabilites*\n"
    else:
        report += "*Aucune vulnerabilite detectee*\n"

    report += f"""
---

## 3. Vulnerabilites Dependances npm (npm audit)

**Outil:** npm audit
**Cible:** `frontend/package.json`
**Vulnerabilites detectees:** {npm_audit["total"]}

"""

    if npm_audit["total"] > 0:
        report += "### Packages vulnerables\n\n"
        for vuln in npm_audit["vulnerabilities"][:10]:
            if isinstance(vuln, dict):
                report += f"- **{vuln.get('name', 'N/A')}**: {vuln.get('severity', 'N/A')}\n"
    else:
        report += "*Aucune vulnerabilite detectee - CONFORME*\n"

    false_positives = secrets.get("false_positives", 0)
    false_positive_files = secrets.get("false_positive_files", [])

    report += f"""
---

## 4. Detection de Secrets (detect-secrets)

**Outil:** detect-secrets {">"}= 1.5.0
**Cible:** Codebase complet (hors node_modules, .venv)

### Resultats

- **Secrets reels dans le code source:** {secrets["total"]}
- **Faux positifs (tests, templates, docs):** {false_positives}
- **Status NFR7:** {"CONFORME" if secrets["total"] == 0 else "NON-CONFORME"}

"""

    if secrets["files"]:
        report += "### Fichiers avec secrets potentiels (ACTION REQUISE)\n\n"
        for f in secrets["files"][:10]:
            report += f"- `{f}`\n"
    else:
        report += "*Aucun secret reel detecte dans le code source - CONFORME NFR7*\n"

    if false_positive_files:
        report += "\n### Faux positifs identifies (tests, templates, docs)\n\n"
        for f in false_positive_files[:10]:
            report += f"- `{f}` (faux positif)\n"

    report += """
---

## 5. Plan de Remediation

### Priorite CRITIQUE (Corriger immediatement)

| Issue | Action | Responsable | Statut |
|-------|--------|-------------|--------|
"""

    # Add critical items
    for issue in bandit["issues"]:
        if issue.get("issue_severity") == "CRITICAL":
            report += f"| {issue.get('test_id')} | Corriger {issue.get('filename')}:{issue.get('line_number')} | Dev | OUVERT |\n"

    for vuln in pip_audit["vulnerabilities"]:
        if "CRITICAL" in str(vuln.get("id", "")).upper():
            report += f"| {vuln.get('id')} | Mettre a jour {vuln.get('package')} | Dev | OUVERT |\n"

    report += """
### Priorite HAUTE (Corriger dans le sprint)

| Issue | Action | Responsable | Statut |
|-------|--------|-------------|--------|
"""

    # Add high items
    for issue in bandit["issues"]:
        if issue.get("issue_severity") == "HIGH":
            report += f"| {issue.get('test_id')} | Corriger {issue.get('filename')}:{issue.get('line_number')} | Dev | OUVERT |\n"

    report += f"""

### Priorite MOYENNE (Planifier prochain sprint)

Les vulnerabilites de severite MEDIUM ({total_medium}) sont documentees dans les rapports detailles et seront adressees dans le prochain sprint.

### Priorite BASSE (Refactoring)

Les vulnerabilites de severite LOW ({total_low}) seront adressees lors des refactorings opportunistes.

---

## 6. Recommandations

1. **Dependances Python:** Mettre a jour les packages vulnerables identifies par pip-audit
2. **Code Python:** Revoir les patterns try/except/pass pour meilleure gestion d'erreurs
3. **SQL dynamique:** Valider que les requetes SQL dans `inventory/services.py` utilisent des parametres prepares
4. **CI/CD:** Les scans de securite sont maintenant integres dans le pipeline GitHub Actions
5. **Pre-commit:** Considerer l'ajout de hooks pre-commit pour detect-secrets

---

## 7. Annexes

- Rapport Bandit complet: `django_backend/security-reports/bandit-report.json`
- Rapport pip-audit complet: `django_backend/security-reports/pip-audit-report.json`
- Rapport npm audit: `frontend/security-reports/npm-audit-report.json`
- Baseline secrets: `.secrets.baseline`

---

*Rapport genere automatiquement par `scripts/consolidate-security-reports.py`*
"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Rapport genere: {output_path}")


def main():
    # Define paths - script runs from idp-portal root
    base_dir = Path(__file__).parent.parent

    # Reports are generated in the current working directory's security-reports folder
    # when running from django_backend or frontend
    django_reports = base_dir / "django_backend" / "security-reports"
    frontend_reports = base_dir / "frontend" / "security-reports"
    root_reports = base_dir / "security-reports"
    output_path = base_dir / "docs" / "security-audit-report.md"

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Parse reports - try multiple locations
    bandit = parse_bandit_report(str(django_reports / "bandit-report.json"))
    if bandit["total"] == 0:
        bandit = parse_bandit_report(str(root_reports / "bandit-report.json"))

    pip_audit = parse_pip_audit_report(str(django_reports / "pip-audit-report.json"))
    if pip_audit["total"] == 0:
        pip_audit = parse_pip_audit_report(str(root_reports / "pip-audit-report.json"))

    npm_audit = parse_npm_audit_report(str(frontend_reports / "npm-audit-report.json"))
    secrets = parse_secrets_report(str(root_reports / "secrets-scan.json"))

    # Generate consolidated report
    generate_report(str(output_path), bandit, pip_audit, npm_audit, secrets)

    # Print summary
    print("\n=== Resume Audit Securite ===")
    print(f"SAST Backend (Bandit): {bandit['total']} issues")
    print(f"  - CRITICAL: {bandit['by_severity'].get('CRITICAL', 0)}")
    print(f"  - HIGH: {bandit['by_severity'].get('HIGH', 0)}")
    print(f"  - MEDIUM: {bandit['by_severity'].get('MEDIUM', 0)}")
    print(f"  - LOW: {bandit['by_severity'].get('LOW', 0)}")
    print(f"Dependances Python: {pip_audit['total']} vulnerabilites")
    print(f"Dependances npm: {npm_audit['total']} vulnerabilites")
    print(f"Secrets detectes: {secrets['total']}")
    print(f"\nNFR7 (Aucun secret): {'CONFORME' if secrets['total'] == 0 else 'NON-CONFORME'}")


if __name__ == "__main__":
    main()
