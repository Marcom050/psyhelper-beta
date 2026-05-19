# First trusted therapist invite checklist (controlled private beta)

> Internal launch-readiness checklist. Do not send this document directly to therapists.

## 1) Prerequisites before invite
- [ ] A formal GO or GO WITH CONDITIONS decision exists in `docs/private_beta_go_no_go_report_template.md` output.
- [ ] No unresolved blocker issues.
- [ ] No unresolved high-severity issues.
- [ ] Staging smoke evidence captured and linked.
- [ ] Manual therapist/client flow validated with synthetic data only.
- [ ] Italian private beta disclaimer is visible in app onboarding/use flow.
- [ ] Support/contact path is defined for beta participants.
- [ ] Known limitations are documented and internally approved.
- [ ] Synthetic-data rehearsal execution is complete and archived.
- [ ] Legal/compliance caveat acknowledged (no claim of full production clinical compliance).
- [ ] Rollback/support procedure is documented and ready.

## 2) Invite wording checklist (content controls)
- [ ] Invite wording does not promise production-grade reliability.
- [ ] Invite wording does not claim clinical/compliance certification.
- [ ] Invite wording explicitly states private beta and limited-scope support.
- [ ] Invite wording avoids guarantees on uptime, data export latency, or roadmap dates.
- [ ] Any therapist-facing text remains in Italian.

## 3) What not to promise
- No guarantee of uninterrupted availability.
- No claim of full clinical compliance certification.
- No promise of immediate feature requests turnaround.
- No promise of irreversible data recovery for beta incidents.

## 4) Feedback to collect from first trusted therapist
- Onboarding clarity and friction points.
- Clarity of Italian UI warnings/disclaimers.
- Therapist workflow fit (client creation, mood tracking, homework, report/chat where enabled).
- Perceived reliability/performance of core beta flows.
- Severity-ranked issues with reproducible steps.

## 5) Post-invite monitoring checklist
- [ ] Confirm first login completed successfully.
- [ ] Monitor auth, audit, and error logs during first 48 hours.
- [ ] Track all reported issues in staging issue log format.
- [ ] Reassess GO WITH CONDITIONS risk items after initial usage window.
- [ ] Confirm support response-time expectations are being met.
