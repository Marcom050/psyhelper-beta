from services.post_consultation_onboarding_service import (
    build_second_session_summary,
    ensure_post_consultation_onboarding,
    progress,
    save_step,
)


def test_progress_x_over_5():
    wellness = {}
    onboarding = ensure_post_consultation_onboarding(wellness)
    assert progress(onboarding) == (0, 5)
    save_step(onboarding, "baseline", {"mood": 6})
    assert progress(onboarding) == (1, 5)


def test_no_duplicate_active_onboarding_created():
    wellness = {}
    first = ensure_post_consultation_onboarding(wellness)
    second = ensure_post_consultation_onboarding(wellness)
    assert first["id"] == second["id"]
    assert len(wellness["post_consultation_onboardings"]) == 1


def test_completed_only_when_all_steps_done():
    wellness = {}
    onboarding = ensure_post_consultation_onboarding(wellness)
    save_step(onboarding, "baseline", {"mood": 5})
    assert onboarding["status"] == "active"
    for step in ("goals", "diary", "cbt", "next_session_note"):
        save_step(onboarding, step, {"ok": True})
    assert onboarding["status"] == "completed"
    summary = build_second_session_summary(onboarding)
    assert "non è diagnostico" in summary["disclaimer"]
