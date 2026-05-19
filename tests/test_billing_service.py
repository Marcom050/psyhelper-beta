from datetime import datetime, timedelta, timezone

from services.billing_service import resolve_billing_status


def test_billing_trial_expired_to_grace():
    now = datetime.now(timezone.utc)
    state = resolve_billing_status({"billing_status": "trialing", "trial_ends_at": (now - timedelta(days=1)).isoformat()}, now=now)
    assert state.status == "grace_period"
