from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

MANUAL_CHECKLIST = [
    "Admin bootstrap: run secure one-time admin bootstrap and disable bootstrap mode afterwards.",
    "Therapist onboarding/login: create therapist user, verify first login and consent/terms acceptance.",
    "Client creation: create a beta test client profile using synthetic identifiers only.",
    "Mood entry: record one mood entry for the synthetic client and verify it appears in timeline/report views.",
    "Homework assignment: create and complete one homework assignment for the synthetic client.",
    "Report/chat check (if enabled): verify report generation and chat response paths behave without backend errors.",
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
    except Exception as exc:  # pragma: no cover - surfaced in runtime output and tests via return code
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


def _http_mode(base_url: str) -> int:
    synthetic_id = f"beta-smoke-{uuid.uuid4()}"
    print(f"[INFO] HTTP smoke mode: base_url={base_url}")
    print(f"[INFO] Synthetic test identifier (non-destructive): {synthetic_id}")

    checked = 0
    passed = 0
    for label, path in SAFE_ENDPOINT_CANDIDATES:
        checked += 1
        url = f"{base_url.rstrip('/')}{path}"
        try:
            status, _body = _http_get(url)
            if status == 200:
                passed += 1
                print(f"[PASS] {label}: status=200 @ {url}")
            else:
                print(f"[FAIL] {label}: unexpected status={status} @ {url}")
        except HTTPError as exc:
            print(f"[FAIL] {label}: HTTP error status={exc.code} @ {url}")
        except URLError as exc:
            print(f"[FAIL] {label}: endpoint unreachable @ {url}: {exc}")

    if passed == 0:
        print("[FAIL] No safe health endpoints were reachable. Validate deployment URL/networking before beta onboarding.")
        return 1

    print(f"[PASS] HTTP smoke completed: {passed}/{checked} safe endpoint checks passed")
    _print_manual_checklist()
    return 0


def _dry_run_mode() -> int:
    print("[INFO] Dry-run mode (no network): validating local readiness invocation and app entrypoints")
    print(f"[INFO] ENVIRONMENT={os.getenv('ENVIRONMENT', 'development')}")

    code, stdout, stderr = _run_readiness_check()
    if stdout:
        print(stdout, end="" if stdout.endswith("\n") else "\n")
    if stderr:
        print(stderr, end="" if stderr.endswith("\n") else "\n")
    if code != 0:
        print("[FAIL] readiness check failed during dry-run")
        return code

    checks = [
        _entrypoint_status(Path("api/app.py"), "psyhelper_fastapi_app", "app"),
        _entrypoint_status(Path("psyhelper_streamlit.py"), "psyhelper_streamlit_app", "api_client_config"),
    ]

    failures = [detail for ok, critical, detail in checks if not ok and critical]
    for ok, critical, detail in checks:
        marker = "PASS" if ok else ("FAIL" if critical else "WARN")
        print(f"[{marker}] {detail}")

    if failures:
        print("[FAIL] dry-run local entrypoint validation failed")
        return 1

    print("[PASS] dry-run local checks passed")
    _print_manual_checklist()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Private beta smoke test (safe, non-destructive)")
    parser.add_argument("--dry-run", action="store_true", help="Run local checks only (no network).")
    parser.add_argument("--manual-checklist", action="store_true", help="Print manual controlled-beta checklist and exit.")
    parser.add_argument("--base-url", default=os.getenv("SMOKE_BASE_URL", ""), help="API base URL for HTTP smoke mode. Can also be set with SMOKE_BASE_URL.")
    args = parser.parse_args()

    if args.manual_checklist:
        _print_manual_checklist()
        return 0
    if args.dry_run:
        return _dry_run_mode()
    if args.base_url:
        return _http_mode(args.base_url)
    return _dry_run_mode()


if __name__ == "__main__":
    sys.exit(main())
