from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REQUIRED_FLOWS = [
    "health",
    "signup/onboarding therapist",
    "login",
    "create client",
    "mood entry",
    "homework assignment",
    "chat/report (if available)",
    "export self",
    "readiness check",
]


def _http_mode(base_url: str) -> int:
    health_url = f"{base_url.rstrip('/')}/health"
    try:
        with urlopen(health_url, timeout=5) as resp:
            if resp.status != 200:
                print(f"[FAIL] health endpoint status={resp.status} @ {health_url}")
                return 1
    except URLError as exc:
        print(f"[FAIL] health endpoint unreachable @ {health_url}: {exc}")
        return 1

    print(f"[PASS] health endpoint reachable @ {health_url}")
    print("[WARN] HTTP smoke currently validates connectivity only; run manual checklist for authenticated flows:")
    for item in REQUIRED_FLOWS[1:]:
        print(f"  - {item}")
    return 0


def _dry_run_mode() -> int:
    print("[PASS] dry-run mode: smoke script import/config checks only")
    print(f"ENVIRONMENT={os.getenv('ENVIRONMENT', 'development')}")
    import subprocess

    result = subprocess.run([sys.executable, 'scripts/preprod_readiness_check.py'], capture_output=True, text=True, check=False)
    print(result.stdout, end='')
    code = result.returncode
    if code != 0:
        print("[FAIL] readiness check failed during dry-run smoke")
        return code

    required_files = [Path("api/app.py"), Path("psyhelper_streamlit.py")]
    missing = [str(p) for p in required_files if not p.exists()]
    if missing:
        print(f"[FAIL] required files missing: {', '.join(missing)}")
        return 1

    print("[PASS] readiness check and required app entrypoints available")
    print("[WARN] no running API detected; execute manual private-beta flow checklist:")
    for item in REQUIRED_FLOWS:
        print(f"  - {item}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Private beta smoke test (safe, non-destructive)")
    parser.add_argument("--base-url", default="", help="API base URL (e.g. http://localhost:8000). If omitted, dry-run mode is used.")
    args = parser.parse_args()
    return _http_mode(args.base_url) if args.base_url else _dry_run_mode()


if __name__ == "__main__":
    sys.exit(main())
