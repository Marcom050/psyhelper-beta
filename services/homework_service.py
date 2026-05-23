"""Homework CBT service helpers for PsyHelper.

This module keeps homework application logic independent from Streamlit and
preserves the existing wellness JSON shape used by therapist and client views.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime


CBT_HOMEWORK_TEMPLATES = {
    "Respiro 3 minuti": {
        "titolo": "Respiro guidato di 3 minuti",
        "obiettivo": "Un breve esercizio per fermarti, osservare il momento presente e annotare cosa cambia prima e dopo.",
        "campi": ["Com'era il tuo stato prima dell'esercizio?"],
        "suggerimento": "Che cosa hai notato durante i 3 minuti? Com'è il tuo stato adesso?",
    },
    "Pensiero più realistico": {
        "titolo": "Pensiero più realistico",
        "obiettivo": "Questa scheda ti aiuta a osservare un pensiero difficile e a formulare una versione più equilibrata.",
        "campi": ["Quale pensiero difficile hai notato?"],
        "suggerimento": "Quali elementi lo sostengono? Quali elementi lo mettono in dubbio? Quale pensiero alternativo più realistico puoi formulare?",
    },
    "Piccolo passo evitato": {
        "titolo": "Piccolo passo verso una situazione evitata",
        "obiettivo": "Questa scheda ti aiuta a scegliere un piccolo passo realistico verso qualcosa che tendi a evitare.",
        "campi": ["Quale situazione o attività hai evitato?"],
        "suggerimento": "Quale piccolo passo realistico puoi fare? Quanto ti sembra difficile da 0 a 10?",
    },
    "Tempo per le preoccupazioni": {
        "titolo": "Spazio dedicato alle preoccupazioni",
        "obiettivo": "Questa scheda ti aiuta a raccogliere le preoccupazioni in uno spazio definito, invece di seguirle per tutta la giornata.",
        "campi": ["Quali preoccupazioni sono emerse?"],
        "suggerimento": "Quali sono sotto il tuo controllo, anche solo in parte? Cosa puoi lasciare in sospeso per ora?",
    },
    "Azione di cura": {
        "titolo": "Azione di cura personale",
        "obiettivo": "Questa scheda ti aiuta a scegliere una piccola azione concreta di cura verso di te e a osservare l'effetto che ha.",
        "campi": ["Quale piccola azione di cura hai scelto?"],
        "suggerimento": "Quando pensi di farla? Com'era il tuo stato prima e com'è stato dopo averla fatta?",
    },
    "Nota per la seduta": {
        "titolo": "Nota da portare in seduta",
        "obiettivo": "Questa scheda ti aiuta a segnare qualcosa che vuoi ricordare o discutere con il terapeuta durante la prossima seduta.",
        "campi": ["Che cosa vorresti portare in seduta?"],
        "suggerimento": "Perché ti sembra importante? C'è una domanda o un punto specifico che vuoi affrontare?",
    },
}

HOMEWORK_STATUS_LABELS = {
    "assigned": "Assegnato",
    "submitted": "Inviato",
    "reviewed": "Revisionato",
    "expired": "Scaduto",
    "completed": "Completato",
    "pending": "Da completare",
    "draft": "Bozza",
    "in_progress": "In compilazione",
}


@dataclass
class HomeworkAssignment:
    id: str
    template: str
    objective: str
    instructions: str
    questions: list
    due_date: str
    assigned_at: str
    assigned_by: str

    def to_dict(self):
        return asdict(self)


@dataclass
class HomeworkSubmission:
    assignment_id: str | None
    template: str
    answers: dict
    summary: str
    submitted_at: str

    def to_dict(self):
        return asdict(self)


@dataclass
class HomeworkStatus:
    assignment: dict
    submission: dict | None
    status: str


def clean_text(value):
    return str(value or "").strip()


def homework_template_label(template_name):
    return CBT_HOMEWORK_TEMPLATES.get(template_name, {}).get("titolo", template_name)


def format_homework_status_label(status):
    normalized = clean_text(status).lower().replace(" ", "_")
    if normalized in HOMEWORK_STATUS_LABELS:
        return HOMEWORK_STATUS_LABELS[normalized]
    return clean_text(status) or "Da completare"


def homework_questions_for(template_name, assignment=None):
    assignment = assignment or {}
    custom_questions = [clean_text(question) for question in assignment.get("questions", [])]
    custom_questions = [question for question in custom_questions if question]
    if custom_questions:
        return custom_questions
    template = CBT_HOMEWORK_TEMPLATES.get(template_name, {})
    return template.get("campi", ["Scrivi qui la tua risposta"])


def homework_main_prompt(template_name, assignment=None):
    questions = homework_questions_for(template_name, assignment)
    return questions[0] if questions else "Scrivi qui la tua risposta"


def homework_answer_items(answers):
    if isinstance(answers, dict):
        return [(clean_text(question), clean_text(answer)) for question, answer in answers.items() if clean_text(answer)]
    if isinstance(answers, list):
        return [(f"Risposta {index}", clean_text(answer)) for index, answer in enumerate(answers, start=1) if clean_text(answer)]
    answer = clean_text(answers)
    return [("Risposta", answer)] if answer else []


def homework_readable_summary(submission, max_chars=180):
    summary = clean_text(submission.get("summary"))
    answer_items = homework_answer_items(submission.get("answers", {}))
    readable = summary or (" · ".join(answer for _, answer in answer_items[:2]) if answer_items else "Nessuna risposta inserita.")
    return readable if len(readable) <= max_chars else f"{readable[:max_chars].rstrip()}…"


def validate_assignment(assignment):
    required = ["id", "template", "objective", "instructions", "questions", "due_date", "assigned_at", "assigned_by"]
    if not isinstance(assignment, dict):
        return False
    if any(key not in assignment for key in required):
        return False
    return isinstance(assignment.get("questions"), list)


def validate_submission(submission):
    required = ["assignment_id", "template", "submitted_at", "answers", "summary"]
    if not isinstance(submission, dict):
        return False
    if any(key not in submission for key in required):
        return False
    return isinstance(submission.get("answers"), dict)


def _iso_date(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return clean_text(value)


def _utc_now(now=None):
    return now or datetime.now(UTC)


def create_assignment(template_name, due_date, assigned_by, prompt=None, now=None):
    template = CBT_HOMEWORK_TEMPLATES[template_name]
    final_prompt = clean_text(prompt) or homework_main_prompt(template_name)
    assigned_at = _utc_now(now)
    assignment = HomeworkAssignment(
        id=f"hw_{assigned_at.strftime('%Y%m%d%H%M%S')}",
        template=template_name,
        objective=template["obiettivo"],
        instructions=clean_text(template.get("suggerimento")),
        questions=[final_prompt],
        due_date=_iso_date(due_date),
        assigned_at=assigned_at.isoformat(timespec="seconds"),
        assigned_by=assigned_by,
    ).to_dict()
    if not validate_assignment(assignment):
        raise ValueError("Invalid homework assignment")
    return assignment


def create_submission(assignment_id, template, prompt, answer, now=None):
    answers = {prompt: answer}
    submission = HomeworkSubmission(
        assignment_id=assignment_id,
        template=template,
        submitted_at=_utc_now(now).isoformat(timespec="seconds"),
        answers=answers,
        summary=homework_readable_summary({"answers": answers}, max_chars=140),
    ).to_dict()
    if not validate_submission(submission):
        raise ValueError("Invalid homework submission")
    return submission


def get_assigned_homework(wellness):
    return (wellness or {}).get("homework_assignments", [])


def get_submitted_homework(wellness):
    return (wellness or {}).get("homework_submissions", [])


def completed_assignment_ids(submissions):
    return {submission.get("assignment_id") for submission in submissions}


def get_open_assignments(assignments, submissions):
    completed_ids = completed_assignment_ids(submissions)
    return [assignment for assignment in assignments if assignment.get("id") not in completed_ids]


def assignment_status(assignment, completed_ids, today=None):
    if assignment.get("id") in completed_ids or assignment.get("status") == "completato":
        return format_homework_status_label("completed")
    due = clean_text(assignment.get("due_date"))
    if due:
        try:
            if date.fromisoformat(due) < (today or date.today()):
                return format_homework_status_label("expired")
        except ValueError:
            pass
    return format_homework_status_label("pending")


def homework_statuses(assignments, submissions, today=None):
    submissions_by_assignment = {submission.get("assignment_id"): submission for submission in submissions}
    completed_ids = set(submissions_by_assignment)
    return [
        HomeworkStatus(
            assignment=assignment,
            submission=submissions_by_assignment.get(assignment.get("id")),
            status=assignment_status(assignment, completed_ids, today=today),
        )
        for assignment in assignments
    ]


def homework_assignment_rows(assignments, completed_ids):
    rows = []
    for assignment in assignments:
        rows.append({
            "homework": assignment.get("template", "Homework"),
            "scadenza": assignment.get("due_date", "—"),
            "stato": assignment_status(assignment, completed_ids),
            "consegna": homework_main_prompt(assignment.get("template", "Homework"), assignment),
        })
    return rows


def submitted_homework_rows(submissions, display_defaults=True):
    return [
        {
            "data": submission.get("submitted_at", "—") if display_defaults else submission.get("submitted_at"),
            "homework": submission.get("template", "Homework") if display_defaults else submission.get("template"),
            "sintesi": homework_readable_summary(submission),
        }
        for submission in sorted(submissions, key=lambda item: item.get("submitted_at", ""), reverse=True)
    ]


def append_assignment(wellness, assignment):
    wellness.setdefault("homework_assignments", []).append(assignment)
    return wellness


def append_submission(wellness, submission):
    wellness.setdefault("homework_submissions", []).append(submission)
    return wellness
