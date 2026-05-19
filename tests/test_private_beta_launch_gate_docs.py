from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_launch_gate_docs_exist():
    assert Path("docs/private_beta_launch_gate_checklist.md").exists()
    assert Path("docs/private_beta_rehearsal_commands.md").exists()
    assert Path("docs/private_beta_launch_gate_status.md").exists()


def test_launch_gate_status_blocked_until_safety_gate_completed():
    text = _read("docs/private_beta_launch_gate_status.md")
    assert "BLOCKED UNTIL COMMERCIAL BETA SAFETY GATE IS COMPLETED" in text


def test_launch_gate_rule_contains_all_decisions():
    text = _read("docs/private_beta_launch_gate_checklist.md")
    assert "GO WITH CONDITIONS" in text
    assert "GO WITH CONDITIONS" in text
    assert "NO-GO" in text


def test_invite_checklist_references_launch_gate_status():
    text = _read("docs/first_trusted_therapist_invite_checklist.md")
    assert "docs/private_beta_launch_gate_status.md" in text
    assert "GO or GO WITH CONDITIONS" in text


def test_docs_do_not_contain_real_secrets_or_real_urls():
    docs = [
        "docs/private_beta_launch_gate_checklist.md",
        "docs/private_beta_rehearsal_commands.md",
        "docs/private_beta_launch_gate_status.md",
    ]
    banned = ["sk-", "akia", "-----BEGIN", "http://", "https://"]
    for doc in docs:
        text = _read(doc)
        for marker in banned:
            assert marker not in text


def test_italian_ui_constraint_and_chat_logout_confirmation_documented():
    text = _read("docs/private_beta_launch_gate_checklist.md")
    assert "Product-facing text shown during rehearsal is in Italian" in text
    assert "Logout clears visible chat state automatically" in text
