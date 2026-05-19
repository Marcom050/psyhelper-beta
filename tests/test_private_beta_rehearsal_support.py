from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_report(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "scripts/generate_private_beta_report.py", *args], capture_output=True, text=True, check=False)


def test_rehearsal_templates_exist_and_key_language_present():
    go = Path("docs/private_beta_go_no_go_report_template.md")
    issue = Path("docs/private_beta_staging_issue_log_template.md")
    invite = Path("docs/first_trusted_therapist_invite_checklist.md")
    assert go.exists() and issue.exists() and invite.exists()

    go_text = go.read_text().lower()
    assert "go with conditions" in go_text
    assert "no-go" in go_text
    assert "blocker" in go_text


def test_templates_do_not_contain_obvious_real_secrets():
    markers = ["sk-", "akia", "-----begin", "real_secret", "prod_secret"]
    for path in [
        "docs/private_beta_go_no_go_report_template.md",
        "docs/private_beta_staging_issue_log_template.md",
        "docs/first_trusted_therapist_invite_checklist.md",
    ]:
        text = Path(path).read_text().lower()
        for m in markers:
            assert m not in text


def test_italian_copy_constraint_documented():
    text = Path("docs/private_beta_ux_flow.md").read_text().lower()
    assert "deve restare in italiano" in text


def test_valid_evidence_generates_markdown_and_includes_manual_followups(tmp_path):
    evidence = tmp_path / "evidence.json"
    out = tmp_path / "report.md"
    payload = {
        "mode": "dry-run",
        "overall_result": "pass",
        "checks_run": ["readiness_check"],
        "status_per_check": {"readiness_check": "pass"},
        "warnings": ["example warning"],
        "manual_follow_up_items": ["manual step A"],
    }
    evidence.write_text(json.dumps(payload))
    result = _run_report("--evidence", str(evidence), "--output", str(out))
    assert result.returncode == 0
    assert out.exists()
    report = out.read_text()
    assert "manual step A" in report
    assert "example warning" in report


def test_missing_evidence_path_fails_clearly(tmp_path):
    missing = tmp_path / "missing.json"
    result = _run_report("--evidence", str(missing))
    assert result.returncode == 2
    assert "evidence file not found" in result.stdout.lower()


def test_invalid_json_fails_clearly(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("{not json")
    result = _run_report("--evidence", str(bad))
    assert result.returncode == 2
    assert "invalid json" in result.stdout.lower()


def test_secret_like_keys_not_emitted(tmp_path):
    evidence = tmp_path / "evidence.json"
    payload = {
        "mode": "dry-run",
        "overall_result": "pass",
        "status_per_check": {"x": "pass"},
        "manual_follow_up_items": [],
        "api_token": "super-secret-value",
        "nested": {"password": "abc123"},
    }
    evidence.write_text(json.dumps(payload))
    result = _run_report("--evidence", str(evidence))
    assert result.returncode == 0
    output = result.stdout.lower()
    assert "super-secret-value" not in output
    assert "abc123" not in output
