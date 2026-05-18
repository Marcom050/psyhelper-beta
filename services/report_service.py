"""Pure reporting and clinical recap helpers for PsyHelper.

The functions in this module are intentionally UI-agnostic: they do not import
Streamlit, do not read session state, and only operate on explicit arguments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd


HIGH_RISK_KEYWORDS = [
    "suicidio", "suicid", "farla finita", "non voglio vivere", "uccidermi", "autolesion", "tagliarmi",
    "morire", "overdose", "impicc", "buttarmi", "sparire per sempre",
]

AVOIDANCE_KEYWORDS = ["evito", "evitare", "rimando", "non sono uscito", "annullo", "isolamento", "mi isolo", "scappo"]
CATASTROPHIC_KEYWORDS = ["disastro", "catastrofe", "terribile", "non ce la farò", "andrà malissimo", "rovinerò", "fallirò"]
SOCIAL_KEYWORDS = ["sociale", "persone", "uscire", "gruppo", "festa", "colleghi", "giudicano", "vergogna"]
WORK_KEYWORDS = ["lavoro", "capo", "collega", "scadenza", "ufficio", "riunione", "cliente", "turno"]


@dataclass(frozen=True)
class ReportSection:
    """A titled report section made of already formatted text lines."""

    title: str
    lines: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class WeeklyRecap:
    """Textual pre-session recap generated from a clinical report."""

    items: list[str]

    def __iter__(self):
        return iter(self.items)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]

    def to_text(self, *, bullet_prefix: str = "") -> str:
        return "\n".join(f"{bullet_prefix}{item}" for item in self.items)


@dataclass(frozen=True)
class ClinicalReport:
    """Clinical snapshot and exportable report data produced from wellness inputs."""

    entries_count: int
    avg_anxiety: float
    avg_stress: float
    insights: list[str]
    alerts: list[str]
    homework_total: int
    homework_completed: int
    homework_compliance: float
    last_activity: str
    scope_df: pd.DataFrame = field(default_factory=pd.DataFrame, compare=False)
    export_text: str = ""
    sections: list[ReportSection] = field(default_factory=list)

    def __getitem__(self, key):
        return getattr(self, key)

    def as_dict(self) -> dict[str, Any]:
        return {
            "entries_count": self.entries_count,
            "avg_anxiety": self.avg_anxiety,
            "avg_stress": self.avg_stress,
            "insights": self.insights,
            "alerts": self.alerts,
            "homework_total": self.homework_total,
            "homework_completed": self.homework_completed,
            "homework_compliance": self.homework_compliance,
            "last_activity": self.last_activity,
            "scope_df": self.scope_df,
            "export_text": self.export_text,
            "sections": self.sections,
        }


def mood_entries_dataframe(wellness: Mapping[str, Any] | None) -> pd.DataFrame:
    """Return the existing mood-entry shape as a date-sorted DataFrame."""

    entries = (wellness or {}).get("mood_entries", [])
    if not entries:
        return pd.DataFrame()
    df = pd.DataFrame(entries)
    df["data"] = pd.to_datetime(df["data"], errors="coerce")
    return df.dropna(subset=["data"]).sort_values("data")


def most_common_values(series, limit=3):
    values = []
    for item in series.dropna():
        if isinstance(item, list):
            values.extend(item)
        elif item:
            values.extend([part.strip() for part in str(item).split(",") if part.strip()])
    return pd.Series(values).value_counts().head(limit) if values else pd.Series(dtype="int64")


def text_blob_from_entries(entries: Iterable[Mapping[str, Any]]) -> str:
    fields = ["trigger", "pensiero_automatico", "comportamento", "risposta_alternativa", "nota_professionista", "bisogno"]
    return " ".join(str(entry.get(field, "")) for entry in entries for field in fields).lower()


def keyword_hits(text: str, keywords: Sequence[str]) -> int:
    return sum(1 for keyword in keywords if keyword in text)


def _normalized_today(now=None):
    return pd.Timestamp.today().normalize() if now is None else pd.Timestamp(now).normalize()


def _scope_dataframe(df: pd.DataFrame, now=None) -> tuple[pd.DataFrame, pd.DataFrame, pd.Timestamp]:
    today = _normalized_today(now)
    if df.empty:
        return pd.DataFrame(), pd.DataFrame(), today
    last_14 = df[df["data"] >= today - pd.Timedelta(days=14)]
    prev_14 = df[(df["data"] < today - pd.Timedelta(days=14)) & (df["data"] >= today - pd.Timedelta(days=28))]
    return last_14 if not last_14.empty else df, prev_14, today


def build_export_text(scope_df: pd.DataFrame) -> tuple[str, list[ReportSection]]:
    """Build the text exported by the client report tab, preserving its format."""

    if scope_df.empty:
        return "", []

    trigger_counts = most_common_values(scope_df["trigger"], limit=5)
    sensation_counts = most_common_values(scope_df["sensazioni"], limit=5)
    mood_counts = scope_df["umore"].value_counts().head(5)
    notes = scope_df["nota_professionista"].dropna().tail(5)
    note_lines = [f"- {note}" for note in notes if str(note).strip()] or ["- Nessuna nota inserita."]

    sections = [
        ReportSection("Stati d'animo più frequenti", [f"- {name}: {count}" for name, count in mood_counts.items()]),
        ReportSection("Trigger ricorrenti", [f"- {name}: {count}" for name, count in trigger_counts.items()]),
        ReportSection("Sensazioni corporee ricorrenti", [f"- {name}: {count}" for name, count in sensation_counts.items()]),
        ReportSection("Ultime note per il professionista", note_lines),
    ]

    report = [
        "RESOCONTO PSYHELPER",
        f"Periodo: {scope_df['data'].min().date()} - {scope_df['data'].max().date()}",
        f"Schede compilate: {len(scope_df)}",
        f"Ansia media: {scope_df['ansia'].mean():.1f}/10",
        f"Stress medio: {scope_df['stress'].mean():.1f}/10",
        f"Intensità emotiva media: {scope_df['umore_intensita'].mean():.1f}/10",
        "",
    ]
    for index, section in enumerate(sections):
        report.append(f"{section.title}:")
        report.extend(section.lines)
        if index < len(sections) - 1:
            report.append("")

    return "\n".join(report), sections


def generate_clinical_report(wellness: Mapping[str, Any] | None, messages: Sequence[Mapping[str, Any]] | None = None, *, now=None) -> ClinicalReport:
    wellness = wellness or {}
    entries = wellness.get("mood_entries", [])
    messages = messages or []
    assignments = wellness.get("homework_assignments", [])
    submissions = wellness.get("homework_submissions", [])
    df = mood_entries_dataframe(wellness)
    scope_df, prev_14, today = _scope_dataframe(df, now=now)

    insights = []
    alerts = []
    if not scope_df.empty:
        avg_anxiety = scope_df["ansia"].mean()
        avg_stress = scope_df["stress"].mean()
        latest = scope_df.iloc[-1]
        if latest.get("ansia", 0) >= 8 or latest.get("umore_intensita", 0) >= 8:
            alerts.append("Forte intensità emotiva recente: potenziale area da attenzionare.")
        if not prev_14.empty and avg_anxiety - prev_14["ansia"].mean() >= 1.5:
            insights.append("Ansia in aumento rispetto alle 2 settimane precedenti.")
        monday_df = df[df["data"].dt.weekday == 0]
        if len(monday_df) >= 2 and monday_df["ansia"].mean() >= df["ansia"].mean() + 1:
            insights.append("Ansia tendenzialmente più alta il lunedì.")
        trigger_counts = most_common_values(scope_df.get("trigger", pd.Series(dtype="object")), limit=3)
        for trigger, count in trigger_counts.items():
            if count >= 2:
                insights.append(f"Trigger ricorrente: {trigger} ({count} rilevazioni).")
        if len(scope_df) <= 1 and len(df) >= 3:
            alerts.append("Riduzione delle compilazioni recenti: possibile rischio drop-out o calo aderenza.")
        last_entry_date = df["data"].max() if not df.empty else None
        if last_entry_date is not None and (today - last_entry_date.normalize()).days >= 7:
            alerts.append("Nessuna compilazione negli ultimi 7 giorni: verificare engagement.")
    else:
        avg_anxiety = avg_stress = 0
        alerts.append("Nessuna scheda compilata: aderenza non valutabile.")

    text_blob = text_blob_from_entries(entries) + " " + " ".join(str(m.get("content", "")) for m in messages).lower()
    if keyword_hits(text_blob, HIGH_RISK_KEYWORDS):
        alerts.append("Parole ad alto rischio rilevate: potenziale area da attenzionare, senza diagnosi automatica.")
    if keyword_hits(text_blob, CATASTROPHIC_KEYWORDS) >= 2:
        insights.append("Pensieri catastrofici ricorrenti nel materiale scritto.")
    if keyword_hits(text_blob, AVOIDANCE_KEYWORDS) >= 2:
        insights.append("Indicatori di evitamento in aumento o ricorrenti.")
    if keyword_hits(text_blob, SOCIAL_KEYWORDS) >= 2:
        insights.append("Temi sociali/interpersonali ricorrenti.")
    if keyword_hits(text_blob, WORK_KEYWORDS) >= 2:
        insights.append("Trigger legati al lavoro ricorrenti.")

    completed_ids = {submission.get("assignment_id") for submission in submissions}
    total_assignments = len(assignments)
    completed_assignments = len([a for a in assignments if a.get("id") in completed_ids or a.get("status") == "completato"])
    overdue = []
    for assignment in assignments:
        due_date = assignment.get("due_date")
        if assignment.get("id") in completed_ids:
            continue
        if due_date and pd.to_datetime(due_date, errors="coerce") < today:
            overdue.append(assignment)
    if overdue:
        alerts.append(f"{len(overdue)} homework assegnati risultano oltre scadenza.")

    export_text, sections = build_export_text(scope_df)
    return ClinicalReport(
        entries_count=len(scope_df),
        avg_anxiety=avg_anxiety,
        avg_stress=avg_stress,
        insights=insights[:6] or ["Servono più dati recenti per generare pattern affidabili."],
        alerts=alerts[:6],
        homework_total=total_assignments,
        homework_completed=completed_assignments,
        homework_compliance=(completed_assignments / total_assignments * 100) if total_assignments else 0,
        last_activity=df["data"].max().date().isoformat() if not df.empty else "—",
        scope_df=scope_df,
        export_text=export_text,
        sections=sections,
    )


def clinical_snapshot(wellness: Mapping[str, Any] | None, messages: Sequence[Mapping[str, Any]] | None = None, *, now=None) -> ClinicalReport:
    return generate_clinical_report(wellness, messages, now=now)


def weekly_recap(report: ClinicalReport | Mapping[str, Any]) -> WeeklyRecap:
    return WeeklyRecap([
        f"Schede ultime 2 settimane: {report['entries_count']}",
        f"Ansia media: {report['avg_anxiety']:.1f}/10",
        f"Stress medio: {report['avg_stress']:.1f}/10",
        f"Homework completati: {report['homework_completed']} su {report['homework_total']} ({report['homework_compliance']:.0f}%)",
        *report["insights"][:4],
    ])


def build_timeline_events(wellness: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    wellness = wellness or {}
    events = []
    for entry in wellness.get("mood_entries", []):
        events.append({
            "data": entry.get("data", entry.get("creata_il", "")),
            "tipo": "Diario",
            "titolo": f"{entry.get('umore', 'Umore')} · ansia {entry.get('ansia', '—')}/10",
            "dettaglio": entry.get("trigger") or entry.get("pensiero_automatico") or "Scheda CBT compilata",
        })
    for assignment in wellness.get("homework_assignments", []):
        events.append({
            "data": assignment.get("assigned_at", ""),
            "tipo": "Homework assegnato",
            "titolo": assignment.get("template", "Homework"),
            "dettaglio": assignment.get("instructions", ""),
        })
    for submission in wellness.get("homework_submissions", []):
        events.append({
            "data": submission.get("submitted_at", ""),
            "tipo": "Homework completato",
            "titolo": submission.get("template", "Homework"),
            "dettaglio": submission.get("summary", ""),
        })
    events.extend(wellness.get("timeline_events", []))
    return sorted(events, key=lambda item: str(item.get("data", "")), reverse=True)
