"""Tenant analytics foundation for therapist dashboard."""

from datetime import datetime, timedelta

from services import auth_service


def therapist_overview(therapist_username: str) -> dict:
    clients = auth_service.get_clients_for_tenant(therapist_username)
    active_clients = len(clients)
    recent_cutoff = datetime.utcnow() - timedelta(days=14)
    recent_mood = 0
    pending_homework = 0
    completed_homework = 0
    anxiety = []
    stress = []
    last_activity = None
    for client in clients:
        username = client.get("username")
        bundle = auth_service.load_account_bundle(username)
        wellness = bundle.get("wellness", {})
        mood_entries = wellness.get("mood_entries", [])
        if mood_entries:
            latest = max((m.get("data") or "" for m in mood_entries), default="")
            if latest:
                try:
                    if datetime.fromisoformat(latest) >= recent_cutoff:
                        recent_mood += 1
                except Exception:
                    pass
            for m in mood_entries:
                if isinstance(m.get("ansia"), int): anxiety.append(m["ansia"])
                if isinstance(m.get("stress"), int): stress.append(m["stress"])
        assignments = wellness.get("homework_assignments", [])
        submissions = wellness.get("homework_submissions", [])
        submitted = {s.get("assignment_id") for s in submissions if isinstance(s, dict)}
        pending_homework += len([a for a in assignments if isinstance(a, dict) and a.get("id") not in submitted])
        completed_homework += len(submitted)
    total_homework = pending_homework + completed_homework
    completion_pct = (completed_homework / total_homework * 100.0) if total_homework else 0.0
    return {
        "active_clients": active_clients,
        "clients_with_recent_mood_entries": recent_mood,
        "pending_homework_count": pending_homework,
        "homework_completion_pct": round(completion_pct, 2),
        "average_anxiety": round(sum(anxiety) / len(anxiety), 2) if anxiety else None,
        "average_stress": round(sum(stress) / len(stress), 2) if stress else None,
        "recent_activity_timestamp": last_activity,
    }
