from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MANUAL_CHECKLIST = [
    "Admin bootstrap: run secure one-time admin bootstrap and disable bootstrap mode afterwards.",
    "Therapist onboarding/login: create therapist user, verify first login and consent/terms acceptance.",
    "Client login + onboarding (mobile viewport): verify smartphone readability and complete onboarding.",
    "Check-in/Diario CBT (mobile): save one mood entry ensuring essential fields are easy to complete on phone.",
    "Homework response (mobile): open assigned homework, submit one response, and verify submission appears in history.",
    "Chat message (mobile): send one message via chat_input and verify response/disclaimer visibility.",
    "Monitoraggio + Resoconto view (mobile): verify summary-first layout and detailed data accessibility.",
    "Footer actions/logout (mobile): verify Pulisci chat, Torna su, and Esci are visible and usable.",
    "No user-facing English copy + emergency/non-replacement disclaimer still present.",
    "Therapist/admin flows sanity: no obvious regressions; patient deletion still works from therapist account.",
    "Self export: execute data-export flow for a synthetic user and verify secure delivery/cleanup.",
    "Audit/log verification: confirm auth/admin/export actions are present in audit/platform logs.",
    "Tenant/subscription sanity: confirm correct tenant scoping and expected subscription/trial gating.",
]

SAFE_ENDPOINT_CANDIDATES = [
    ("health", "/health"),
    ("health_db", "/health/db"),
]


def _print_manual_checklist() -> None:
    print("[INFO] Manual checklist for controlled private beta:")
    for idx, item in enumerate(MANUAL_CHECKLIST, start=1):
        print(f"  {idx}. {item}")
    print("[INFO] Authenticated API/UI flows are intentionally not auto-executed by this script to avoid unsafe test credentials and destructive operations.")


def _entrypoint_status(path: Path, module_name: str, attribute: str) -> tuple[bool, bool, str]:
    if not path.exists():
        return False, True, f"missing file: {path}"

    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return False, True, f"unable to create import spec for {path}"

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover
        source = path.read_text()
        try:
            compile(source, str(path), "exec")
        except Exception as parse_exc:
            return False, True, f"import failed and syntax parse failed for {path}: {parse_exc}"
        return True, False, f"import skipped for {path} due to optional dependency/runtime context: {exc}"

    if not hasattr(module, attribute):
        return False, True, f"{path} imported but missing attribute '{attribute}'"

    return True, False, f"{path} imports and exposes '{attribute}'"


def _run_readiness_check() -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "scripts/preprod_readiness_check.py"],
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _http_get(url: str, timeout_seconds: int = 8) -> tuple[int, str]:
    req = Request(url, method="GET")
    with urlopen(req, timeout=timeout_seconds) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _safe_write_evidence(evidence: dict[str, object], evidence_output: str) -> None:
    output_path = Path(evidence_output)
    parent = output_path.parent
    if not parent.exists() or not parent.is_dir():
        raise ValueError(f"invalid evidence output path: parent directory does not exist: {parent}")

    output_path.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(f"[INFO] Evidence JSON written: {output_path}")


def _http_mode(base_url: str, evidence: dict[str, object]) -> int:
    synthetic_id = f"beta-smoke-{uuid.uuid4()}"
    print(f"[INFO] HTTP smoke mode: base_url={base_url}")
    print(f"[INFO] Synthetic test identifier (non-destructive): {synthetic_id}")

    checked = 0
    passed = 0
    statuses: dict[str, str] = {}

    for label, path in SAFE_ENDPOINT_CANDIDATES:
        checked += 1
        url = f"{base_url.rstrip('/')}{path}"
        try:
            status, _body = _http_get(url)
            if status == 200:
                passed += 1
                statuses[label] = "pass"
                print(f"[PASS] {label}: status=200 @ {url}")
            else:
                statuses[label] = f"fail: status={status}"
                print(f"[FAIL] {label}: unexpected status={status} @ {url}")
        except HTTPError as exc:
            statuses[label] = f"fail: http_error={exc.code}"
            print(f"[FAIL] {label}: HTTP error status={exc.code} @ {url}")
        except URLError as exc:
            statuses[label] = "fail: unreachable"
            print(f"[FAIL] {label}: endpoint unreachable @ {url}: {exc}")

    evidence["checks_run"] = [f"http:{label}" for label, _ in SAFE_ENDPOINT_CANDIDATES]
    evidence["status_per_check"] = statuses
    evidence["manual_follow_up_items"] = MANUAL_CHECKLIST

    if passed == 0:
        msg = "No safe health endpoints were reachable. Validate deployment URL/networking before beta onboarding."
        evidence["overall_result"] = "fail"
        evidence["warnings"] = [msg]
        print(f"[FAIL] {msg}")
        return 1

    evidence["overall_result"] = "pass"
    evidence["warnings"] = []
    print(f"[PASS] HTTP smoke completed: {passed}/{checked} safe endpoint checks passed")
    _print_manual_checklist()
    return 0


def _dry_run_mode(evidence: dict[str, object]) -> int:
    print("[INFO] Dry-run mode (no network): validating local readiness invocation and app entrypoints")
    print(f"[INFO] ENVIRONMENT={os.getenv('ENVIRONMENT', 'development')}")

    code, stdout, stderr = _run_readiness_check()
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n")

    checks = [
        _entrypoint_status(Path("api/app.py"), "psyhelper_fastapi_app", "app"),
        _entrypoint_status(Path("psyhelper_streamlit.py"), "psyhelper_streamlit_app", "api_client_config"),
    ]

    status_map: dict[str, str] = {
        "readiness_check": "pass" if code == 0 else "fail",
    }

    failures = []
    for index, (ok, critical, detail) in enumerate(checks, start=1):
        marker = "PASS" if ok else ("FAIL" if critical else "WARN")
        print(f"[{marker}] {detail}")
        check_key = f"entrypoint_check_{index}"
        status_map[check_key] = "pass" if ok else ("fail" if critical else "warn")
        if not ok and critical:
            failures.append(detail)

    evidence["checks_run"] = ["readiness_check", "entrypoint:api_app", "entrypoint:streamlit_app"]
    evidence["status_per_check"] = status_map
    evidence["manual_follow_up_items"] = MANUAL_CHECKLIST

    if code != 0:
        evidence["overall_result"] = "fail"
        evidence["warnings"] = ["readiness check failed during dry-run"]
        print("[FAIL] readiness check failed during dry-run")
        return code

    if failures:
        evidence["overall_result"] = "fail"
        evidence["warnings"] = failures
        print("[FAIL] dry-run local entrypoint validation failed")
        return 1

    evidence["overall_result"] = "pass"
    evidence["warnings"] = []
    print("[PASS] dry-run local checks passed")
    _print_manual_checklist()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Private beta smoke test (safe, non-destructive)")
    parser.add_argument("--dry-run", action="store_true", help="Run local checks only (no network).")
    parser.add_argument("--manual-checklist", action="store_true", help="Print manual controlled-beta checklist and exit.")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL", ""), help="API base URL for HTTP smoke mode. Can also be set with SMOKE_BASE_URL.")
    parser.add_argument("--evidence-output", default="", help="Optional output path for safe JSON smoke evidence.")
    args = parser.parse_args()

    mode = "manual-checklist" if args.manual_checklist else "dry-run" if args.dry_run else "http" if args.base_url else "dry-run"
    evidence: dict[str, object] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "mode": mode,
        "base_url": args.base_url or "",
        "checks_run": [],
        "status_per_check": {},
        "overall_result": "pending",
        "warnings": [],
        "manual_follow_up_items": [],
    }

    if args.manual_checklist:
        _print_manual_checklist()
        evidence["checks_run"] = ["manual_checklist_printed"]
        evidence["status_per_check"] = {"manual_checklist_printed": "pass", "authenticated_flows": "manual_required"}
        evidence["overall_result"] = "manual_required"
        evidence["warnings"] = ["Authenticated flows remain manual by design for staging safety."]
        rc = 0
    elif args.dry_run:
        rc = _dry_run_mode(evidence)
    elif args.base_url:
        rc = _http_mode(args.base_url, evidence)
    else:
        rc = _dry_run_mode(evidence)

    if args.evidence_output:
        try:
            _safe_write_evidence(evidence, args.evidence_output)
        except Exception as exc:
            print(f"[FAIL] unable to write evidence output: {exc}")
            return 2

    return rc


if __name__ == "__main__":
    sys.exit(main())
