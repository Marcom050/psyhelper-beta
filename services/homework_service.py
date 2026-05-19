"""Homework CBT service helpers for PsyHelper.

This module keeps homework application logic independent from Streamlit and
preserves the existing wellness JSON shape used by therapist and client views.
"""

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime


CBT_HOMEWORK_TEMPLATES = {
    "Respiro 3 minuti": {
        "obiettivo": "Ridurre l'attivazione fisica dell'ansia con una pausa breve e ripetibile.",
        "campi": ["Fallo una volta. Ansia prima/dopo 0-10 e una parola su com'è andata."],
        "suggerimento": "Adatto per ansia, tensione e momenti di blocco.",
    },
    "Pensiero più realistico": {
        "obiettivo": "Allenare una risposta più equilibrata a un pensiero ansioso o insicuro.",
        "campi": ["Scrivi: pensiero difficile + risposta più realistica."],
        "suggerimento": "Utile per ruminazione, catastrofismo e autocritica.",
    },
    "Piccolo passo evitato": {
        "obiettivo": "Ridurre l'evitamento con un'azione piccola, sicura e concreta.",
        "campi": ["Fai un passo di 5 minuti che stavi evitando. Scrivi quale."],
        "suggerimento": "Utile quando ansia o insicurezza portano a rimandare.",
    },
    "Tempo per le preoccupazioni": {
        "obiettivo": "Contenere i pensieri ripetitivi dando loro uno spazio limitato.",
        "campi": ["Dedica 10 minuti alle preoccupazioni. Scrivi solo le 2 principali."],
        "suggerimento": "Utile per sovrappensieri, stress e rimuginio serale.",
    },
    "Azione di cura": {
        "obiettivo": "Inserire un gesto semplice che sostenga energia, calma o autostima.",
        "campi": ["Fai una cosa gentile per te. Scrivi cosa e umore dopo 0-10."],
        "suggerimento": "Utile per stress, stanchezza e svalutazione di sé.",
    },
    "Nota per la seduta": {
        "obiettivo": "Tenere traccia di un punto importante da portare in colloquio.",
        "campi": ["Scrivi una cosa importante da ricordare in seduta."],
        "suggerimento": "Da usare quando serve una nota libera e breve.",
    },
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
    return template_name


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
        return "Completato"
    due = clean_text(assignment.get("due_date"))
    if due:
        try:
            if date.fromisoformat(due) < (today or date.today()):
                return "Scaduto"
        except ValueError:
            pass
    return "Da completare"


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
