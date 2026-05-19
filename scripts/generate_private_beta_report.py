from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SECRET_MARKERS = ("secret", "token", "password", "authorization", "bearer", "api_key", "apikey", "credential")


def _is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return any(marker in lowered for marker in SECRET_MARKERS)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for k, v in value.items():
            if _is_secret_key(k):
                clean[k] = "[REDACTED]"
            else:
                clean[k] = _redact(v)
        return clean
    if isinstance(value, list):
        return [_redact(item) for item in value]
    return value


def _load_evidence(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"evidence file not found: {path}")
    try:
        payload = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in evidence file {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"evidence file must contain a JSON object: {path}")
    return _redact(payload)


def _render_report(evidence_docs: list[tuple[Path, dict[str, Any]]]) -> str:
    now = datetime.now(UTC).isoformat()
    lines = [
        "# Private beta rehearsal report draft",
        "",
        f"Generated at (UTC): {now}",
        "",
        "## Evidence summary",
    ]
    for idx, (path, doc) in enumerate(evidence_docs, start=1):
        checks = doc.get("checks_run", [])
        statuses = doc.get("status_per_check", {})
        warnings = doc.get("warnings", [])
        manual_follow_ups = doc.get("manual_follow_up_items", [])

        lines.extend(
            [
                "",
                f"### Evidence #{idx}",
                f"- Source: `{path}`",
                f"- Mode: `{doc.get('mode', 'unknown')}`",
                f"- Overall result: `{doc.get('overall_result', 'unknown')}`",
                f"- Base URL: `{doc.get('base_url', '')}`",
                f"- Checks run: {len(checks) if isinstance(checks, list) else 0}",
            ]
        )

        if isinstance(statuses, dict) and statuses:
            lines.append("- Check statuses:")
            for key, value in statuses.items():
                lines.append(f"  - `{key}`: `{value}`")

        if isinstance(warnings, list) and warnings:
            lines.append("- Warnings:")
            for item in warnings:
                lines.append(f"  - {item}")

        if isinstance(manual_follow_ups, list) and manual_follow_ups:
            lines.append("- Manual follow-up items:")
            for item in manual_follow_ups:
                lines.append(f"  - {item}")

    lines.extend(
        [
            "",
            "## Next actions",
            "- Copy this draft into the go/no-go report template.",
            "- Confirm unresolved blocker/high issues before any real therapist invite.",
            "- Keep rehearsal synthetic-only and retain evidence links.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a markdown private-beta rehearsal report from smoke evidence JSON.")
    parser.add_argument("--evidence", nargs="+", required=True, help="One or more evidence JSON file paths.")
    parser.add_argument("--output", default="", help="Optional markdown output file path. If omitted, report is printed to stdout.")
    args = parser.parse_args()

    try:
        evidence_docs = [(Path(path), _load_evidence(Path(path))) for path in args.evidence]
        report = _render_report(evidence_docs)
        if args.output:
            out = Path(args.output)
            if out.parent and not out.parent.exists():
                raise FileNotFoundError(f"output directory not found: {out.parent}")
            out.write_text(report)
            print(f"[INFO] Report written: {out}")
        else:
            print(report)
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
